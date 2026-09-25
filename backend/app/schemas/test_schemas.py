import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class TestGenerateRequest(BaseModel):
    material_id: Optional[int] = None
    note_id: Optional[int] = None
    title: Optional[str] = None

class TestQuestionMCQStudent(BaseModel):
    id: int
    question: str
    options: List[Dict[str, str]]
    marks: int = 1

class TestQuestionTFStudent(BaseModel):
    id: int
    question: str
    marks: int = 1

class TestQuestionFillStudent(BaseModel):
    id: int
    question: str
    marks: int = 1

class TestQuestionQAStudent(BaseModel):
    id: int
    question: str
    marks: int = 2

class TestSectionsStudent(BaseModel):
    section_a: List[TestQuestionMCQStudent]
    section_b: List[TestQuestionTFStudent]
    section_c: List[TestQuestionFillStudent]
    section_d: List[TestQuestionQAStudent]

class TestPaperStudentResponse(BaseModel):
    id: int
    title: str
    total_questions: int = 20
    total_marks: int = 25
    duration_minutes: int = 30
    sections: TestSectionsStudent
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True

class TestPaperListItem(BaseModel):
    id: int
    title: str
    total_questions: int = 20
    total_marks: int = 25
    duration_minutes: int = 30
    attempts_count: int = 0
    best_score: Optional[float] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class TestStartResponse(BaseModel):
    attempt_id: int
    test_paper_id: int
    started_at: datetime.datetime
    ends_at: datetime.datetime
    duration_seconds: int = 1800
    remaining_seconds: int
    status: str
    saved_answers: Dict[str, str] = {}

class TestSaveDraftRequest(BaseModel):
    answers: Dict[str, str]

class TestSubmitRequest(BaseModel):
    answers: Dict[str, str]
    submission_type: Optional[str] = "manual"  # manual or automatic

class QuestionMistakeReview(BaseModel):
    question_id: int
    section: str
    question: str
    student_answer: str
    correct_answer: str
    marks_obtained: float
    max_marks: int
    is_correct: bool
    feedback: str
    missing_concepts: Optional[List[str]] = []
    ai_evaluation: Optional[str] = None
    important_keywords: Optional[List[str]] = []

class TestSectionScores(BaseModel):
    section_a: float = 0.0
    section_b: float = 0.0
    section_c: float = 0.0
    section_d: float = 0.0
    total: float = 0.0

class TestAttemptResultResponse(BaseModel):
    id: int
    test_paper_id: int
    test_title: str
    score: float
    max_marks: int = 25
    percentage: float
    time_taken_seconds: int
    started_at: datetime.datetime
    submitted_at: datetime.datetime
    submission_type: str
    submission_message: str
    section_scores: TestSectionScores
    mistakes_review: List[QuestionMistakeReview]
    all_questions_review: List[QuestionMistakeReview]

    class Config:
        from_attributes = True
