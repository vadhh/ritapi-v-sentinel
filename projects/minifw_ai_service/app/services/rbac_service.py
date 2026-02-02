from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

from app.models.user import User, UserRole, SectorType
from app.models.audit import AuditLog, AuditAction, AuditSeverity


class RBACService:
    """Role-Based Access Control Service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_permission(
        self,
        user: User,
        required_role: UserRole,
        action: str = "perform this action"
    ) -> bool:
        """
        Check if user has required permission level
        Raises HTTPException if permission denied
        """
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled"
            )
        
        if user.is_locked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User account is locked until {user.locked_until}"
            )
        
        if not user.has_permission(required_role):
            # Log unauthorized access attempt
            AuditService.log_action(
                db=self.db,
                action=AuditAction.UNAUTHORIZED_ACCESS,
                description=f"User {user.username} attempted to {action} without sufficient permissions",
                user_id=user.id,
                username=user.username,
                severity=AuditSeverity.WARNING,
                success="failure"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}, your role: {user.role.value}"
            )
        
        return True
    
    def check_sector_access(
        self,
        user: User,
        target_sector: SectorType,
        action: str = "access this sector"
    ) -> bool:
        """
        Check if user can access specific sector
        Super admins can access all sectors, others only their assigned sector
        """
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        if user.sector != target_sector:
            AuditService.log_action(
                db=self.db,
                action=AuditAction.UNAUTHORIZED_ACCESS,
                description=f"User {user.username} from sector {user.sector.value} attempted to {action} in sector {target_sector.value}",
                user_id=user.id,
                username=user.username,
                severity=AuditSeverity.WARNING,
                success="failure"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You can only access resources in your sector ({user.sector.value})"
            )
        
        return True
    
    def can_modify_user(self, requesting_user: User, target_user: User) -> bool:
        """Check if requesting user can modify target user"""
        # Super admin can modify anyone
        if requesting_user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Admin can modify users in their sector (except super admins)
        if requesting_user.role == UserRole.ADMIN:
            if target_user.role == UserRole.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot modify super admin accounts"
                )
            if requesting_user.sector != target_user.sector:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only modify users in your sector"
                )
            return True
        
        # Users can only modify themselves
        if requesting_user.id == target_user.id:
            return True
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify other users"
        )
    
    def require_permission(self, required_role: UserRole):
        """Decorator factory for requiring specific permissions"""
        def decorator(func):
            def wrapper(user: User, *args, **kwargs):
                self.check_permission(user, required_role, func.__name__)
                return func(user, *args, **kwargs)
            return wrapper
        return decorator


class AuditService:
    """Service for creating and managing audit logs"""
    
    @staticmethod
    def log_action(
        db: Session,
        action: AuditAction,
        description: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        before_value: Optional[dict] = None,
        after_value: Optional[dict] = None,
        extra_data: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: str = "success",
        error_message: Optional[str] = None
    ) -> AuditLog:
        """Create and save an audit log entry"""
        
        audit_entry = AuditLog(
            action=action,
            description=description,
            user_id=user_id,
            username=username,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            before_value=before_value,
            after_value=after_value,
            extra_data=extra_data,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            error_message=error_message
        )
        
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        
        return audit_entry
    
    @staticmethod
    def log_user_action(
        db: Session,
        user: User,
        action: AuditAction,
        description: str,
        **kwargs
    ) -> AuditLog:
        """Convenience method to log actions with user context"""
        return AuditService.log_action(
            db=db,
            action=action,
            description=description,
            user_id=user.id,
            username=user.username,
            **kwargs
        )
    
    @staticmethod
    def log_policy_change(
        db: Session,
        user: User,
        action: AuditAction,
        policy_id: str,
        before_policy: Optional[dict] = None,
        after_policy: Optional[dict] = None,
        description: str = "Policy modified"
    ) -> AuditLog:
        """Log policy-related changes"""
        return AuditService.log_action(
            db=db,
            action=action,
            description=description,
            user_id=user.id,
            username=user.username,
            resource_type="policy",
            resource_id=policy_id,
            before_value=before_policy,
            after_value=after_policy,
            severity=AuditSeverity.WARNING
        )
    
    @staticmethod
    def log_enforcement_action(
        db: Session,
        action: AuditAction,
        description: str,
        target_ip: str,
        ai_score: Optional[float] = None,
        threat_category: Optional[str] = None,
        rule_id: Optional[str] = None,
        sector: Optional[str] = None
    ) -> AuditLog:
        """Log AI enforcement decisions"""
        enforcement_data = {
            "target_ip": target_ip,
            "ai_score": ai_score,
            "threat_category": threat_category,
            "rule_id": rule_id,
            "sector": sector
        }
        
        return AuditService.log_action(
            db=db,
            action=action,
            description=description,
            resource_type="enforcement",
            resource_id=target_ip,
            extra_data=enforcement_data,
            severity=AuditSeverity.WARNING if action == AuditAction.IP_BLOCKED else AuditSeverity.INFO
        )
    
    @staticmethod
    def get_user_activity(
        db: Session,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ):
        """Get recent activity for a specific user"""
        return db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).offset(offset).all()
    
    @staticmethod
    def get_policy_history(
        db: Session,
        policy_id: str,
        limit: int = 50
    ):
        """Get change history for a specific policy"""
        return db.query(AuditLog).filter(
            AuditLog.resource_type == "policy",
            AuditLog.resource_id == policy_id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()
    
    @staticmethod
    def get_enforcement_logs(
        db: Session,
        sector: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ):
        """Get enforcement action logs with filters"""
        query = db.query(AuditLog).filter(
            AuditLog.action.in_([
                AuditAction.IP_BLOCKED,
                AuditAction.IP_UNBLOCKED,
                AuditAction.DOMAIN_BLOCKED,
                AuditAction.ALERT_TRIGGERED,
                AuditAction.THROTTLE_APPLIED
            ])
        )
        
        if sector:
            # Filter by sector in extra_data
            query = query.filter(
                AuditLog.extra_data.contains(f'"sector": "{sector}"')
            )
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    @staticmethod
    def get_security_events(
        db: Session,
        severity: Optional[AuditSeverity] = None,
        limit: int = 500
    ):
        """Get security-related events"""
        query = db.query(AuditLog).filter(
            AuditLog.action.in_([
                AuditAction.UNAUTHORIZED_ACCESS,
                AuditAction.USER_LOGIN_FAILED,
                AuditAction.SUSPICIOUS_ACTIVITY,
                AuditAction.RATE_LIMIT_EXCEEDED
            ])
        )
        
        if severity:
            query = query.filter(AuditLog.severity == severity)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()