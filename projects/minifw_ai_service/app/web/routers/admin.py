from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.controllers.admin.dashboard_controller import dashboard_controller
from app.controllers.admin.allow_domain_controller import (
    allow_domain_controller,
    add_allow_domain,
    update_allow_domain,
    delete_allow_domain
)
from app.controllers.admin.deny_ip_controller import (
    deny_ip_controller,
    add_deny_ip,
    update_deny_ip,
    delete_deny_ip
)
from app.controllers.admin.deny_asn_controller import (
    deny_asn_controller,
    add_deny_asn,
    update_deny_asn,
    delete_deny_asn
)
from app.controllers.admin.deny_domain_controller import (
    deny_domain_controller,
    add_deny_domain,
    update_deny_domain,
    delete_deny_domain
)

from app.controllers.admin.events_controller import events_controller
from app.controllers.admin.events_api_controller import events_datatable_controller
from app.controllers.admin.download_events_controller import download_events_controller
from app.controllers.admin.policy_controller import (
    policy_controller,
    add_segment_controller,
    delete_segment_controller,
    update_segment_subnets_controller,
    update_features_controller,
    update_enforcement_controller,
    update_collectors_controller,
    update_burst_controller
)
from app.controllers.admin.user_management_controller import (
    user_management_page_controller,
    get_all_users_controller,
    create_user_controller,
    update_user_controller,
    change_password_controller,
    delete_user_controller,
    get_current_user_info_controller
)
from app.controllers.admin.audit_logs_controller import (
    audit_logs_page_controller,
    get_all_audit_logs_controller,
    get_audit_statistics_controller,
    export_audit_logs_controller
)

from typing import Optional  # <-- ADD THIS
from sqlalchemy.orm import Session  # <-- ADD THIS
from app.database import get_db  # <-- ADD THIS

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/web/templates")

# Pydantic models for request bodies
class AddDomainRequest(BaseModel):
    domain: str

class UpdateDomainRequest(BaseModel):
    old: str
    new: str

class DeleteDomainRequest(BaseModel):
    domain: str
    
class AddIpRequest(BaseModel):
    ip: str

class UpdateIpRequest(BaseModel):
    old: str
    new: str

class DeleteIpRequest(BaseModel):
    ip: str
    
class AddAsnRequest(BaseModel):
    asn: str

class UpdateAsnRequest(BaseModel):
    old: str
    new: str

class DeleteAsnRequest(BaseModel):
    asn: str
    
class AddDenyDomainRequest(BaseModel):
    domain: str

class UpdateDenyDomainRequest(BaseModel):
    old: str
    new: str

class DeleteDenyDomainRequest(BaseModel):
    domain: str

# Policy requests
class AddSegmentRequest(BaseModel):
    segment_name: str
    block_threshold: int
    monitor_threshold: int

class UpdateSubnetsRequest(BaseModel):
    segment_name: str
    subnets: list

class UpdateFeaturesRequest(BaseModel):
    dns_weight: int
    sni_weight: int
    asn_weight: int
    burst_weight: int

class UpdateEnforcementRequest(BaseModel):
    ipset_name_v4: str
    ip_timeout_seconds: int
    nft_table: str
    nft_chain: str

class UpdateCollectorsRequest(BaseModel):
    dnsmasq_log_path: str
    zeek_ssl_log_path: str
    use_zeek_sni: bool

class UpdateBurstRequest(BaseModel):
    dns_queries_per_minute_monitor: int
    dns_queries_per_minute_block: int
    
class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str
    sector: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    must_change_password: bool = True

