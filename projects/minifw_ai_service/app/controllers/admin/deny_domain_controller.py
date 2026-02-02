from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates

from app.services.deny_domain.get_deny_domains_service import get_deny_domains
from app.services.deny_domain.add_deny_domain_service import add_deny_domain_service
from app.services.deny_domain.update_deny_domain_service import update_deny_domain_service
from app.services.deny_domain.delete_deny_domain_service import delete_deny_domain_service

templates = Jinja2Templates(directory="app/web/templates")


def deny_domain_controller(request: Request):
    domains = get_deny_domains()

    return templates.TemplateResponse(
        "admin/deny_domain.html",
        {
            "request": request,
            "domains": domains,
            "user": {"name": "Fahrezi"},
        }
    )

def add_deny_domain(domain: str):
    try:
        add_deny_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def update_deny_domain(old_domain: str, new_domain: str):
    try:
        update_deny_domain_service(old_domain, new_domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

def delete_deny_domain(domain: str):
    try:
        delete_deny_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))