"""
Audit Logs Controller for MiniFW V-Sentinel
Controller functions for viewing audit logs and system activity
"""

from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from app.models.user import User, UserRole
from app.models.audit import AuditLog, AuditAction, AuditSeverity
from app.services.rbac_service import RBACService, AuditService

templates = Jinja2Templates(directory="app/web/templates")


def audit_logs_page_controller(request: Request):
    """
    Audit logs page controller
    Shows audit log viewer interface
    """
    
    return templates.TemplateResponse(
        "admin/audit_logs.html",
        {"request": request}
    )


def get_all_audit_logs_controller(
    db: Session,
    current_user: User,
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get audit logs with filters
    """
    
    # Check permission - all authenticated users can view audit logs
    # but only super_admin and auditor can see all logs
    rbac = RBACService(db)
    
    # Build query
    query = db.query(AuditLog)
    
    # If user is not super_admin or auditor, only show their own logs
    if current_user.role not in ['super_admin', 'auditor', 'admin']:
        query = query.filter(AuditLog.user_id == current_user.id)
    
    # Apply filters
    if action:
        query = query.filter(AuditLog.action == action)
    
    if severity:
        query = query.filter(AuditLog.severity == severity)
    
    if username:
        query = query.filter(AuditLog.username.like(f'%{username}%'))
    
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(AuditLog.timestamp >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(AuditLog.timestamp <= end)
        except ValueError:
            pass
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset).all()
    
    # Convert to response format
    logs_data = [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "username": log.username,
            "user_role": log.user_role,
            "user_sector": log.user_sector,
            "action": log.action,
            "severity": log.severity,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "ip_address": log.ip_address,
            "success": log.success,
            "before_value": log.before_value,
            "after_value": log.after_value,
            "extra_data": log.extra_data
        }
        for log in logs
    ]
    
    # Log this access
    AuditService.log_user_action(
        db=db,
        user=current_user,
        action=AuditAction.LOG_ACCESSED,
        description=f"Viewed audit logs (total: {total}, filters: action={action}, severity={severity})",
        resource_type="audit_logs",
        severity=AuditSeverity.INFO
    )
    
    return {
        "logs": logs_data,
        "total": total,
        "limit": limit,
        "offset": offset
    }


def get_audit_statistics_controller(
    db: Session,
    current_user: User,
    days: int = 7
):
    """
    Get audit log statistics for dashboard
    """
    
    # Check permission
    rbac = RBACService(db)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Build base query
    query = db.query(AuditLog).filter(
        AuditLog.timestamp >= start_date,
        AuditLog.timestamp <= end_date
    )
    
    # If not super_admin/auditor, only show own logs
    if current_user.role not in ['super_admin', 'auditor', 'admin']:
        query = query.filter(AuditLog.user_id == current_user.id)
    
    # Get statistics
    total_logs = query.count()
    
    # Count by severity
    critical = query.filter(AuditLog.severity == 'critical').count()
    warnings = query.filter(AuditLog.severity == 'warning').count()
    info = query.filter(AuditLog.severity == 'info').count()
    
    # Count by action type
    user_actions = query.filter(AuditLog.action.in_([
        'user_login', 'user_logout', 'user_created', 'user_updated', 'user_deleted'
    ])).count()
    
    policy_changes = query.filter(AuditLog.action.in_([
        'policy_created', 'policy_updated', 'policy_deleted'
    ])).count()
    
    enforcement_actions = query.filter(AuditLog.action.in_([
        'ip_blocked', 'ip_unblocked', 'domain_blocked', 'alert_triggered'
    ])).count()
    
    failed_logins = query.filter(AuditLog.action == 'user_login_failed').count()
    unauthorized = query.filter(AuditLog.action == 'unauthorized_access').count()
    
    # Get recent critical events
    recent_critical = db.query(AuditLog).filter(
        AuditLog.severity == 'critical',
        AuditLog.timestamp >= start_date
    ).order_by(AuditLog.timestamp.desc()).limit(10).all()
    
    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_logs": total_logs,
        "by_severity": {
            "critical": critical,
            "warning": warnings,
            "info": info
        },
        "by_category": {
            "user_actions": user_actions,
            "policy_changes": policy_changes,
            "enforcement_actions": enforcement_actions,
            "failed_logins": failed_logins,
            "unauthorized_access": unauthorized
        },
        "recent_critical": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "username": log.username,
                "action": log.action,
                "description": log.description
            }
            for log in recent_critical
        ]
    }


def export_audit_logs_controller(
    db: Session,
    current_user: User,
    format: str = "json",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Export audit logs to JSON or CSV
    """
    
    # Check permission - only super_admin, admin, and auditor can export
    rbac = RBACService(db)
    if current_user.role not in ['super_admin', 'admin', 'auditor']:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to export audit logs"
        )
    
    # Build query
    query = db.query(AuditLog)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.filter(AuditLog.timestamp >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.filter(AuditLog.timestamp <= end)
        except ValueError:
            pass
    
    logs = query.order_by(AuditLog.timestamp.desc()).all()
    
    # Log export action
    AuditService.log_user_action(
        db=db,
        user=current_user,
        action="log_exported",
        description=f"Exported {len(logs)} audit logs in {format} format",
        resource_type="audit_logs",
        severity="warning"
    )
    
    # Convert to export format
    export_data = [
        {
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "username": log.username,
            "user_role": log.user_role,
            "action": log.action,
            "severity": log.severity,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "ip_address": log.ip_address,
            "success": log.success
        }
        for log in logs
    ]
    
    return {
        "format": format,
        "count": len(export_data),
        "data": export_data
    }