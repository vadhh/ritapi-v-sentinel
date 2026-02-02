from typing import Optional, List
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets

from app.models.user import User, UserRole, SectorType
from app.models.audit import AuditAction, AuditSeverity
from app.services.rbac_service import AuditService

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserManagementService:
    """Service for managing users with RBAC and audit logging"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: UserRole,
        sector: SectorType,
        full_name: Optional[str] = None,
        department: Optional[str] = None,
        created_by_user: Optional[User] = None,
        must_change_password: bool = True
    ) -> User:
        """Create a new user with audit logging"""
        
        # Check if username or email already exists
        existing = self.db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing:
            raise ValueError("Username or email already exists")
        
        # Hash password
        hashed_password = pwd_context.hash(password)
        
        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            role=role.value if isinstance(role, UserRole) else role,
            sector=sector.value if isinstance(sector, SectorType) else sector,
            full_name=full_name,
            department=department,
            must_change_password=must_change_password,
            created_by=created_by_user.username if created_by_user else "system",
            created_at=datetime.utcnow()
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Log user creation
        AuditService.log_action(
            db=self.db,
            action=AuditAction.USER_CREATED,
            description=f"User {username} created with role {role.value} in sector {sector.value}",
            user_id=created_by_user.id if created_by_user else None,
            username=created_by_user.username if created_by_user else "system",
            resource_type="user",
            resource_id=str(user.id),
            after_value={
                "username": username,
                "email": email,
                "role": role.value,
                "sector": sector.value
            },
            severity=AuditSeverity.INFO
        )
        
        return user
    
    def update_user_role(
        self,
        user_id: int,
        new_role: UserRole,
        modified_by: User
    ) -> User:
        """Update user's role with audit logging"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        old_role = user.role
        user.role = new_role
        user.updated_at = datetime.utcnow()
        user.updated_by = modified_by.username
        
        self.db.commit()
        self.db.refresh(user)
        
        # Log role change
        AuditService.log_action(
            db=self.db,
            action=AuditAction.ROLE_CHANGED,
            description=f"User {user.username} role changed from {old_role.value} to {new_role.value}",
            user_id=modified_by.id,
            username=modified_by.username,
            resource_type="user",
            resource_id=str(user.id),
            before_value={"role": old_role.value},
            after_value={"role": new_role.value},
            severity=AuditSeverity.WARNING
        )
        
        return user
    
    def update_user_sector(
        self,
        user_id: int,
        new_sector: SectorType,
        modified_by: User
    ) -> User:
        """Update user's sector with audit logging"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        old_sector = user.sector
        user.sector = new_sector
        user.updated_at = datetime.utcnow()
        user.updated_by = modified_by.username
        
        self.db.commit()
        self.db.refresh(user)
        
        # Log sector change
        AuditService.log_action(
            db=self.db,
            action=AuditAction.SECTOR_CHANGED,
            description=f"User {user.username} sector changed from {old_sector.value} to {new_sector.value}",
            user_id=modified_by.id,
            username=modified_by.username,
            resource_type="user",
            resource_id=str(user.id),
            before_value={"sector": old_sector.value},
            after_value={"sector": new_sector.value},
            severity=AuditSeverity.WARNING
        )
        
        return user
    
    def disable_user(
        self,
        user_id: int,
        disabled_by: User,
        reason: Optional[str] = None
    ) -> User:
        """Disable user account with audit logging"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        user.updated_by = disabled_by.username
        
        self.db.commit()
        self.db.refresh(user)
        
        # Log user disable
        AuditService.log_action(
            db=self.db,
            action=AuditAction.USER_DISABLED,
            description=f"User {user.username} disabled. Reason: {reason or 'Not specified'}",
            user_id=disabled_by.id,
            username=disabled_by.username,
            resource_type="user",
            resource_id=str(user.id),
            metadata={"reason": reason},
            severity=AuditSeverity.WARNING
        )
        
        return user
    
    def enable_user(
        self,
        user_id: int,
        enabled_by: User
    ) -> User:
        """Enable user account with audit logging"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        user.is_active = True
        user.is_locked = False
        user.locked_until = None
        user.failed_login_attempts = 0
        user.updated_at = datetime.utcnow()
        user.updated_by = enabled_by.username
        
        self.db.commit()
        self.db.refresh(user)
        
        # Log user enable
        AuditService.log_action(
            db=self.db,
            action=AuditAction.USER_ENABLED,
            description=f"User {user.username} enabled",
            user_id=enabled_by.id,
            username=enabled_by.username,
            resource_type="user",
            resource_id=str(user.id),
            severity=AuditSeverity.INFO
        )
        
        return user
    
    def lock_user_account(
        self,
        user: User,
        duration_minutes: int = 30,
        reason: str = "Multiple failed login attempts"
    ):
        """Lock user account temporarily"""
        user.is_locked = True
        user.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        
        self.db.commit()
        
        # Log account lock
        AuditService.log_action(
            db=self.db,
            action=AuditAction.SUSPICIOUS_ACTIVITY,
            description=f"User {user.username} account locked: {reason}",
            user_id=user.id,
            username=user.username,
            resource_type="user",
            resource_id=str(user.id),
            metadata={
                "reason": reason,
                "locked_until": user.locked_until.isoformat(),
                "duration_minutes": duration_minutes
            },
            severity=AuditSeverity.WARNING
        )
    
    def record_failed_login(
        self,
        username: str,
        ip_address: str,
        user_agent: str
    ):
        """Record failed login attempt"""
        user = self.db.query(User).filter(User.username == username).first()
        
        if user:
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                self.lock_user_account(user)
            
            self.db.commit()
        
        # Log failed login
        AuditService.log_action(
            db=self.db,
            action=AuditAction.USER_LOGIN_FAILED,
            description=f"Failed login attempt for username: {username}",
            username=username,
            user_id=user.id if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=AuditSeverity.WARNING,
            success="failure"
        )
    
    def record_successful_login(
        self,
        user: User,
        ip_address: str,
        user_agent: str,
        session_id: str
    ):
        """Record successful login"""
        user.last_login = datetime.utcnow()
        user.last_login_ip = ip_address
        user.failed_login_attempts = 0
        user.session_token = session_id
        
        self.db.commit()
        
        # Log successful login
        AuditService.log_action(
            db=self.db,
            action=AuditAction.USER_LOGIN,
            description=f"User {user.username} logged in successfully",
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            severity=AuditSeverity.INFO
        )
    
    def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
        changed_by: Optional[User] = None
    ):
        """Change user password with verification"""
        # Verify old password
        if not pwd_context.verify(old_password, user.hashed_password):
            raise ValueError("Incorrect current password")
        
        # Hash new password
        user.hashed_password = pwd_context.hash(new_password)
        user.last_password_change = datetime.utcnow()
        user.must_change_password = False
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Log password change
        AuditService.log_action(
            db=self.db,
            action=AuditAction.PASSWORD_CHANGED,
            description=f"Password changed for user {user.username}",
            user_id=changed_by.id if changed_by else user.id,
            username=changed_by.username if changed_by else user.username,
            resource_type="user",
            resource_id=str(user.id),
            severity=AuditSeverity.INFO
        )
    
    def reset_password(
        self,
        user_id: int,
        new_password: str,
        reset_by: User
    ) -> str:
        """Admin reset of user password"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise ValueError("User not found")
        
        user.hashed_password = pwd_context.hash(new_password)
        user.last_password_change = datetime.utcnow()
        user.must_change_password = True
        user.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        # Log password reset
        AuditService.log_action(
            db=self.db,
            action=AuditAction.PASSWORD_RESET,
            description=f"Password reset for user {user.username} by admin {reset_by.username}",
            user_id=reset_by.id,
            username=reset_by.username,
            resource_type="user",
            resource_id=str(user.id),
            severity=AuditSeverity.WARNING
        )
        
        return new_password
    
    def get_users_by_sector(
        self,
        sector: SectorType,
        include_inactive: bool = False
    ) -> List[User]:
        """Get all users in a specific sector"""
        query = self.db.query(User).filter(User.sector == sector)
        
        if not include_inactive:
            query = query.filter(User.is_active == True)
        
        return query.all()
    
    def get_users_by_role(
        self,
        role: UserRole,
        sector: Optional[SectorType] = None
    ) -> List[User]:
        """Get all users with a specific role"""
        query = self.db.query(User).filter(User.role == role)
        
        if sector:
            query = query.filter(User.sector == sector)
        
        return query.all()