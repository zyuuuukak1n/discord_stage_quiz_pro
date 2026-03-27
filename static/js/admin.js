const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${window.location.host}/ws/audience`;

let ws;

function refreshScoreboard(ranking) {
    const adminRanking = document.getElementById('adminRanking');
    if (!adminRanking) return;
    
    adminRanking.innerHTML = '';
    ranking.forEach(u => {
        const row = document.createElement('div');
        row.className = "flex justify-between items-center p-3 bg-gray-900 rounded border border-gray-700";
        row.innerHTML = `
            <div class="font-semibold">${u.display_name}</div>
            <div class="flex items-center gap-3">
                <span class="text-cyan-400 font-black">${u.score} pt</span>
                <button onclick="editUserScore(${u.id}, '${u.display_name}', ${u.score})" class="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded border border-gray-600">✏️ Edit</button>
            </div>
        `;
        adminRanking.appendChild(row);
    });
}

// 自動再接続機能付きのWebSocket接続
function connectWebSocket() {
    ws = new WebSocket(wsUrl);

    ws.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.action === "SYNC_STATE") {
            document.getElementById('statusBox').innerText = data.state;
            if (data.answering_user_id) {
                document.getElementById('currentAnswererId').value = data.answering_user_id;
                document.getElementById('currentAnswererName').innerText = data.answering_user_name || "Unknown";
            }
        }
        else if (data.action === "START_QUESTION") {
            document.getElementById('statusBox').innerText = "ASKING";
            document.getElementById('currentAnswererName').innerText = "Waiting...";
            document.getElementById('currentAnswererId').value = "";
        }
        else if (data.action === "PAUSE_QUESTION") {
            document.getElementById('statusBox').innerText = "PAUSED";
            if (data.user_id) {
                document.getElementById('currentAnswererId').value = data.user_id;
                document.getElementById('currentAnswererName').innerText = data.display_name;
            }
        }
        else if (data.action === "RESUME_QUESTION") {
            document.getElementById('statusBox').innerText = "ASKING";
        }
        else if (data.action === "SHOW_ANSWER") {
            document.getElementById('statusBox').innerText = "SHOWING ANSWER";
        }
        else if (data.action === "SHOW_CHOICES") {
            document.getElementById('statusBox').innerText = "ASKING";
        }
        else if (data.action === "JUDGEMENT") {
            document.getElementById('statusBox').innerText = "WAITING";
            document.getElementById('currentAnswererName').innerText = "Waiting...";
            document.getElementById('currentAnswererId').value = "";
            if (data.ranking) {
                refreshScoreboard(data.ranking);
            }
        }
        else if (data.action === "RESET_STATE") {
            document.getElementById('statusBox').innerText = "WAITING";
            document.getElementById('currentAnswererName').innerText = "Waiting...";
            document.getElementById('currentAnswererId').value = "";
        }
    };

    // 切断されたら1秒後に再接続する
    ws.onclose = function () {
        console.log("WebSocket disconnected. Reconnecting in 1 second...");
        setTimeout(connectWebSocket, 1000);
    };
}

// 初回接続
connectWebSocket();

function updatePointsFields() {
    const select = document.getElementById("questionSelect");
    if (select && select.value && typeof questionsData !== 'undefined' && questionsData[select.value]) {
        document.getElementById('correctPoints').value = questionsData[select.value].points;
        document.getElementById('incorrectPoints').value = 0;
    }
}

window.addEventListener('DOMContentLoaded', updatePointsFields);
document.getElementById('questionSelect').addEventListener('change', updatePointsFields);

async function nextQuestion() {
    if (!confirm("現在の回答者をオーディエンスに戻し、次の問題に進みますか？")) return;

    await apiCall('/api/state/return_audience');

    const select = document.getElementById("questionSelect");
    if (select.selectedIndex < select.options.length - 1) {
        select.selectedIndex += 1;
        select.dispatchEvent(new Event('change'));
    } else {
        alert("最後の問題です！");
    }
}

async function apiCall(endpoint, method = "POST") {
    try {
        const response = await fetch(endpoint, { method: method });
        const res = await response.json();
        console.log(res);
        return res;
    } catch (err) {
        console.error("API Call error:", err);
    }
}

async function startQuestion() {
    const select = document.getElementById("questionSelect");
    const qId = select.value;
    if (!qId) return alert("Please specify a question ID!");
    await apiCall(`/api/state/start_question/${qId}`);
}

async function judge(isCorrect) {
    const userId = document.getElementById("currentAnswererId").value;
    if (!userId) {
        alert("No answerer currently registered via Hand-Raise!\n（通信切断または挙手が行われていません）");
        return;
    }

    const points = isCorrect
        ? parseInt(document.getElementById('correctPoints').value)
        : parseInt(document.getElementById('incorrectPoints').value);

    try {
        const response = await fetch(`/api/state/judgement?user_id=${userId}&is_correct=${isCorrect}&point_change=${points}`, {
            method: 'POST'
        });
        const res = await response.json();

        if (res.status === "error") {
            alert("エラー: " + res.message);
        } else {
            console.log("Judgement successful:", res);
        }
    } catch (err) {
        console.error("API Call error:", err);
    }
}

async function factoryReset() {
    const code = prompt("🚨 警告 🚨\n本当にすべてのデータ（ユーザー、スコア、問題の進行状態）を削除し、初期状態に戻しますか？\n実行する場合は「RESET」と入力してください。");
    if (code === "RESET") {
        await apiCall('/api/state/hard_reset');
        alert("Factory Reset が完了しました。ページをリロードします。");
        window.location.reload();
    } else if (code !== null) {
        alert("入力が間違っています。キャンセルされました。");
    }
}

async function editUserScore(userId, displayName, currentScore) {
    const newScoreStr = prompt(`✏️ ${displayName} の新しいスコアを入力してください:`, currentScore);
    if (newScoreStr === null || newScoreStr === "") return;
    
    const newScore = parseInt(newScoreStr, 10);
    if (isNaN(newScore)) {
        alert("無効な数値です。");
        return;
    }
    
    try {
        const response = await fetch(`/api/state/users/${userId}/score?score=${newScore}`, { method: 'PUT' });
        const res = await response.json();
        if (res.status === "ok") {
            window.location.reload(); // リロードして画面更新
        } else {
            alert("エラー: " + res.message);
        }
    } catch (err) {
        console.error("API Call error:", err);
    }
}