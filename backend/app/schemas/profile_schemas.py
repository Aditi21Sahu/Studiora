from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class ProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: datetime
    materials_uploaded: int
    notes_generated: int
    quizzes_completed: int
    average_score: float

    class Config:
        from_attributes = True
