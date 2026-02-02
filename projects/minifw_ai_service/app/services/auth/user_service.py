from sqlalchemy.orm import Session
from app.models.user import User
from app.services.auth.password_service import get_password_hash, verify_password
from app.services.auth.totp_service import generate_totp_secret
from datetime import datetime
from typing import Optional

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username"""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, username: str, email: str, password: str) -> User:
    """Create new user"""
    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user with username and password"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def enable_2fa(db: Session, user: User) -> str:
    """Enable 2FA for user and return secret"""
    secret = generate_totp_secret()
    user.totp_secret = secret
    user.is_2fa_enabled = True
    db.commit()
    return secret

def disable_2fa(db: Session, user: User):
    """Disable 2FA for user"""
    user.is_2fa_enabled = False
    user.totp_secret = None
    db.commit()

def update_last_login(db: Session, user: User):
    """Update user's last login timestamp"""
    user.last_login = datetime.utcnow()
    db.commit()