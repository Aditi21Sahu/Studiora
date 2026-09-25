import sys
import logging

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
import app.models  # Ensures all models are registered with Base metadata
from app.routes import (
    auth_router,
    materials_router,
    notes_router,
    quizzes_router,
    reports_router,
    profile_router,
    youtube_router,
    tests_router
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("studiora")

# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="STUDIORA API",
    description="AI-Powered Learning Platform Backend for Studiora",
    version=settings.VERSION
)

# Configure CORS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    settings.FRONTEND_URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory for static access if needed
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API Routers under /api
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(materials_router, prefix=settings.API_V1_STR)
app.include_router(notes_router, prefix=settings.API_V1_STR)
app.include_router(quizzes_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(profile_router, prefix=settings.API_V1_STR)
app.include_router(youtube_router, prefix=settings.API_V1_STR)
app.include_router(tests_router, prefix=settings.API_V1_STR)

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/info")
def app_info():
    return {
        "app": "STUDIORA API",
        "tagline": "Everything you need to learn better",
        "status": "online",
        "version": settings.VERSION
    }

from fastapi.responses import RedirectResponse

@app.get("/login")
def redirect_login():
    return RedirectResponse(url="/login.html")

@app.get("/register")
def redirect_register():
    return RedirectResponse(url="/register.html")

@app.get("/forgot-password")
def redirect_forgot_password():
    return RedirectResponse(url="/forgot-password.html")

@app.get("/dashboard")
def redirect_dashboard():
    return RedirectResponse(url="/dashboard.html")

@app.get("/study-material")
def redirect_study_material():
    return RedirectResponse(url="/study-material.html")

@app.get("/notes")
def redirect_notes():
    return RedirectResponse(url="/notes.html")

@app.get("/quizzes")
def redirect_quizzes():
    return RedirectResponse(url="/quizzes.html")

@app.get("/reports")
def redirect_reports():
    return RedirectResponse(url="/reports.html")

@app.get("/test-papers")
def redirect_test_papers():
    return RedirectResponse(url="/test-papers.html")

# Mount static frontend directory at root /
import os
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

