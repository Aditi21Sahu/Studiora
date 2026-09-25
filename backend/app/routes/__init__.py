from app.routes.auth import router as auth_router
from app.routes.materials import router as materials_router
from app.routes.notes import router as notes_router
from app.routes.quizzes import router as quizzes_router
from app.routes.reports import router as reports_router
from app.routes.profile import router as profile_router
from app.routes.youtube import router as youtube_router
from app.routes.tests import router as tests_router

__all__ = [
    "auth_router",
    "materials_router",
    "notes_router",
    "quizzes_router",
    "reports_router",
    "profile_router",
    "youtube_router",
    "tests_router"
]
