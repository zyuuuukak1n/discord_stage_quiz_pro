const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${window.location.host}/ws/audience`;
const ws = new WebSocket(wsUrl);

function updatePointsFields() {
    const select = document.getElementById("questionSelect");
    if (select && select.value && questionsData[select.value]) {
        document.getElementById('correctPoints').value = questionsData[select.value].points;
        document.getElementById('incorrectPoints').value = -questionsData[select.value].points;
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
    else if (data.action === "JUDGEMENT") {
        document.getElementById('statusBox').innerText = "WAITING";
        document.getElementById('currentAnswererName').innerText = "Waiting...";
        document.getElementById('currentAnswererId').value = "";
        window.location.reload();
    }
    else if (data.action === "RESET_STATE") {
        document.getElementById('statusBox').innerText = "WAITING";
        document.getElementById('currentAnswererName').innerText = "Waiting...";
        document.getElementById('currentAnswererId').value = "";
    }
};

async function apiCall(endpoint, method = "POST") {
    try {
        const response = await fetch(endpoint, { method: method });
        const res = await response.json();
        console.log(res);
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
        alert("No answerer currently registered via Hand-Raise!");
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
        console.log(res);
    } catch (err) {
        console.error("API Call error:", err);
    }
}
