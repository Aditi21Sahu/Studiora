import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.test_paper import TestPaper
from app.models.test_attempt import TestAttempt
from app.schemas.test_schemas import (
    TestGenerateRequest, TestPaperStudentResponse, TestPaperListItem,
    TestStartResponse, TestSaveDraftRequest, TestSubmitRequest,
    TestAttemptResultResponse
)
from app.services.auth_service import get_current_user
from app.services.test_service import test_service

router = APIRouter(prefix="/tests", tags=["Test Papers"])
logger = logging.getLogger(__name__)

@router.post("/generate", response_model=TestPaperStudentResponse, status_code=status.HTTP_201_CREATED)
def generate_test_endpoint(
    req: TestGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a 20-question, 25-mark timed test paper from selected study material or note."""
    paper = test_service.generate_test_paper(
        db=db,
        user_id=current_user.id,
        material_id=req.material_id,
        note_id=req.note_id,
        title=req.title
    )
    return test_service.get_test_paper_student_view(db, paper.id, current_user.id)

@router.get("/", response_model=List[TestPaperListItem])
def get_user_test_papers_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all test papers generated for the current user."""
    return test_service.get_user_test_papers(db, current_user.id)

@router.get("/attempts/active", response_model=Optional[TestStartResponse])
def get_active_test_attempt_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if the user has an in-progress test attempt that can be resumed."""
    import datetime, json
    now = datetime.datetime.utcnow()
    active_att = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.user_id == current_user.id,
            TestAttempt.status == "in_progress",
            TestAttempt.ends_at > now
        )
        .order_by(TestAttempt.started_at.desc())
        .first()
    )
    if not active_att:
        return None

    remaining = max(0, int((active_att.ends_at - now).total_seconds()))
    saved_answers = {}
    try:
        saved_answers = json.loads(active_att.answers_json or "{}")
    except Exception:
        pass

    return {
        "attempt_id": active_att.id,
        "test_paper_id": active_att.test_paper_id,
        "started_at": active_att.started_at,
        "ends_at": active_att.ends_at,
        "duration_seconds": 1800,
        "remaining_seconds": remaining,
        "status": "in_progress",
        "saved_answers": saved_answers
    }

@router.get("/{test_id}", response_model=TestPaperStudentResponse)
def get_test_paper_endpoint(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve student-safe view of the test paper (answers and marking keys hidden)."""
    return test_service.get_test_paper_student_view(db, test_id, current_user.id)

@router.post("/{test_id}/start", response_model=TestStartResponse)
def start_test_attempt_endpoint(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start or resume a 30-minute timed test attempt with server-side persistent timer."""
    return test_service.start_test_attempt(db, test_id, current_user.id)

@router.post("/attempts/{attempt_id}/save-draft")
def save_draft_endpoint(
    attempt_id: int,
    req: TestSaveDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save in-progress test answers so refreshing the page never loses user work."""
    return test_service.save_test_draft(db, attempt_id, current_user.id, req.answers)

@router.post("/attempts/{attempt_id}/submit", response_model=TestAttemptResultResponse)
def submit_test_attempt_endpoint(
    attempt_id: int,
    req: TestSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit complete 25-mark test attempt, evaluate answers with AI, and return scores & mistakes."""
    return test_service.submit_test_attempt(
        db=db,
        attempt_id=attempt_id,
        user_id=current_user.id,
        answers=req.answers,
        submission_type=req.submission_type or "manual"
    )

@router.get("/attempts/{attempt_id}/result", response_model=TestAttemptResultResponse)
def get_test_attempt_result_endpoint(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve result breakdown and detailed mistake analysis for a completed test attempt."""
    return test_service.get_attempt_result(db, attempt_id, current_user.id)

@router.delete("/{test_id}")
def delete_test_paper_endpoint(
    test_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a test paper."""
    paper = db.query(TestPaper).filter(TestPaper.id == test_id, TestPaper.user_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test paper not found.")
    db.delete(paper)
    db.commit()
    return {"message": "Test paper deleted successfully."}
