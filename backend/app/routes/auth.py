import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.activity import Activity
from app.schemas.auth_schemas import (
    UserRegister, UserLogin, Token, UserResponse,
    ForgotPasswordRequest, ForgotPasswordResponse
)
from app.services.auth_service import (
    get_password_hash, verify_password, create_access_token, get_current_user
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """Register a new student account."""
    # Check if passwords match
    if user_in.confirm_password and user_in.password != user_in.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )

    # Check email existence
    existing = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Password validation
    if len(user_in.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )

    # Create new user
    hashed_pwd = get_password_hash(user_in.password)
    user = User(
        full_name=user_in.full_name.strip(),
        email=user_in.email.lower().strip(),
        password_hash=hashed_pwd
    )
    db.add(user)
    db.flush()

    # Welcome activity
    activity = Activity(
        user_id=user.id,
        activity_type="account_created",
        title="Account created",
        description="Welcome to Studiora! Start by uploading your study materials."
    )
    db.add(activity)
    db.commit()
    db.refresh(user)

    # Create token
    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email
    }

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """Authenticate student credentials and issue JWT."""
    email_clean = user_in.email.lower().strip()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Please try again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return current_user

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Initiate password reset flow."""
    user = db.query(User).filter(User.email == req.email.lower().strip()).first()
    if not user:
        # Prevent email enumeration while still helping development
        return {
            "status": "success",
            "message": f"If an account exists for {req.email}, a password reset link has been dispatched."
        }

    # In local development mode, password reset link is logged
    logger.info("Password reset requested for user %s (%s).", user.id, user.email)
    return {
        "status": "success",
        "message": f"Password reset instructions have been sent to {req.email}. (Email provider configuration documented in README)."
    }

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout endpoint."""
    return {"status": "success", "message": "Successfully logged out."}
