import csv
import io
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from ..database import get_db
from ..models import Question, QuestionType, Choice

router = APIRouter(prefix="/api/questions", tags=["questions"])

class QuestionCreate(BaseModel):
    question_type: str = "descriptive"
    question_text: str
    point_value: int = 10
    media_url: Optional[str] = None
    sort_order: int = 0

@router.get("")
async def get_questions(db: Session = Depends(get_db)):
    questions = db.query(Question).order_by(Question.sort_order).all()
    return questions

@router.post("")
async def create_question(question: QuestionCreate, db: Session = Depends(get_db)):
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

@router.put("/{q_id}")
async def update_question(q_id: int, question: QuestionCreate, db: Session = Depends(get_db)):
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

@router.delete("/{q_id}")
async def delete_question(q_id: int, db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.id == q_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()
    return {"status": "deleted"}

@router.post("/import")
async def import_questions(file: UploadFile = File(...), db: Session = Depends(get_db)):
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
        db.flush() # ID取得のため
        
        # 選択肢の追加処理
        for i in range(1, 5):
            choice_text = row.get(f"choice_{i}")
            if choice_text and choice_text.strip():
                new_choice = Choice(
                    question_id=new_q.id,
                    choice_text=choice_text.strip(),
                    sort_order=i
                )
                db.add(new_choice)

        imported_count += 1
        
    db.commit()
    return {"status": "ok", "imported": imported_count}
