from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.rbac_service import RBACService

from app.services.deny_domain.get_deny_domains_service import get_deny_domains
from app.services.deny_domain.add_deny_domain_service import add_deny_domain_service
from app.services.deny_domain.update_deny_domain_service import (
    update_deny_domain_service,
)
from app.services.deny_domain.delete_deny_domain_service import (
    delete_deny_domain_service,
)

templates = Jinja2Templates(directory="app/web/templates")


def deny_domain_controller(request: Request):
    domains = get_deny_domains()

    return templates.TemplateResponse(
        "admin/deny_domain.html",
        {
            "request": request,
            "domains": domains,
            "user": {"name": "Fahrezi"},
        },
    )


def add_deny_domain(current_user: User, db: Session, domain: str):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "add deny-list domains"
    )
    try:
        add_deny_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_deny_domain(
    current_user: User, db: Session, old_domain: str, new_domain: str
):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "update deny-list domains"
    )
    try:
        update_deny_domain_service(old_domain, new_domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def delete_deny_domain(current_user: User, db: Session, domain: str):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "delete deny-list domains"
    )
    try:
        delete_deny_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
