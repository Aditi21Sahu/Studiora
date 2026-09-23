import os
import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.models.material import Material
from app.models.activity import Activity
from app.schemas.material_schemas import MaterialResponse, MaterialDetailResponse, MaterialUrlRequest
from app.services.auth_service import get_current_user
from app.services.document_service import document_service
from app.services.video_service import video_service
from app.services.youtube_service import youtube_service
from app.services.notes_service import notes_service
from app.services.quiz_service import quiz_service

router = APIRouter(prefix="/materials", tags=["Study Materials"])
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".txt": "txt",
    ".md": "txt",
    ".mp4": "video",
    ".mkv": "video",
    ".mov": "video",
    ".webm": "video",
    ".avi": "video"
}

@router.post("/upload", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def upload_material(
    file: UploadFile = File(...),
    custom_title: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload PDF, DOCX, or MP4 video study material."""
    filename = file.filename or "uploaded_material"
    _, ext = os.path.splitext(filename.lower())

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Please upload a PDF, Word (DOCX), or Video (MP4) file."
        )

    file_type = ALLOWED_EXTENSIONS[ext]
    safe_filename = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
    dest_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    # Save file contents
    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    title = custom_title.strip() if custom_title and custom_title.strip() else os.path.splitext(filename)[0].replace("_", " ").title()
    file_size_str = f"{len(content) / (1024 * 1024):.1f} MB"

    # Extract text content according to file type
    text_content = ""
    status_str = "completed"
    try:
        if file_type == "pdf":
            text_content, size_summary = document_service.extract_text_from_pdf(dest_path)
            file_size_str = f"{file_size_str} &bull; {size_summary}"
        elif file_type == "docx":
            text_content, size_summary = document_service.extract_text_from_docx(dest_path)
            file_size_str = f"{file_size_str} &bull; {size_summary}"
        elif file_type == "txt":
            with open(dest_path, "r", encoding="utf-8", errors="ignore") as tf:
                raw = tf.read()
            text_content = document_service.clean_text(raw)
            lines_count = len([line for line in text_content.splitlines() if line.strip()])
            file_size_str = f"{file_size_str} &bull; {lines_count} lines"
        elif file_type == "video":
            # Video speech-to-text processing
            text_content, size_summary = video_service.extract_audio_and_transcribe(dest_path)
            file_size_str = size_summary
    except Exception as e:
        logger.error("Processing failed for %s: %s", filename, str(e))
        status_str = "failed"
        text_content = str(e)

    # Create Material in database
    material = Material(
        user_id=current_user.id,
        title=title,
        file_path=dest_path,
        file_type=file_type,
        source_type="upload",
        file_size=file_size_str,
        status=status_str,
        text_content=text_content
    )
    db.add(material)
    db.flush()

    # Log Activity
    activity = Activity(
        user_id=current_user.id,
        activity_type="material_upload",
        title="Study material uploaded",
        description=f"Uploaded '{title}' ({file_type.upper()})"
    )
    db.add(activity)

    db.commit()
    db.refresh(material)

    # Automatically generate structured notes and starting quiz if valid text content exists
    if text_content and status_str == "completed":
        try:
            saved_note = notes_service.generate_notes_from_material(db, material.id, current_user.id)
            try:
                quiz_service.generate_quiz(db, current_user.id, material_id=material.id, note_id=saved_note.id if saved_note else None, question_count=5)
            except Exception as qe:
                logger.warning("Auto quiz generation for uploaded material %s failed: %s", material.id, str(qe))
        except Exception as ne:
            logger.warning("Auto note generation for uploaded material %s failed: %s", material.id, str(ne))

    return material

@router.post("/url", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
def add_url_material(
    req: MaterialUrlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process YouTube or online learning URL."""
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL cannot be empty")

    is_youtube = ("youtube.com" in url.lower() or "youtu.be" in url.lower())
    title = req.title.strip() if req.title and req.title.strip() else ("YouTube Video Lecture" if is_youtube else "Online Learning Resource")

    text_content = ""
    status_str = "completed"
    file_type = "video" if is_youtube else "url"
    source_type = "youtube" if is_youtube else "url"
    size_str = "Online URL"

    if is_youtube:
        try:
            text_content, yt_title, duration_str = youtube_service.get_youtube_content(url)
            size_str = duration_str
            if not req.title or not req.title.strip():
                title = yt_title
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to process YouTube video automatically: {str(e)}"
            )
    else:
        # Online course URL check
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This online course or page cannot be accessed automatically due to authentication/access controls. Please upload the PDF, Word document, or transcript directly."
        )

    material = Material(
        user_id=current_user.id,
        title=title,
        file_path=url,
        file_type=file_type,
        source_type=source_type,
        file_size=size_str,
        status=status_str,
        text_content=text_content
    )
    db.add(material)
    db.flush()

    activity = Activity(
        user_id=current_user.id,
        activity_type="material_upload",
        title="Online content added",
        description=f"Processed video transcript for '{title}'"
    )
    db.add(activity)

    db.commit()
    db.refresh(material)

    # Automatically generate structured notes and starting quiz if valid text content exists
    if text_content and status_str == "completed":
        try:
            saved_note = notes_service.generate_notes_from_material(db, material.id, current_user.id)
            try:
                quiz_service.generate_quiz(db, current_user.id, material_id=material.id, note_id=saved_note.id if saved_note else None, question_count=5)
            except Exception as qe:
                logger.warning("Auto quiz generation for URL material %s failed: %s", material.id, str(qe))
        except Exception as ne:
            logger.warning("Auto note generation for URL material %s failed: %s", material.id, str(ne))

    return material

@router.get("/", response_model=List[MaterialResponse])
def get_materials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all study materials for the authenticated student."""
    return db.query(Material).filter(Material.user_id == current_user.id).order_by(Material.created_at.desc()).all()

@router.get("/{material_id}", response_model=MaterialDetailResponse)
def get_material_detail(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single study material with content."""
    mat = db.query(Material).filter(Material.id == material_id, Material.user_id == current_user.id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study material not found")
    return mat

@router.delete("/{material_id}")
def delete_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete study material and associated stored file."""
    mat = db.query(Material).filter(Material.id == material_id, Material.user_id == current_user.id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study material not found")

    # Clean up local file if stored
    if mat.file_path and os.path.exists(mat.file_path) and mat.source_type == "upload":
        try:
            os.remove(mat.file_path)
        except Exception:
            pass

    db.delete(mat)
    db.commit()
    return {"status": "success", "message": "Study material deleted successfully."}
