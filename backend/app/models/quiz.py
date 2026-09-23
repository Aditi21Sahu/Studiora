import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=True)
    title = Column(String, nullable=False)
    question_count = Column(Integer, default=5)
    questions_json = Column(Text, nullable=False)  # JSON-encoded array of questions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="quizzes")
    material = relationship("Material", back_populates="quizzes")
    note = relationship("Note", back_populates="quizzes")
    attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")