class UpdateUserRequest(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    sector: Optional[str] = None
    full_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    new_password: str
    must_change_password: bool = True


@router.get("/")
def dashboard(request: Request):
    return dashboard_controller(request)

@router.get("/allow-domain")
def get_allow_domain(request: Request):
    return allow_domain_controller(request)

@router.post("/allow-domain")
def post_allow_domain(payload: AddDomainRequest):
    add_allow_domain(payload.domain)
    return {"message": "Domain added successfully"}

@router.put("/allow-domain")
def put_allow_domain(payload: UpdateDomainRequest):
    update_allow_domain(payload.old, payload.new)
    return {"message": "Domain updated successfully"}

@router.delete("/allow-domain")
def del_allow_domain(payload: DeleteDomainRequest):
    delete_allow_domain(payload.domain)
    return {"message": "Domain deleted successfully"}

# Deny IP routes
@router.get("/deny-ip")
def get_deny_ip(request: Request):
    return deny_ip_controller(request)

@router.post("/deny-ip")
def post_deny_ip(payload: AddIpRequest):
    add_deny_ip(payload.ip)
    return {"message": "IP address added successfully"}

@router.put("/deny-ip")
def put_deny_ip(payload: UpdateIpRequest):
    update_deny_ip(payload.old, payload.new)
    return {"message": "IP address updated successfully"}

@router.delete("/deny-ip")
def del_deny_ip(payload: DeleteIpRequest):
    delete_deny_ip(payload.ip)
    return {"message": "IP address deleted successfully"}


# Deny ASN routes
@router.get("/deny-asn")
def get_deny_asn(request: Request):
    return deny_asn_controller(request)

@router.post("/deny-asn")
def post_deny_asn(payload: AddAsnRequest):
    add_deny_asn(payload.asn)
    return {"message": "ASN added successfully"}

@router.put("/deny-asn")
def put_deny_asn(payload: UpdateAsnRequest):
    update_deny_asn(payload.old, payload.new)
    return {"message": "ASN updated successfully"}

@router.delete("/deny-asn")
def del_deny_asn(payload: DeleteAsnRequest):
    delete_deny_asn(payload.asn)
    return {"message": "ASN deleted successfully"}


# Deny Domain routes
@router.get("/deny-domain")
def get_deny_domain(request: Request):
    return deny_domain_controller(request)

@router.post("/deny-domain")
def post_deny_domain(payload: AddDenyDomainRequest):
    add_deny_domain(payload.domain)
    return {"message": "Domain added successfully"}

@router.put("/deny-domain")
def put_deny_domain(payload: UpdateDenyDomainRequest):
    update_deny_domain(payload.old, payload.new)
    return {"message": "Domain updated successfully"}

@router.delete("/deny-domain")
def del_deny_domain(payload: DeleteDenyDomainRequest):
    delete_deny_domain(payload.domain)
    return {"message": "Domain deleted successfully"}

# Events page
@router.get("/events")
def get_events(request: Request, current_user: User = Depends(get_current_user)):
    return events_controller(request)


# Events DataTables API
@router.get("/api/events")
def api_get_events(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    search_value: str = "",
    order_column: int = 0,
    order_dir: str = "desc"
):
    """API endpoint for DataTables server-side processing"""
    return events_datatable_controller(
        draw=draw,
        start=start,
        length=length,
        search_value=search_value,
        order_column=order_column,
        order_dir=order_dir
    )


# Events Download API
@router.get("/api/events/download")
def api_download_events(action_filter: str = "all"):
    """API endpoint for downloading events as Excel report"""
    return download_events_controller(action_filter)

# Policy Configuration routes
@router.get("/policy")
def get_policy(request: Request):
    return policy_controller(request)

@router.post("/policy/segment")
def post_segment(payload: AddSegmentRequest):
    add_segment_controller(payload.segment_name, payload.block_threshold, payload.monitor_threshold)
    return {"message": "Segment saved successfully"}

@router.delete("/policy/segment/{segment_name}")
def delete_segment(segment_name: str):
    delete_segment_controller(segment_name)
    return {"message": "Segment deleted successfully"}

@router.post("/policy/segment/subnets")
def post_segment_subnets(payload: UpdateSubnetsRequest):
    update_segment_subnets_controller(payload.segment_name, payload.subnets)
    return {"message": "Subnets updated successfully"}

@router.post("/policy/features")
def post_features(payload: UpdateFeaturesRequest):
    update_features_controller(payload.dns_weight, payload.sni_weight, payload.asn_weight, payload.burst_weight)
    return {"message": "Feature weights updated successfully"}

@router.post("/policy/enforcement")
def post_enforcement(payload: UpdateEnforcementRequest):
    update_enforcement_controller(payload.ipset_name_v4, payload.ip_timeout_seconds, payload.nft_table, payload.nft_chain)
    return {"message": "Enforcement configuration updated successfully"}

@router.post("/policy/collectors")
def post_collectors(payload: UpdateCollectorsRequest):
    update_collectors_controller(payload.dnsmasq_log_path, payload.zeek_ssl_log_path, payload.use_zeek_sni)
    return {"message": "Collectors configuration updated successfully"}

@router.post("/policy/burst")
def post_burst(payload: UpdateBurstRequest):
    update_burst_controller(payload.dns_queries_per_minute_monitor, payload.dns_queries_per_minute_block)
    return {"message": "Burst detection configuration updated successfully"}

# User Management Page
@router.get("/users")
def get_user_management_page(request: Request):
    """User management page (Super Admin only)"""
    return user_management_page_controller(request)

# Get Current User Info (for permission check)
@router.get("/api/auth/current-user")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return get_current_user_info_controller(current_user)

# Get All Users
@router.get("/api/users")
def get_all_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users (Super Admin only)"""
    return get_all_users_controller(db, current_user)

# Create User
@router.post("/api/users")
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new user (Super Admin only)"""
    return create_user_controller(
        db=db,
        current_user=current_user,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        sector=payload.sector,
        full_name=payload.full_name,
        department=payload.department,
        phone=payload.phone,
        must_change_password=payload.must_change_password
    )

# Update User
@router.put("/api/users/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user (Super Admin only)"""
    return update_user_controller(
        db=db,
        current_user=current_user,
        user_id=user_id,
        email=payload.email,
        role=payload.role,
        sector=payload.sector,
        full_name=payload.full_name,
        department=payload.department,
        phone=payload.phone,
        is_active=payload.is_active
    )

# Change User Password
@router.put("/api/users/{user_id}/password")
def change_user_password(
    user_id: int,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password (Super Admin only)"""
    return change_password_controller(
        db=db,
        current_user=current_user,
        user_id=user_id,
        new_password=payload.new_password,
        must_change_password=payload.must_change_password
    )

# Delete User
@router.delete("/api/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user (Super Admin only)"""
    return delete_user_controller(db, current_user, user_id)

# ============================================================
# AUDIT LOGS ROUTES
# ============================================================

@router.get("/audit-logs")
def get_audit_logs_page(request: Request):
    return audit_logs_page_controller(request)

@router.get("/api/audit/logs")
def get_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    severity: Optional[str] = None,
    username: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    return get_all_audit_logs_controller(
        db=db,
        current_user=current_user,
        limit=limit,
        offset=offset,
        action=action,
        severity=severity,
        username=username,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date
    )

@router.get("/api/audit/statistics")
def get_audit_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    days: int = 7
):
    return get_audit_statistics_controller(db, current_user, days)

@router.get("/api/audit/export")
def export_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    format: str = "json",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    return export_audit_logs_controller(db, current_user, format, start_date, end_date)


# ============================================================
# SECTOR LOCK ROUTES (Factory-Set Configuration)
# ============================================================

@router.get("/api/sector-lock")
def get_sector_lock_status():
    """
    Get the factory-set sector lock status.
    
    This endpoint returns the immutable sector configuration.
    The sector CANNOT be changed via the Admin UI.
    
    Returns:
        - sector: Current sector (school, hospital, government, finance, legal, establishment)
        - locked: Always True (factory-set)
        - config: Sector-specific policy configuration
        - description: Human-readable sector description
    """
    try:
        from app.minifw_ai.sector_lock import get_sector_lock
        
        lock = get_sector_lock()
        config = lock.get_sector_config()
        
        return {
            "success": True,
            "sector": lock.get_sector(),
            "locked": True,  # Always locked - factory-set
            "description": config.get("description", "Factory-set sector"),
            "config": {
                # Only expose safe-to-display config items
                "force_safesearch": config.get("force_safesearch", False),
                "block_vpns": config.get("block_vpns", False),
                "iomt_high_priority": config.get("iomt_high_priority", False),
                "block_tor": config.get("block_tor", False),
                "geo_ip_strict": config.get("geo_ip_strict", False),
                "data_exfiltration_watch": config.get("data_exfiltration_watch", False),
                "extra_feeds": config.get("extra_feeds", []),
            },
            "message": "Sector is factory-set and cannot be modified via UI"
        }
    except RuntimeError as e:
        return {
            "success": False,
            "sector": "unknown",
            "locked": False,
            "error": str(e),
            "message": "Sector not configured - device may be unprovisioned"
        }
    except ImportError:
        return {
            "success": False,
            "sector": "unknown", 
            "locked": False,
            "error": "Sector lock module not available",
            "message": "Sector lock system not installed"
        }