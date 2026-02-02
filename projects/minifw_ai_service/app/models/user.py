from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    """User role definitions with hierarchical permissions"""
    SUPER_ADMIN = "super_admin"      # Full system access, can manage all sectors
    ADMIN = "admin"                  # Sector-specific admin access
    OPERATOR = "operator"            # Can view and execute actions, cannot modify policies
    AUDITOR = "auditor"              # Read-only access with audit capabilities
    VIEWER = "viewer"                # Read-only dashboard access


class SectorType(str, enum.Enum):
    """Sector classifications for different organization types (Factory-Set)"""
    HOSPITAL = "hospital"
    SCHOOL = "school"
    GOVERNMENT = "government"
    FINANCE = "finance"
    LEGAL = "legal"
    ESTABLISHMENT = "establishment"


class User(Base):
    __tablename__ = "users"
    
    # Basic identification
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Role-Based Access Control (RBAC)
    role = Column(String(20), default=UserRole.VIEWER.value, nullable=False)
    sector = Column(String(20), default=SectorType.ESTABLISHMENT.value, nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Multi-Factor Authentication
    is_2fa_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(32), nullable=True)
    backup_codes = Column(String(500), nullable=True)  # JSON array of backup codes
    
    # Session and security
    session_token = Column(String(255), nullable=True)
    last_password_change = Column(DateTime, default=datetime.utcnow)
    password_expires_at = Column(DateTime, nullable=True)
    must_change_password = Column(Boolean, default=False)
    
    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)
    last_login = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    
    # Additional metadata
    full_name = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    
    @property
    def role_enum(self) -> UserRole:
        """Get role as enum"""
        return UserRole(self.role)
    
    @property
    def sector_enum(self) -> SectorType:
        """Get sector as enum"""
        return SectorType(self.sector)
    
    def __repr__(self):
        return f"<User {self.username} ({self.role}) - {self.sector}>"
    
    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required permission level"""
        role_hierarchy = {
            UserRole.SUPER_ADMIN: 5,
            UserRole.ADMIN: 4,
            UserRole.OPERATOR: 3,
            UserRole.AUDITOR: 2,
            UserRole.VIEWER: 1
        }
        user_role = UserRole(self.role)
        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)
    
    def can_modify_policy(self) -> bool:
        """Check if user can modify firewall policies"""
        user_role = UserRole(self.role)
        return user_role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    def can_execute_enforcement(self) -> bool:
        """Check if user can execute enforcement actions"""
        user_role = UserRole(self.role)
        return user_role in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.OPERATOR]
    
    def can_access_audit(self) -> bool:
        """Check if user can access audit logs"""
        return True  # All authenticated users can view their own actions
    
    def can_export_data(self) -> bool:
        """Check if user can export reports and logs"""
        user_role = UserRole(self.role)
        return user_role in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.AUDITOR]