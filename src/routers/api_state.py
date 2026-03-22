from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import asyncio
import discord

from ..database import get_db
from ..models import GameState, GameStateEnum, User, Question, ScoreLog
from ..websocket_manager import manager

router = APIRouter(prefix="/api/state", tags=["state"])

@router.post("/start_question/{question_id}")
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

@router.post("/pause")
async def api_pause_question(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.paused
    db.commit()
    
    await manager.broadcast_state({"action": "PAUSE_QUESTION"})
    return {"status": "ok"}

@router.post("/resume")
async def api_resume_question(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.asking
    db.commit()
    
    await manager.broadcast_state({"action": "RESUME_QUESTION"})
    return {"status": "ok"}

@router.post("/show_answer")
async def api_show_answer(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.showing_answer
    db.commit()
    
    await manager.broadcast_state({"action": "SHOW_ANSWER"})
    return {"status": "ok"}

@router.post("/judgement")
async def api_judgement(user_id: int, is_correct: bool, point_change: int, db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    user = db.query(User).filter(User.id == user_id).first()
    question = db.query(Question).filter(Question.id == state.current_question_id).first()
    
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
    
    from ..bot import bot
    audio_file = "audio/correct.mp3" if is_correct else "audio/incorrect.mp3"
    if hasattr(bot, 'play_audio_active_vc'):
        asyncio.create_task(bot.play_audio_active_vc(audio_file))
    
    return {"status": "ok", "point": point_change}

@router.post("/return_audience")
async def api_return_audience(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    
    if state and state.answering_user_id:
        user = db.query(User).filter(User.id == state.answering_user_id).first()
        if user:
            try:
                from ..bot import bot
                if bot.guilds:
                    guild = bot.guilds[0]
                    member = guild.get_member(int(user.discord_user_id))
                    if member and member.voice and getattr(member.voice.channel, "type", None) == discord.ChannelType.stage_voice:
                        asyncio.create_task(member.edit(suppress=True))
            except Exception as e:
                print(f"[API ERROR] Return audience failed: {e}")

    state.current_state = GameStateEnum.waiting
    state.answering_user_id = None
    db.commit()

    await manager.broadcast_state({"action": "RESET_STATE"})
    return {"status": "ok"}

@router.post("/reset")
async def api_state_reset(db: Session = Depends(get_db)):
    state = db.query(GameState).filter(GameState.id == 1).first()
    state.current_state = GameStateEnum.waiting
    state.answering_user_id = None
    state.current_question_id = None
    db.commit()

    await manager.broadcast_state({"action": "RESET_STATE"})
    return {"status": "ok"}
