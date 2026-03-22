import asyncio
import json
import csv
import io
import discord # 追加
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from .database import engine, Base, get_db
from .models import GameState, GameStateEnum, User, Question, Choice, ScoreLog

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_state(self, state_data: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(state_data))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)

manager = ConnectionManager()

# ==== HTML ROUTES ====
@app.get("/admin", response_class=HTMLResponse)
async def get_admin(request: Request, db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.sort_order).all()
    users = db.query(User).order_by(User.total_score.desc()).all()
    state = db.query(GameState).filter(GameState.id == 1).first()
    if not state:
        state = GameState(current_state=GameStateEnum.waiting)
        db.add(state)
        db.commit()

    return templates.TemplateResponse("admin.html", {
        "request": request, 
        "questions": questions,
        "users": users,
        "state": state
    })

@app.get("/audience", response_class=HTMLResponse)
async def get_audience(request: Request):
    return templates.TemplateResponse("audience.html", {"request": request})

# ==== API ENDPOINTS: GAME STATE CONTROL ====

@app.post("/api/state/start_question/{question_id}")
async def api_start_question(question_id: int, db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    question = db.query(Question).filter(Question.id == question_id).first()
    
    state.current_state = GameStateEnum.asking
    state.current_question_id = question_id
    state.answering_user_id = None
    question.is_used = True
    db.commit()
    
    await manager.broadcast_state({
        "action": "START_QUESTION", 
        "question_id": question.id,
        "question_text": question.question_text,
        "media_url": question.media_url
    })
    return {"status": "ok"}

@app.post("/api/state/pause")
async def api_pause_question(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.paused
    db.commit()
    
    await manager.broadcast_state({"action": "PAUSE_QUESTION"})
    return {"status": "ok"}

@app.post("/api/state/resume")
async def api_resume_question(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.asking
    db.commit()
    
    await manager.broadcast_state({"action": "RESUME_QUESTION"})
    return {"status": "ok"}

@app.post("/api/state/show_answer")
async def api_show_answer(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.showing_answer
    db.commit()
    
    await manager.broadcast_state({"action": "SHOW_ANSWER"})
    return {"status": "ok"}

# カスタムポイントを受け取るように変更
@app.post("/api/state/judgement")
async def api_judgement(user_id: int, is_correct: bool, point_change: int, db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    user = db.query(User).filter(User.id == user_id).first()
    question = db.query(Question).filter(Question.id == state.current_question_id).first()
    
    # 画面から送られてきたカスタムポイントを加算/減算
    user.total_score += point_change
    log = ScoreLog(user_id=user.id, question_id=question.id, score_change=point_change, reason="Correct" if is_correct else "Incorrect")
    db.add(log)
    
    state.current_state = GameStateEnum.waiting
    state.answering_user_id = None
    db.commit()

    users = db.query(User).order_by(User.total_score.desc()).all()
    user_data = [{"id": u.id, "display_name": u.display_name, "score": u.total_score} for u in users]
    
    await manager.broadcast_state({
        "action": "JUDGEMENT",
        "is_correct": is_correct,
        "user_id": user_id,
        "ranking": user_data
    })
    
    from .bot import bot
    audio_file = "audio/correct.mp3" if is_correct else "audio/incorrect.mp3"
    if hasattr(bot, 'play_audio_active_vc'):
        asyncio.create_task(bot.play_audio_active_vc(audio_file))
    
    return {"status": "ok", "point": point_change}

# 【新規追加】回答者をオーディエンスに降ろすAPI
@app.post("/api/state/return_audience")
async def api_return_audience(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    
    if state and state.answering_user_id:
        user = db.query(User).filter(User.id == state.answering_user_id).first()
        if user:
            try:
                from .bot import bot
                if bot.guilds:
                    guild = bot.guilds[0]
                    member = guild.get_member(int(user.discord_user_id))
                    if member and member.voice and getattr(member.voice.channel, "type", None) == discord.ChannelType.stage_voice:
                        # ユーザーをオーディエンスに戻す
                        asyncio.create_task(member.edit(suppress=True))
            except Exception as e:
                print(f"[API ERROR] Return audience failed: {e}")

    state.current_state = GameStateEnum.waiting
    state.answering_user_id = None
    db.commit()

    await manager.broadcast_state({"action": "RESET_STATE"})
    return {"status": "ok"}

@app.post("/api/state/reset")
async def api_state_reset(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.waiting
    state.answering_user_id = None
    state.current_question_id = None
    db.commit()

    await manager.broadcast_state({"action": "RESET_STATE"})
    return {"status": "ok"}


# ==== QUESTION MANAGEMENT ROUTES ====

class QuestionCreate(BaseModel):
    question_type: str = "descriptive"
    question_text: str
    point_value: int = 10
    media_url: Optional[str] = None
    sort_order: int = 0

@app.get("/admin/questions", response_class=HTMLResponse)
async def get_admin_questions(request: Request, db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.sort_order).all()
    return templates.TemplateResponse("admin_questions.html", {"request": request, "questions": questions})

@app.get("/api/questions")
async def get_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.sort_order).all()
    return questions

@app.post("/api/questions")
async def create_question(question: QuestionCreate, db: Session = Depends(get_db)):
    from .models import QuestionType
    q_type = QuestionType.descriptive if question.question_type == "descriptive" else QuestionType.multiple_choice
    new_q = Question(
        question_type=q_type,
        question_text=question.question_text,
        point_value=question.point_value,
        media_url=question.media_url,
        sort_order=question.sort_order
    )
    db.add(new_q)
    db.commit()
    db.refresh(new_q)
    return new_q

@app.put("/api/questions/{q_id}")
async def update_question(q_id: int, question: QuestionCreate, db: Session = Depends(get_db)):
    from .models import QuestionType
    q = db.query(Question).filter(Question.id == q_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    
    q.question_type = QuestionType.descriptive if question.question_type == "descriptive" else QuestionType.multiple_choice
    q.question_text = question.question_text
    q.point_value = question.point_value
    q.media_url = question.media_url
    q.sort_order = question.sort_order
    
    db.commit()
    db.refresh(q)
    return q

@app.delete("/api/questions/{q_id}")
async def delete_question(q_id: int, db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == q_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
    return {"status": "deleted"}

@app.post("/api/questions/import")
async def import_questions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    from .models import QuestionType
    contents = await file.read()
    try:
        decoded = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = contents.decode("shift_jis")
        except:
            decoded = contents.decode("utf-8", errors="replace")
            
    reader = csv.DictReader(io.StringIO(decoded))
    
    imported_count = 0
    for row in reader:
        q_type_str = row.get("question_type", "descriptive")
        q_type = QuestionType.descriptive if q_type_str == "descriptive" else QuestionType.multiple_choice
        
        q_text = row.get("question_text", "").strip()
        if not q_text:
            continue
            
        try:
            point_val = int(row.get("point_value", 10))
        except ValueError:
            point_val = 10
            
        try:
            sort_ord = int(row.get("sort_order", 0))
        except ValueError:
            sort_ord = 0
            
        media_url = row.get("media_url") or None
        
        new_q = Question(
            question_type=q_type,
            question_text=q_text,
            point_value=point_val,
            sort_order=sort_ord,
            media_url=media_url
        )
        db.add(new_q)
        imported_count += 1
        
    db.commit()
    return {"status": "ok", "imported": imported_count}


# ==== WEBSOCKET ====
@app.websocket("/ws/audience")
async def websocket_audience(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        db = next(get_db())
        state = db.query(GameState).filter(GameState.id == 1).first()
        users = db.query(User).order_by(User.total_score.desc()).all()
        user_data = [{"id": u.id, "display_name": u.display_name, "score": u.total_score} for u in users]
        
        sync_data = {
            "action": "SYNC_STATE",
            "state": state.current_state.value if state else "waiting",
            "question_id": state.current_question_id if state else None,
            "answering_user_id": state.answering_user_id if state else None,
            "ranking": user_data
        }
        
        if state and state.current_question_id:
             q = db.query(Question).filter(Question.id == state.current_question_id).first()
             if q:
                 sync_data["question_text"] = q.question_text
                 sync_data["media_url"] = q.media_url
             
             if state.answering_user_id:
                 ans_usr = db.query(User).filter(User.id == state.answering_user_id).first()
                 sync_data["answering_user_name"] = ans_usr.display_name if ans_usr else ""
                 
        await websocket.send_text(json.dumps(sync_data))
        
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)