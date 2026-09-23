from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QuizGenerateRequest(BaseModel):
    material_id: Optional[int] = None
    note_id: Optional[int] = None
    question_count: int = 5  # 5, 10, or 15

class QuizOption(BaseModel):
    id: str  # "A", "B", "C", "D"
    text: str

class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[Dict[str, str]]  # [{"id": "A", "text": "..."}]
    correct_answer: str  # "A", "B", "C", or "D"
    explanation: str

class QuizQuestionPublic(BaseModel):
    id: int
    question: str
    options: List[Dict[str, str]]

class QuizResponse(BaseModel):
    id: int
    user_id: int
    material_id: Optional[int] = None
    note_id: Optional[int] = None
    title: str
    question_count: int
    questions: List[QuizQuestionPublic]
    created_at: datetime
    best_score: Optional[float] = None
    total_attempts: Optional[int] = 0

    class Config:
        from_attributes = True

class SingleAnswerCheckRequest(BaseModel):
    quiz_id: int
    question_id: int
    selected_option: str

class SingleAnswerCheckResponse(BaseModel):
    question_id: int
    is_correct: bool
    correct_option: str       # e.g. "C"
    correct_text: str         # e.g. "2ndPlace"
    correct_answer: str       # e.g. "C. 2ndPlace"
    selected_option: str      # e.g. "B"
    selected_text: str        # e.g. "_name"
    user_answer: str          # e.g. "B. _name"
    explanation: str

class QuizSubmitAnswerItem(BaseModel):
    question_id: int
    selected_option: str

class QuizSubmitRequest(BaseModel):
    time_taken_seconds: int = 0
    answers: List[QuizSubmitAnswerItem]

class ReviewMistakeItem(BaseModel):
    question_id: int
    question: str
    question_text: Optional[str] = None
    options: List[Dict[str, str]]
    selected_option: Optional[str] = None
    selected_text: Optional[str] = None
    user_answer: str
    correct_option: Optional[str] = None
    correct_text: Optional[str] = None
    correct_answer: str
    is_correct: Optional[bool] = False
    explanation: str

class QuizAttemptResponse(BaseModel):
    id: int
    quiz_id: int
    quiz_title: str
    score: int
    total_questions: int
    percentage: float
    time_taken_seconds: int
    questions_to_review: List[ReviewMistakeItem]
    answers: Optional[List[ReviewMistakeItem]] = None
    all_answers: Optional[List[ReviewMistakeItem]] = None
    created_at: datetime

    class Config:
        from_attributes = True
