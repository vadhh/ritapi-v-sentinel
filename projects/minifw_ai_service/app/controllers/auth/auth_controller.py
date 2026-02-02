from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth.user_service import (
    authenticate_user,
    get_user_by_username,
    enable_2fa,
    update_last_login
)
from app.services.auth.token_service import create_access_token
from app.services.auth.totp_service import verify_totp, get_totp_uri, generate_qr_code

templates = Jinja2Templates(directory="app/web/templates")


def login_page_controller(request: Request):
    """Show login page"""
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request}
    )


def login_controller(request: Request, username: str, password: str, db: Session = Depends(get_db)):
    """Handle login"""
    user = authenticate_user(db, username, password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # If 2FA is enabled, redirect to 2FA page
    if user.is_2fa_enabled:
        return {
            "requires_2fa": True,
            "username": username
        }
    
    # No 2FA, create token and login
    access_token = create_access_token(data={"sub": user.username})
    update_last_login(db, user)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "requires_2fa": False
    }


def verify_2fa_controller(
    request: Request,
    username: str,
    totp_code: str,
    db: Session = Depends(get_db)
):
    """Verify 2FA code"""
    user = get_user_by_username(db, username)
    
    if not user or not user.is_2fa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not enabled for this user"
        )
    
    # Verify TOTP code
    if not verify_totp(user.totp_secret, totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code"
        )
    
    # Create token
    access_token = create_access_token(data={"sub": user.username})
    update_last_login(db, user)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


def setup_2fa_controller(request: Request, username: str, db: Session = Depends(get_db)):
    """Setup 2FA for user"""
    user = get_user_by_username(db, username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Enable 2FA and get secret
    secret = enable_2fa(db, user)
    
    # Generate QR code
    uri = get_totp_uri(secret, user.username)
    qr_code = generate_qr_code(uri)
    
    return {
        "secret": secret,
        "qr_code": qr_code,
        "uri": uri
    }