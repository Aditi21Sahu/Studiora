import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    file_type = Column(String, nullable=False)  # 'pdf', 'docx', 'video', 'url'
    source_type = Column(String, default="upload")  # 'upload', 'youtube', 'url'
    file_size = Column(String, nullable=True)  # e.g., '2.4 MB' or '12 pages'
    status = Column(String, default="uploaded")  # 'uploaded', 'processing', 'completed', 'failed'
    text_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="materials")
    notes = relationship("Note", back_populates="material", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="material", cascade="all, delete-orphan")
    test_papers = relationship("TestPaper", back_populates="material", cascade="all, delete-orphan")
