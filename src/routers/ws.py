from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
import json

from ..database import get_db
from ..models import GameState, User, Question
from ..websocket_manager import manager

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/audience")
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
