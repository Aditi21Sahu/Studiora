import json
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.material import Material
from app.models.note import Note
from app.models.activity import Activity
from app.ai.groq_service import groq_service

logger = logging.getLogger(__name__)

class NotesService:
    """Service handling notes generation from study materials, retrieval, and formatting."""

    @staticmethod
    def generate_notes_from_material(db: Session, material_id: int, user_id: int) -> Note:
        material = db.query(Material).filter(Material.id == material_id, Material.user_id == user_id).first()
        if not material:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study material not found")

        # Return existing note if already generated for this material
        existing_note = db.query(Note).filter(Note.material_id == material_id, Note.user_id == user_id).first()
        if existing_note:
            return existing_note

        if material.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=material.text_content or "Study material processing failed"
            )

        if not material.text_content or not material.text_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Study material does not contain any readable text content"
            )

        # Update status to processing
        material.status = "processing"
        db.commit()

        try:
            # Generate structured notes via Groq AI
            notes_data = groq_service.generate_notes(
                text=material.text_content,
                title_hint=material.title
            )

            # Create Note model
            new_note = Note(
                user_id=user_id,
                material_id=material.id,
                title=notes_data.get("title", f"{material.title} Notes"),
                summary=notes_data.get("summary", ""),
                key_points=json.dumps(notes_data.get("key_points", [])),
                sections=json.dumps(notes_data.get("sections", [])),
                important_terms=json.dumps(notes_data.get("important_terms", [])),
                revision_points=json.dumps(notes_data.get("revision_points", []))
            )
            db.add(new_note)

            # Update material status
            material.status = "completed"

            # Record activity
            activity = Activity(
                user_id=user_id,
                activity_type="notes_generated",
                title="Notes generated",
                description=f"Generated structured notes for '{material.title}'"
            )
            db.add(activity)

            db.commit()
            db.refresh(new_note)
            return new_note

        except Exception as e:
            material.status = "failed"
            db.commit()
            logger.error("Failed to generate notes for material %s: %s", material_id, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate study notes: {str(e)}"
            )

    @staticmethod
    def get_user_notes(db: Session, user_id: int) -> List[Note]:
        return db.query(Note).filter(Note.user_id == user_id).order_by(Note.created_at.desc()).all()

    @staticmethod
    def get_note_by_id(db: Session, note_id: int, user_id: int) -> Note:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study notes not found")
        return note

    @staticmethod
    def delete_note(db: Session, note_id: int, user_id: int) -> bool:
        note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
        if not note:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study notes not found")
        db.delete(note)
        db.commit()
        return True

notes_service = NotesService()
