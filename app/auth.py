"""
Authentication and session management.
"""
import os
from typing import Optional
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlmodel import Session, select
from itsdangerous import URLSafeTimedSerializer, BadSignature

from app.database import get_session
from app.models import User, UserRole

# Session secret key
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
SESSION_COOKIE_NAME = "aims_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

# Create serializer for session tokens
serializer = URLSafeTimedSerializer(SECRET_KEY)

# HTTP Basic for initial auth
security = HTTPBasic()


def create_session_token(user_id: int) -> str:
    """Create a session token for a user."""
    return serializer.dumps({"user_id": user_id, "created_at": datetime.utcnow().isoformat()})


def verify_session_token(token: str) -> Optional[dict]:
    """Verify and decode a session token."""
    try:
        data = serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data
    except BadSignature:
        return None


def set_session_cookie(response: Response, user_id: int):
    """Set session cookie in response."""
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def get_current_user(
    request: Request,
    session: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user from session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    
    data = verify_session_token(token)
    if not data:
        return None
    
    user = session.get(User, data["user_id"])
    if not user or not user.is_active:
        return None
    
    return user


def require_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authenticated user."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return current_user


def require_admin(
    current_user: User = Depends(require_user)
) -> User:
    """Require admin user."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def authenticate_user(
    email: str,
    password: str,
    session: Session
) -> Optional[User]:
    """Authenticate user by email and password."""
    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    
    if not user or not user.verify_password(password):
        return None
    
    if not user.is_active:
        return None
    
    return user


def create_user(
    email: str,
    username: str,
    password: str,
    role: UserRole,
    session: Session
) -> User:
    """Create a new user."""
    # Check if user exists
    existing = session.exec(
        select(User).where(
            (User.email == email) | (User.username == username)
        )
    ).first()
    
    if existing:
        raise ValueError("User with this email or username already exists")
    
    # Validate password
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters long")
    
    # Bcrypt has a 72-byte limit, truncate if necessary
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    # Create user
    user = User(
        email=email,
        username=username,
        hashed_password=User.hash_password(password),
        role=role
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user
