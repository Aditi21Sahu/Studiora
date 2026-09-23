import json
import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.note import Note
from app.models.material import Material
from app.schemas.note_schemas import NoteResponse
from app.services.auth_service import get_current_user
from app.services.notes_service import notes_service
from app.utils.pdf_generator import generate_notes_pdf, generate_notes_txt

router = APIRouter(prefix="/notes", tags=["Study Notes"])

def _format_note_response(note: Note, db: Session) -> dict:
    source_title = None
    source_type = None
    if note.material_id:
        mat = db.query(Material).filter(Material.id == note.material_id).first()
        if mat:
            source_title = mat.title
            source_type = mat.file_type

    return {
        "id": note.id,
        "user_id": note.user_id,
        "material_id": note.material_id,
        "title": note.title,
        "summary": note.summary,
        "key_points": json.loads(note.key_points) if note.key_points else [],
        "sections": json.loads(note.sections) if note.sections else [],
        "important_terms": json.loads(note.important_terms) if note.important_terms else [],
        "revision_points": json.loads(note.revision_points) if note.revision_points else [],
        "source_title": source_title,
        "source_type": source_type,
        "created_at": note.created_at
    }

@router.post("/generate/{material_id}", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def generate_notes_endpoint(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate structured study notes from an uploaded study material."""
    note = notes_service.generate_notes_from_material(db, material_id, current_user.id)
    return _format_note_response(note, db)

@router.get("/", response_model=List[NoteResponse])
def get_all_notes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all study notes saved for the user."""
    notes = notes_service.get_user_notes(db, current_user.id)
    return [_format_note_response(n, db) for n in notes]

@router.get("/{note_id}", response_model=NoteResponse)
def get_note_detail(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single study note with full educational sections and definitions."""
    note = notes_service.get_note_by_id(db, note_id, current_user.id)
    return _format_note_response(note, db)

@router.get("/{note_id}/download/{file_format}")
def download_note(
    note_id: int,
    file_format: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download study notes as PDF or TXT."""
    note = notes_service.get_note_by_id(db, note_id, current_user.id)
    formatted = _format_note_response(note, db)

    # Clean filename
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', note.title.lower().strip())
    safe_name = re.sub(r'_+', '_', safe_name).strip('_') or "study_notes"

    fmt = file_format.lower().strip()
    if fmt == "pdf":
        pdf_stream = generate_notes_pdf(formatted)
        return StreamingResponse(
            pdf_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={safe_name}_notes.pdf"}
        )
    elif fmt == "txt":
        txt_content = generate_notes_txt(formatted)
        return PlainTextResponse(
            txt_content,
            headers={"Content-Disposition": f"attachment; filename={safe_name}_notes.txt"}
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Only 'pdf' and 'txt' are supported for download."
        )

@router.delete("/{note_id}")
def delete_note_endpoint(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a note."""
    notes_service.delete_note(db, note_id, current_user.id)
    return {"status": "success", "message": "Note deleted successfully."}
