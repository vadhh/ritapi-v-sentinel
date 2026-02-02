"""
User Management Controller for MiniFW V-Sentinel
Controller functions for user CRUD operations
"""

from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.user import User, UserRole, SectorType
from app.models.audit import AuditAction, AuditSeverity
from app.services.rbac_service import RBACService, AuditService
from app.services.user_management_service import UserManagementService

templates = Jinja2Templates(directory="app/web/templates")


def user_management_page_controller(request: Request):
    """
    User management page controller
    Shows user management interface (Super Admin only)
    """
    
    # Render the page (permission check happens in JavaScript)
    return templates.TemplateResponse(
        "admin/user_management.html",
        {"request": request}
    )


def get_all_users_controller(db: Session, current_user: User):
    """
    Get all users
    Returns list of all users with their details
    """
    
    # Check permission
    rbac = RBACService(db)
    rbac.check_permission(current_user, UserRole.SUPER_ADMIN, "view all users")
    
    # Get all users
    users = db.query(User).all()
    
    # Log access
    AuditService.log_user_action(
        db=db,
        user=current_user,
        action=AuditAction.LOG_ACCESSED,
        description=f"Retrieved list of all users ({len(users)} users)",
        resource_type="users",
        severity=AuditSeverity.INFO
    )
    
    # Convert to response format
    users_data = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "sector": user.sector,
            "full_name": user.full_name,
            "department": user.department,
            "phone": user.phone,
            "is_active": user.is_active,
            "is_locked": user.is_locked,
            "is_2fa_enabled": user.is_2fa_enabled,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
            "last_login_ip": user.last_login_ip
        }
        for user in users
    ]
    
    return {"users": users_data, "total": len(users_data)}


def create_user_controller(
    db: Session,
    current_user: User,
    username: str,
    email: str,
    password: str,
    role: str,
    sector: str,
    full_name: Optional[str] = None,
    department: Optional[str] = None,
    phone: Optional[str] = None,
    must_change_password: bool = True
):
    """
    Create new user
    """
    
    # Check permission
    rbac = RBACService(db)
    rbac.check_permission(current_user, UserRole.SUPER_ADMIN, "create users")
    
    # Create user
    user_service = UserManagementService(db)
    
    try:
        # Convert string role/sector to enum
        role_enum = UserRole(role)
        sector_enum = SectorType(sector)
        
        new_user = user_service.create_user(
            username=username,
            email=email,
            password=password,
            role=role_enum,
            sector=sector_enum,
            full_name=full_name,
            department=department,
            created_by_user=current_user,
            must_change_password=must_change_password
        )
        
        return {
            "id": new_user.id,
            "username": new_user.username,
            "email": new_user.email,
            "role": new_user.role,
            "sector": new_user.sector,
            "message": "User created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_user_controller(
    db: Session,
    current_user: User,
    user_id: int,
    email: Optional[str] = None,
    role: Optional[str] = None,
    sector: Optional[str] = None,
    full_name: Optional[str] = None,
    department: Optional[str] = None,
    phone: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """
    Update user details
    """
    
    # Check permission
    rbac = RBACService(db)
    rbac.check_permission(current_user, UserRole.SUPER_ADMIN, "update users")
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Store old values for audit
    old_values = {
        "email": user.email,
        "role": user.role,
        "sector": user.sector,
        "is_active": user.is_active
    }
    
    # Update fields
    if email is not None:
        user.email = email
    if role is not None:
        user.role = role  # Store as string directly
    if sector is not None:
        user.sector = sector  # Store as string directly
    if full_name is not None:
        user.full_name = full_name
    if department is not None:
        user.department = department
    if phone is not None:
        user.phone = phone
    if is_active is not None:
        user.is_active = is_active
    
    user.updated_at = datetime.now()
    user.updated_by = current_user.username
    
    db.commit()
    db.refresh(user)
    
    # Log the update
    new_values = {
        "email": user.email,
        "role": user.role,
        "sector": user.sector,
        "is_active": user.is_active
    }
    
    AuditService.log_user_action(
        db=db,
        user=current_user,
        action=AuditAction.USER_UPDATED,
        description=f"Updated user {user.username}",
        resource_type="user",
        resource_id=str(user.id),
        before_value=old_values,
        after_value=new_values,
        severity=AuditSeverity.WARNING
    )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "sector": user.sector,
        "message": "User updated successfully"
    }


def change_password_controller(
    db: Session,
    current_user: User,
    user_id: int,
    new_password: str,
    must_change_password: bool = True
):
    """
    Change user password
    """
    
    # Check permission
    rbac = RBACService(db)
    rbac.check_permission(current_user, UserRole.SUPER_ADMIN, "change user passwords")
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Change password using service
    user_service = UserManagementService(db)
    
    try:
        user_service.reset_password(
            user_id=user_id,
            new_password=new_password,
            reset_by=current_user
        )
        
        # Update must_change_password flag
        user.must_change_password = must_change_password
        db.commit()
        
        return {
            "message": "Password changed successfully",
            "user": user.username,
            "must_change_password": must_change_password
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def delete_user_controller(
    db: Session,
    current_user: User,
    user_id: int
):
    """
    Delete user
    """
    
    # Check permission
    rbac = RBACService(db)
    rbac.check_permission(current_user, UserRole.SUPER_ADMIN, "delete users")
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account"
        )
    
    # Store user info for audit
    user_info = {
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "sector": user.sector
    }
    
    # Delete user
    db.delete(user)
    
    # Log deletion
    AuditService.log_user_action(
        db=db,
        user=current_user,
        action=AuditAction.USER_DELETED,
        description=f"Deleted user {user.username}",
        resource_type="user",
        resource_id=str(user_id),
        before_value=user_info,
        severity=AuditSeverity.CRITICAL
    )
    
    db.commit()
    
    return {
        "message": "User deleted successfully",
        "deleted_user": user_info["username"]
    }


def get_current_user_info_controller(current_user: User):
    """
    Get current user information
    Used by frontend to check permissions
    """
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "sector": current_user.sector,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active
    }