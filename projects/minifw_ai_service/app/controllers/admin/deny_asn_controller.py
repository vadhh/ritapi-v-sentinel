from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.services.deny_asn.get_deny_asns_service import get_deny_asns
from app.services.deny_asn.add_deny_asn_service import add_deny_asn_service
from app.services.deny_asn.update_deny_asn_service import update_deny_asn_service
from app.services.deny_asn.delete_deny_asn_service import delete_deny_asn_service

templates = Jinja2Templates(directory="app/web/templates")


def deny_asn_controller(request: Request):
    asns = get_deny_asns()

    return templates.TemplateResponse(
        "admin/deny_asn.html",
        {
            "request": request,
            "asns": asns,
            "user": {"name": "Fahrezi"},
        }
    )

def add_deny_asn(asn: str):
    try:
        add_deny_asn_service(asn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def update_deny_asn(old_asn: str, new_asn: str):
    try:
        update_deny_asn_service(old_asn, new_asn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def delete_deny_asn(asn: str):
    try:
        delete_deny_asn_service(asn)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))