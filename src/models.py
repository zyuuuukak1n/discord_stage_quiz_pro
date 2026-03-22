from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Enum
from sqlalchemy.orm import relationship
import enum
import datetime
from .database import Base

class QuestionType(enum.Enum):
    multiple_choice = "multiple_choice"
    descriptive = "descriptive"

class GameStateEnum(enum.Enum):
    waiting = "waiting"
    asking = "asking"
    answering = "answering"
    showing_answer = "showing_answer"
    paused = "paused"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    discord_user_id = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    total_score = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    score_logs = relationship("ScoreLog", back_populates="user")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    question_type = Column(Enum(QuestionType), nullable=False, default=QuestionType.descriptive)
    question_text = Column(Text, nullable=False)
    point_value = Column(Integer, default=10)
    media_url = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    is_used = Column(Boolean, default=False)

    choices = relationship("Choice", back_populates="question")
    score_logs = relationship("ScoreLog", back_populates="question")

class Choice(Base):
    __tablename__ = "choices"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    choice_text = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    question = relationship("Question", back_populates="choices")

class GameState(Base):
    __tablename__ = "game_state"
    id = Column(Integer, primary_key=True, index=True) # Always 1
    current_state = Column(Enum(GameStateEnum), default=GameStateEnum.waiting)
    current_question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    answering_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    current_question = relationship("Question")
    answering_user = relationship("User")

class ScoreLog(Base):
    __tablename__ = "score_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=True)
    score_change = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="score_logs")
    question = relationship("Question", back_populates="score_logs")
