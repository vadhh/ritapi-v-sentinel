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