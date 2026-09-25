import datetime
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    test_paper_id = Column(Integer, ForeignKey("test_papers.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    ends_at = Column(DateTime, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(String, default="in_progress")  # in_progress, completed, auto_submitted
    submission_type = Column(String, nullable=True)  # manual, automatic
    score = Column(Float, default=0.0)
    max_marks = Column(Integer, default=25)
    percentage = Column(Float, default=0.0)
    section_scores_json = Column(Text, nullable=True)  # JSON {section_a: 4.0, section_b: 5.0, ...}
    time_taken_seconds = Column(Integer, default=0)
    answers_json = Column(Text, default="{}")  # JSON-encoded student answers
    evaluation_json = Column(Text, nullable=True)  # Detailed AI grading, feedback, mistakes
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="test_attempts")
    test_paper = relationship("TestPaper", back_populates="attempts")
