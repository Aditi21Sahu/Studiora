import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    key_points = Column(Text, nullable=True)  # JSON-encoded list of key takeaways
    sections = Column(Text, nullable=True)  # JSON-encoded list of {title, content, subheadings, examples}
    important_terms = Column(Text, nullable=True)  # JSON-encoded list of {term, definition}
    revision_points = Column(Text, nullable=True)  # JSON-encoded list of revision bullet points
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notes")
    material = relationship("Material", back_populates="notes")
    quizzes = relationship("Quiz", back_populates="note")
