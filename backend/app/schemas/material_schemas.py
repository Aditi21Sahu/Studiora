from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class MaterialUrlRequest(BaseModel):
    url: str
    title: Optional[str] = None

class MaterialResponse(BaseModel):
    id: int
    user_id: int
    title: str
    file_type: str
    source_type: str
    file_size: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class MaterialDetailResponse(MaterialResponse):
    text_content: Optional[str] = None
