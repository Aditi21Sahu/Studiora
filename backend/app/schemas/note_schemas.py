from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime

class NoteSection(BaseModel):
    title: str
    content: str
    subsections: Optional[List[Dict[str, Any]]] = []
    bullet_points: Optional[List[str]] = []
    examples: Optional[List[str]] = []

class ImportantTerm(BaseModel):
    term: str
    definition: str

class NoteContentStructure(BaseModel):
    title: str
    summary: str
    key_points: List[str]
    sections: List[Dict[str, Any]]
    important_terms: List[Dict[str, str]]
    revision_points: List[str]

class NoteResponse(BaseModel):
    id: int
    user_id: int
    material_id: Optional[int] = None
    title: str
    summary: Optional[str] = None
    key_points: Optional[List[str]] = []
    sections: Optional[List[Dict[str, Any]]] = []
    important_terms: Optional[List[Dict[str, str]]] = []
    revision_points: Optional[List[str]] = []
    source_title: Optional[str] = None
    source_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
