import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "STUDIORA"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # AI - Groq settings
    GROQ_API_KEY: str = (os.getenv("GROQ_API_KEY") or "").strip()
    GROQ_TEXT_MODEL: str = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
    GROQ_STT_MODEL: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    if not DATABASE_URL or DATABASE_URL in ("sqlite:///./studiora.db", "sqlite:///studiora.db"):
        _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _db_path = os.path.join(_backend_dir, "studiora.db").replace("\\", "/")
        DATABASE_URL = f"sqlite:///{_db_path}"
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "studiora_super_secret_jwt_key_2026_safe_dev_production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    # Uploads directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

settings = Settings()

# Ensure uploads folder exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
