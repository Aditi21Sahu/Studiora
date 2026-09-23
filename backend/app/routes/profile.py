from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.material import Material
from app.models.note import Note
from app.models.attempt import QuizAttempt
from app.schemas.profile_schemas import ProfileResponse, ProfileUpdate, PasswordChange
from app.services.auth_service import get_current_user, get_password_hash, verify_password

router = APIRouter(prefix="/profile", tags=["Profile & Settings"])

@router.get("/", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get profile information and learning statistics."""
    mat_count = db.query(Material).filter(Material.user_id == current_user.id).count()
    note_count = db.query(Note).filter(Note.user_id == current_user.id).count()
    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    
    avg_score = round(sum(a.percentage for a in attempts) / len(attempts), 1) if attempts else 0.0

    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "created_at": current_user.created_at,
        "materials_uploaded": mat_count,
        "notes_generated": note_count,
        "quizzes_completed": len(attempts),
        "average_score": avg_score
    }

@router.put("/update", response_model=ProfileResponse)
def update_profile(
    req: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update profile full name or email."""
    if req.full_name:
        current_user.full_name = req.full_name.strip()
    if req.email:
        new_email = req.email.lower().strip()
        if new_email != current_user.email:
            existing = db.query(User).filter(User.email == new_email).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already in use by another account.")
            current_user.email = new_email

    db.commit()
    db.refresh(current_user)
    return get_profile(current_user=current_user, db=db)

@router.post("/change-password")
def change_password(
    req: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change student account password."""
    if not verify_password(req.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password.")

    if len(req.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must be at least 6 characters long.")

    current_user.password_hash = get_password_hash(req.new_password)
    db.commit()
    return {"status": "success", "message": "Password updated successfully."}
