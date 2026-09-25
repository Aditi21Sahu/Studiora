import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class TestPaper(Base):
    __tablename__ = "test_papers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    note_id = Column(Integer, ForeignKey("notes.id"), nullable=True)
    title = Column(String, nullable=False)
    total_questions = Column(Integer, default=20)
    total_marks = Column(Integer, default=25)
    duration_minutes = Column(Integer, default=30)
    sections_json = Column(Text, nullable=False)  # JSON holding sections A, B, C, D
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="test_papers")
    material = relationship("Material", back_populates="test_papers")
    note = relationship("Note", back_populates="test_papers")
    attempts = relationship("TestAttempt", back_populates="test_paper", cascade="all, delete-orphan")
