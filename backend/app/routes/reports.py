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
from app.models.test_paper import TestPaper
from app.models.test_attempt import TestAttempt
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
    quiz_attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    test_attempts = db.query(TestAttempt).filter(
        TestAttempt.user_id == current_user.id,
        TestAttempt.status.in_(["completed", "auto_submitted"])
    ).all()

    total_assessments_count = len(quiz_attempts) + len(test_attempts)
    all_percentages = [a.percentage for a in quiz_attempts] + [a.percentage for a in test_attempts]

    if all_percentages:
        avg_score = round(sum(all_percentages) / len(all_percentages), 1)
        score_change = "+100%" if len(all_percentages) == 1 else f"{avg_score:.0f}% avg"
    else:
        avg_score = 0.0
        score_change = None

    return {
        "study_materials_count": materials_count,
        "notes_count": notes_count,
        "quizzes_count": total_assessments_count,
        "average_score": avg_score,
        "score_change_label": score_change
    }

@router.get("/growth-chart", response_model=List[GrowthDataPoint])
def get_growth_chart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve score progress data points over time across quizzes and test papers.
    Returns empty list if no attempts have been recorded yet.
    """
    quiz_attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .all()
    )
    test_attempts = (
        db.query(TestAttempt)
        .filter(TestAttempt.user_id == current_user.id, TestAttempt.status.in_(["completed", "auto_submitted"]))
        .all()
    )

    combined_timeline = []
    for att in quiz_attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        title = quiz.title if quiz else f"Quiz #{att.quiz_id}"
        combined_timeline.append({
            "created_at": att.created_at,
            "score": att.percentage,
            "title": title
        })

    for att in test_attempts:
        paper = db.query(TestPaper).filter(TestPaper.id == att.test_paper_id).first()
        title = paper.title if paper else f"Test #{att.test_paper_id}"
        combined_timeline.append({
            "created_at": att.created_at,
            "score": att.percentage,
            "title": title
        })

    combined_timeline.sort(key=lambda x: x["created_at"])

    data_points = []
    for idx, item in enumerate(combined_timeline, 1):
        data_points.append({
            "label": f"Attempt {idx}",
            "score": item["score"],
            "quiz_title": item["title"],
            "date": item["created_at"].strftime("%b %d")
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
    """Retrieve full analytics report for reports page combining quizzes and test papers."""
    quiz_attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.user_id == current_user.id)
        .all()
    )
    test_attempts = (
        db.query(TestAttempt)
        .filter(TestAttempt.user_id == current_user.id, TestAttempt.status.in_(["completed", "auto_submitted"]))
        .all()
    )

    total_attempts = len(quiz_attempts) + len(test_attempts)
    total_questions = sum(a.total_questions for a in quiz_attempts) + sum(20 for _ in test_attempts)
    total_marks_possible = sum(a.total_questions for a in quiz_attempts) + sum(25 for _ in test_attempts)
    total_marks_obtained = sum(a.score for a in quiz_attempts) + sum(a.score for a in test_attempts)

    all_percentages = [a.percentage for a in quiz_attempts] + [a.percentage for a in test_attempts]
    avg_score = round(sum(all_percentages) / total_attempts, 1) if total_attempts > 0 else 0.0
    highest_score = max(all_percentages, default=0.0)
    accuracy = round((total_marks_obtained / total_marks_possible) * 100, 1) if total_marks_possible > 0 else 0.0

    # Growth chart timeline
    combined_timeline = []
    for att in quiz_attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        title = quiz.title if quiz else f"Quiz #{att.quiz_id}"
        combined_timeline.append({
            "created_at": att.created_at,
            "score": att.percentage,
            "title": title
        })
    for att in test_attempts:
        paper = db.query(TestPaper).filter(TestPaper.id == att.test_paper_id).first()
        title = paper.title if paper else f"Test #{att.test_paper_id}"
        combined_timeline.append({
            "created_at": att.created_at,
            "score": att.percentage,
            "title": title
        })
    combined_timeline.sort(key=lambda x: x["created_at"])

    growth_chart = [
        {
            "label": f"Attempt {idx}",
            "score": item["score"],
            "quiz_title": item["title"],
            "date": item["created_at"].strftime("%b %d")
        }
        for idx, item in enumerate(combined_timeline, 1)
    ]

    # Topic performance calculation
    topic_map = {}
    for att in quiz_attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        topic_name = quiz.title.replace(" Quiz", "") if quiz else "General Topics"
        if topic_name not in topic_map:
            topic_map[topic_name] = []
        topic_map[topic_name].append(att.percentage)

    for att in test_attempts:
        paper = db.query(TestPaper).filter(TestPaper.id == att.test_paper_id).first()
        topic_name = paper.title.replace(" Test", "").replace(" Test Paper", "") if paper else "Test Papers"
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

    # Recent attempts (combined, newest first) for attempts history table
    combined_attempts = []
    for att in quiz_attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        title = quiz.title if quiz else f"Quiz #{att.quiz_id}"
        combined_attempts.append({
            "id": att.id,
            "quiz_id": att.quiz_id,
            "quiz_title": title,
            "score": float(att.score),
            "total_questions": att.total_questions,
            "percentage": att.percentage,
            "time_taken_seconds": att.time_taken_seconds,
            "created_at": att.created_at,
            "attempt_type": "quiz"
        })

    for att in test_attempts:
        paper = db.query(TestPaper).filter(TestPaper.id == att.test_paper_id).first()
        title = paper.title if paper else f"Test #{att.test_paper_id}"
        combined_attempts.append({
            "id": att.id,
            "quiz_id": att.test_paper_id,
            "quiz_title": title,
            "score": float(att.score),
            "total_questions": 25,  # 25 marks
            "percentage": att.percentage,
            "time_taken_seconds": att.time_taken_seconds,
            "created_at": att.created_at,
            "attempt_type": "test_paper"
        })

    combined_attempts.sort(key=lambda x: x["created_at"], reverse=True)
    recent_attempts = combined_attempts

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
