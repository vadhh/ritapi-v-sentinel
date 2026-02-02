from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.services.deny_ip.get_deny_ips_service import get_deny_ips
from app.services.deny_ip.add_deny_ip_service import add_deny_ip_service
from app.services.deny_ip.update_deny_ip_service import update_deny_ip_service
from app.services.deny_ip.delete_deny_ip_service import delete_deny_ip_service

templates = Jinja2Templates(directory="app/web/templates")


def deny_ip_controller(request: Request):
    ips = get_deny_ips()

    return templates.TemplateResponse(
        "admin/deny_ip.html",
        {
            "request": request,
            "ips": ips,
            "user": {"name": "Fahrezi"},
        }
    )

def add_deny_ip(ip: str):
    try:
        add_deny_ip_service(ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def update_deny_ip(old_ip: str, new_ip: str):
    try:
        update_deny_ip_service(old_ip, new_ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def delete_deny_ip(ip: str):
    try:
        delete_deny_ip_service(ip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))