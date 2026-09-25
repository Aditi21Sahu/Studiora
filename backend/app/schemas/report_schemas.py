from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class DashboardStats(BaseModel):
    study_materials_count: int
    notes_count: int
    quizzes_count: int
    average_score: float
    score_change_label: Optional[str] = None

class GrowthDataPoint(BaseModel):
    label: str  # e.g. "Attempt 1", "Week 1", or date
    score: float
    quiz_title: Optional[str] = None
    date: str

class RecentActivityItem(BaseModel):
    id: int
    activity_type: str
    title: str
    description: Optional[str] = None
    created_at: datetime
    time_ago: str

class TopicPerformance(BaseModel):
    topic: str
    score: float
    attempts_count: int

class RecentAttemptItem(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    score: float
    total_questions: int
    percentage: float
    time_taken_seconds: int
    created_at: datetime
    attempt_type: Optional[str] = "quiz"

class ReportsSummary(BaseModel):
    average_score: float
    quizzes_completed: int
    total_attempts: int
    highest_score: float
    questions_attempted: int
    accuracy_percentage: float
    growth_chart: List[GrowthDataPoint]
    topic_performances: List[TopicPerformance]
    recent_attempts: List[RecentAttemptItem]
