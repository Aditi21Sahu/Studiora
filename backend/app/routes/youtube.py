from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.youtube_service import youtube_service

router = APIRouter(prefix="/youtube", tags=["YouTube Diagnostics"])

class YouTubeTestRequest(BaseModel):
    url: str

class YouTubeTestResponse(BaseModel):
    success: bool
    video_id: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[str] = None
    transcript_found: Optional[bool] = None
    language: Optional[str] = None
    entry_count: Optional[int] = None
    character_count: Optional[int] = None
    word_count: Optional[int] = None
    sample: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None

@router.post("/test-transcript", response_model=YouTubeTestResponse)
def test_transcript_endpoint(req: YouTubeTestRequest):
    """
    Diagnostic endpoint to inspect and test YouTube URL caption extraction.
    """
    return youtube_service.test_transcript_diagnostics(req.url)
