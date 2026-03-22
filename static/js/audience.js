const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const wsUrl = `${wsProtocol}//${window.location.host}/ws/audience`;

let ws;
function connectWebSocket() {
    ws = new WebSocket(wsUrl);
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleAction(data);
    };
    ws.onclose = function() {
        setTimeout(connectWebSocket, 1000);
    };
}
connectWebSocket();

function resizeScreen() {
    const scaleX = window.innerWidth / 1920;
    const scaleY = window.innerHeight / 1080;
    const scale = Math.min(scaleX, scaleY);
    
    const dx = (window.innerWidth - 1920 * scale) / 2;
    const dy = (window.innerHeight - 1080 * scale) / 2;
    
    document.body.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
}
window.addEventListener('resize', resizeScreen);
resizeScreen();

let fullQuestionText = "";
let currentTypedIndex = 0;
let isPaused = false;
let typeInterval = null;

const elQuestionText = document.getElementById("questionText");
const elContainer = document.getElementById("questionContainer");
const elAnswererPopup = document.getElementById("answererPopup");
const elAnswererName = document.getElementById("answererName");
const elTimerText = document.getElementById("timerText");

function updateRanking(ranking) {
    const container = document.getElementById("rankingList");
    container.innerHTML = "";
    ranking.slice(0, 5).forEach((user, index) => {
        const colors = index === 0 ? "text-neon-gold" : (index === 1 ? "text-gray-300" : (index === 2 ? "text-orange-400" : "text-white"));
        const div = document.createElement("div");
        div.className = `flex justify-between items-center ${colors}`;
        div.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="font-display text-sm opacity-70">0${index+1}</span>
                <span class="truncate max-w-[200px]">${user.display_name}</span>
            </div>
            <div class="font-display tracking-wider">${user.score} pt</div>
        `;
        container.appendChild(div);
    });
}

function playSound(type) {
}

function startTypingEffect() {
    if (typeInterval) clearInterval(typeInterval);
    elContainer.classList.add("typing-cursor");
    
    typeInterval = setInterval(() => {
        if (isPaused) return;

        if (currentTypedIndex < fullQuestionText.length) {
            elQuestionText.innerText = fullQuestionText.substring(0, currentTypedIndex + 1);
            currentTypedIndex++;
        } else {
            clearInterval(typeInterval);
            elContainer.classList.remove("typing-cursor");
        }
    }, 80);
}

function handleAction(data) {
    console.log("WS Data received:", data);
    
    if (data.action === "SYNC_STATE") {
        updateRanking(data.ranking || []);
        if (data.state === "asking" || data.state === "paused") {
            fullQuestionText = data.question_text;
            elQuestionText.innerText = fullQuestionText;
            elContainer.classList.remove("typing-cursor");
            
            if (data.state === "paused" && data.answering_user_name) {
                elAnswererName.innerText = data.answering_user_name;
                elAnswererPopup.classList.remove("hidden");
            }
        } else {
            elQuestionText.innerText = "WAITING FOR NEXT QUESTION...";
        }
    }
    else if (data.action === "START_QUESTION") {
        fullQuestionText = data.question_text || "";
        elQuestionText.innerText = "";
        currentTypedIndex = 0;
        isPaused = false;
        elAnswererPopup.classList.add("hidden");
        startTypingEffect();
        
        elTimerText.innerText = "QUESTION IN PROGRESS...";
        
    }
    else if (data.action === "PAUSE_QUESTION" || data.action === "ANSWER_REQUEST") {
        isPaused = true;
        elContainer.classList.remove("typing-cursor");
        
        if (data.display_name) {
            elAnswererName.innerText = data.display_name;
            elAnswererPopup.classList.remove("hidden");
            const pAnim = elAnswererPopup.querySelector('.popup-anim');
            pAnim.style.animation = 'none';
            pAnim.offsetHeight;
            pAnim.style.animation = null; 
        }
        
        elTimerText.innerText = "PAUSED";
    }
    else if (data.action === "RESUME_QUESTION") {
        isPaused = false;
        elAnswererPopup.classList.add("hidden");
        elContainer.classList.add("typing-cursor");
        elTimerText.innerText = "QUESTION IN PROGRESS...";
    }
    else if (data.action === "SHOW_ANSWER") {
        isPaused = false;
        currentTypedIndex = fullQuestionText.length;
        elQuestionText.innerText = fullQuestionText;
        clearInterval(typeInterval);
        elContainer.classList.remove("typing-cursor");
        elAnswererPopup.classList.add("hidden");
        elTimerText.innerText = "ANSWER REVEAL";
    }
    else if (data.action === "JUDGEMENT") {
        elAnswererPopup.classList.add("hidden");
        if (data.ranking) updateRanking(data.ranking);
        
        const judgmentOverlay = document.createElement("div");
        judgmentOverlay.className = "fixed inset-0 z-[100] flex items-center justify-center pointer-events-none";
        const color = data.is_correct ? "text-green-500 border-green-500" : "text-red-500 border-red-500";
        const text = data.is_correct ? "CORRECT!" : "INCORRECT";
        
        judgmentOverlay.innerHTML = `
            <div class="animate-bounce font-display font-black text-9xl ${color} 
                        bg-gray-900/90 py-10 px-20 rounded-[4rem] border-8 shadow-[0_0_100px_currentColor]">
                ${text}
            </div>
        `;
        document.body.appendChild(judgmentOverlay);
        setTimeout(() => judgmentOverlay.remove(), 3000);
        
        elTimerText.innerText = "WAITING";
    }
    else if (data.action === "RESET_STATE") {
        isPaused = false;
        clearInterval(typeInterval);
        elQuestionText.innerText = "WAITING FOR NEXT QUESTION...";
        elContainer.classList.remove("typing-cursor");
        elAnswererPopup.classList.add("hidden");
        elTimerText.innerText = "WAITING";
    }
}
