from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.database.connection import get_db
from app.database.models import User
from app.schemas.auth import UserSignUp, UserLogin, UserResponse, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.api.dependencies.auth import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(data: UserSignUp, db: Session = Depends(get_db)):
    """Registers a new customer and returns an access token."""
    email_clean = data.email.strip().lower()
    
    existing = db.query(User).filter(User.email.ilike(email_clean)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    user_name = data.name.strip() if data.name else email_clean.split("@")[0].capitalize()
    
    new_user = User(
        email=email_clean,
        hashed_password=hash_password(data.password),
        name=user_name
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"👤 [NEW USER REGISTERED]: {new_user.email} (ID: {new_user.id})")

    access_token = create_access_token(payload={"sub": new_user.id, "email": new_user.email})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )

@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Authenticates customer credentials and returns access token."""
    email_clean = data.email.strip().lower()
    
    user = db.query(User).filter(User.email.ilike(email_clean)).first()
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    logger.info(f"🔑 [USER LOGGED IN]: {user.email} (ID: {user.id})")

    access_token = create_access_token(payload={"sub": user.id, "email": user.email})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logs out current user and invalidates session token."""
    logger.info(f"🚪 [USER LOGGED OUT]: {current_user.email} (ID: {current_user.id})")
    return {"success": True, "message": "Successfully logged out."}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns profile for currently authenticated user."""
    return UserResponse.model_validate(current_user)
