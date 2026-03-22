from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import GameState, GameStateEnum, User, Question

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/admin", response_class=HTMLResponse)
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

@router.get("/audience", response_class=HTMLResponse)
async def get_audience(request: Request):
    return templates.TemplateResponse("audience.html", {"request": request})

@router.get("/admin/questions", response_class=HTMLResponse)
async def get_admin_questions(request: Request, db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.sort_order).all()
    return templates.TemplateResponse("admin_questions.html", {"request": request, "questions": questions})
