from fastapi import Request, HTTPException, status, Depends
from app.services.auth.token_service import verify_token
from app.database import get_db
from sqlalchemy.orm import Session
from app.services.auth.user_service import get_user_by_username

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Dependency untuk get current user dari token
    Raise exception jika tidak ada token atau token invalid
    """
    token = request.cookies.get("access_token")
    
    # Check jika tidak ada token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Get username dari payload
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get user from database
    user = get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


def require_auth(request: Request, db: Session = Depends(get_db)):
    """
    Dependency untuk require authentication
    Returns user object jika authenticated
    """
    return get_current_user(request, db)