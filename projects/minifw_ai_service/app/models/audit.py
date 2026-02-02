from sqlalchemy import Column, Integer, String, DateTime, Text, Enum as SQLEnum, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class AuditAction(str, enum.Enum):
    """Types of actions that can be audited"""
    # User management
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    
    # Role and permission changes
    ROLE_CHANGED = "role_changed"
    SECTOR_CHANGED = "sector_changed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    
    # Policy management
    POLICY_VIEWED = "policy_viewed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_DELETED = "policy_deleted"
    POLICY_ACTIVATED = "policy_activated"
    POLICY_DEACTIVATED = "policy_deactivated"
    POLICY_ROLLED_BACK = "policy_rolled_back"
    POLICY_EXPORTED = "policy_exported"
    
    # Firewall rules
    RULE_CREATED = "rule_created"
    RULE_UPDATED = "rule_updated"
    RULE_DELETED = "rule_deleted"
    RULE_PRIORITY_CHANGED = "rule_priority_changed"
    
    # Enforcement actions
    IP_BLOCKED = "ip_blocked"
    IP_UNBLOCKED = "ip_unblocked"
    DOMAIN_BLOCKED = "domain_blocked"
    DOMAIN_UNBLOCKED = "domain_unblocked"
    ASN_BLOCKED = "asn_blocked"
    ASN_UNBLOCKED = "asn_unblocked"
    ALERT_TRIGGERED = "alert_triggered"
    THROTTLE_APPLIED = "throttle_applied"
    
    # AI and detection
    AI_DETECTION_EVENT = "ai_detection_event"
    AI_SCORE_CALCULATED = "ai_score_calculated"
    AI_MODEL_UPDATED = "ai_model_updated"
    THREAT_DETECTED = "threat_detected"
    FALSE_POSITIVE_MARKED = "false_positive_marked"
    
    # System configuration
    CONFIG_CHANGED = "config_changed"
    SECTOR_CONFIG_CHANGED = "sector_config_changed"
    THRESHOLD_CHANGED = "threshold_changed"
    FEATURE_ENABLED = "feature_enabled"
    FEATURE_DISABLED = "feature_disabled"
    
    # Data access and export
    DATA_EXPORTED = "data_exported"
    REPORT_GENERATED = "report_generated"
    LOG_ACCESSED = "log_accessed"
    DASHBOARD_ACCESSED = "dashboard_accessed"
    
    # Security events
    SESSION_EXPIRED = "session_expired"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"


class AuditSeverity(str, enum.Enum):
    """Severity levels for audit events"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # User information
    user_id = Column(Integer, index=True, nullable=True)  # Can be null for system actions
    username = Column(String(50), index=True, nullable=True)
    user_role = Column(String(20), nullable=True)
    user_sector = Column(String(20), nullable=True)
    
    # Action details
    action = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default=AuditSeverity.INFO.value, nullable=False)
    resource_type = Column(String(50), nullable=True, index=True)  # e.g., "policy", "user", "rule"
    resource_id = Column(String(100), nullable=True, index=True)
    
    # Context and details
    description = Column(Text, nullable=False)
    before_value = Column(JSON, nullable=True)  # State before change (for updates)
    after_value = Column(JSON, nullable=True)   # State after change (for updates)
    extra_data = Column(JSON, nullable=True)     # Additional contextual information (renamed from metadata)
    
    # Network and session information
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(255), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Status and outcome
    success = Column(String(10), default="success", nullable=False)  # success, failure, partial
    error_message = Column(Text, nullable=True)
    
    # Compliance and traceability
    compliance_flag = Column(String(50), nullable=True)  # For regulatory requirements
    retention_until = Column(DateTime, nullable=True)     # When this log can be purged
    
    def __repr__(self):
        return f"<AuditLog {self.id}: {self.action.value} by {self.username} at {self.timestamp}>"
    
    @classmethod
    def create_entry(
        cls,
        action: AuditAction,
        description: str,
        user_id: int = None,
        username: str = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        resource_type: str = None,
        resource_id: str = None,
        before_value: dict = None,
        after_value: dict = None,
        metadata: dict = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        success: str = "success",
        error_message: str = None
    ):
        """Helper method to create audit log entries with consistent structure"""
        return cls(
            action=action,
            description=description,
            user_id=user_id,
            username=username,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            before_value=before_value,
            after_value=after_value,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            error_message=error_message
        )


class PolicyVersion(Base):
    """Track policy changes for rollback and compliance"""
    __tablename__ = "policy_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version_number = Column(Integer, nullable=False, index=True)
    sector = Column(String(20), nullable=False, index=True)
    
    # Policy content
    policy_json = Column(JSON, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA-256 hash of policy
    
    # Version metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(String(50), nullable=False)
    change_description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    
    # Validation and deployment
    validation_status = Column(String(20), default="pending", nullable=False)  # pending, validated, failed
    deployed_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by = Column(String(50), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<PolicyVersion {self.sector} v{self.version_number}>"