import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.quiz import Quiz
from app.schemas.quiz_schemas import (
    QuizGenerateRequest, QuizResponse, SingleAnswerCheckRequest,
    SingleAnswerCheckResponse, QuizSubmitRequest, QuizAttemptResponse
)
from app.services.auth_service import get_current_user
from app.services.quiz_service import quiz_service

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])
logger = logging.getLogger(__name__)

@router.post("/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def generate_quiz_endpoint(
    req: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a 5, 10, or 15 question interactive quiz from material or notes."""
    quiz = quiz_service.generate_quiz(
        db=db,
        user_id=current_user.id,
        material_id=req.material_id,
        note_id=req.note_id,
        question_count=req.question_count
    )
    return quiz_service.get_quiz_by_id(db, quiz.id, current_user.id)

@router.get("/", response_model=List[QuizResponse])
def get_all_quizzes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all quizzes generated for the current user."""
    return quiz_service.get_user_quizzes(db, current_user.id)

@router.get("/{quiz_id}", response_model=QuizResponse)
def get_quiz_detail(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get quiz with questions for taking the test."""
    return quiz_service.get_quiz_by_id(db, quiz_id, current_user.id)

@router.post("/check-answer", response_model=SingleAnswerCheckResponse)
def check_single_answer_endpoint(
    req: SingleAnswerCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check a single question's answer interactively during quiz attempt."""
    return quiz_service.check_single_answer(
        db=db,
        quiz_id=req.quiz_id,
        question_id=req.question_id,
        selected_option=req.selected_option,
        user_id=current_user.id
    )

@router.post("/{quiz_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz_attempt_endpoint(
    quiz_id: int,
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit complete quiz attempt, save score to database, and return results."""
    attempt = quiz_service.submit_attempt(
        db=db,
        quiz_id=quiz_id,
        user_id=current_user.id,
        time_taken_seconds=req.time_taken_seconds,
        answers=req.answers
    )
    return quiz_service.get_attempt_by_id(db, attempt.id, current_user.id)

@router.get("/attempts/{attempt_id}", response_model=QuizAttemptResponse)
def get_attempt_detail(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a completed quiz attempt, including mistakes review."""
    return quiz_service.get_attempt_by_id(db, attempt_id, current_user.id)

@router.delete("/{quiz_id}")
def delete_quiz_endpoint(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a quiz."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == current_user.id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    db.delete(quiz)
    db.commit()
    return {"status": "success", "message": "Quiz deleted successfully."}
