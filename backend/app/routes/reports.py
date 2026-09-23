import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.material import Material
from app.models.note import Note
from app.models.quiz import Quiz
from app.models.attempt import QuizAttempt
from app.models.activity import Activity
from app.schemas.report_schemas import DashboardStats, GrowthDataPoint, RecentActivityItem, ReportsSummary, TopicPerformance
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

def _format_time_ago(dt: datetime.datetime) -> str:
    """Format datetime into human-friendly relative time string."""
    now = datetime.datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min ago" if minutes == 1 else f"{minutes} mins ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    days = hours // 24
    if days < 7:
        return f"{days} day ago" if days == 1 else f"{days} days ago"
    return dt.strftime("%b %d, %Y")

@router.get("/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve real-time database counts for the 4 dashboard stat cards.
    Must return 0 for brand new users.
    """
    materials_count = db.query(Material).filter(Material.user_id == current_user.id).count()
    notes_count = db.query(Note).filter(Note.user_id == current_user.id).count()
    quizzes_count = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).count()

    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    if attempts:
        avg_score = round(sum(a.percentage for a in attempts) / len(attempts), 1)
        score_change = "+100%" if len(attempts) == 1 else f"{avg_score:.0f}% avg"
    else:
        avg_score = 0.0
        score_change = None

    return {
        "study_materials_count": materials_count,
        "notes_count": notes_count,
        "quizzes_count": quizzes_count,
        "average_score": avg_score,
        "score_change_label": score_change
    }

@router.get("/growth-chart", response_model=List[GrowthDataPoint])
def get_growth_chart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve quiz score progress data points over time.
    Returns empty list if no attempts have been recorded yet.
    """
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.asc())
        .all()
    )

    data_points = []
    for idx, att in enumerate(attempts, 1):
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        title = quiz.title if quiz else f"Quiz #{att.quiz_id}"
        data_points.append({
            "label": f"Attempt {idx}",
            "score": att.percentage,
            "quiz_title": title,
            "date": att.created_at.strftime("%b %d")
        })

    return data_points

@router.get("/recent-activity", response_model=List[RecentActivityItem])
def get_recent_activity(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve up to 10 recent activity logs for current user."""
    activities = (
        db.query(Activity)
        .filter(Activity.user_id == current_user.id)
        .order_by(Activity.created_at.desc())
        .limit(10)
        .all()
    )

    return [
        {
            "id": act.id,
            "activity_type": act.activity_type,
            "title": act.title,
            "description": act.description,
            "created_at": act.created_at,
            "time_ago": _format_time_ago(act.created_at)
        }
        for act in activities
    ]

@router.get("/summary", response_model=ReportsSummary)
def get_reports_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full analytics report for reports page."""
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.asc())
        .all()
    )

    total_attempts = len(attempts)
    total_questions = sum(a.total_questions for a in attempts)
    total_correct = sum(a.score for a in attempts)

    avg_score = round(sum(a.percentage for a in attempts) / total_attempts, 1) if total_attempts > 0 else 0.0
    highest_score = max((a.percentage for a in attempts), default=0.0)
    accuracy = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0.0

    growth_chart = [
        {
            "label": f"Quiz {idx}",
            "score": att.percentage,
            "quiz_title": f"Quiz #{att.quiz_id}",
            "date": att.created_at.strftime("%b %d")
        }
        for idx, att in enumerate(attempts, 1)
    ]

    # Topic performance calculation
    topic_map = {}
    for att in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        topic_name = quiz.title.replace(" Quiz", "") if quiz else "General Topics"
        if topic_name not in topic_map:
            topic_map[topic_name] = []
        topic_map[topic_name].append(att.percentage)

    topic_performances = [
        {
            "topic": topic,
            "score": round(sum(scores) / len(scores), 1),
            "attempts_count": len(scores)
        }
        for topic, scores in topic_map.items()
    ]

    # Recent attempts (newest first) for attempts history table
    recent_attempts_list = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
    recent_attempts = []
    for att in recent_attempts_list:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        title = quiz.title if quiz else f"Quiz #{att.quiz_id}"
        recent_attempts.append({
            "id": att.id,
            "quiz_id": att.quiz_id,
            "quiz_title": title,
            "score": att.score,
            "total_questions": att.total_questions,
            "percentage": att.percentage,
            "time_taken_seconds": att.time_taken_seconds,
            "created_at": att.created_at
        })

    return {
        "average_score": avg_score,
        "quizzes_completed": total_attempts,
        "total_attempts": total_attempts,
        "highest_score": highest_score,
        "questions_attempted": total_questions,
        "accuracy_percentage": accuracy,
        "growth_chart": growth_chart,
        "topic_performances": topic_performances,
        "recent_attempts": recent_attempts
    }
