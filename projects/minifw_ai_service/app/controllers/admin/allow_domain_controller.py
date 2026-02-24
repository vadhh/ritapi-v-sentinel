from fastapi import Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.rbac_service import RBACService

from app.services.allow_domain.get_allow_domains_service import get_allow_domains
from app.services.allow_domain.add_allow_domain_service import add_allow_domain_service
from app.services.allow_domain.update_allow_domain_service import (
    update_allow_domain_service,
)
from app.services.allow_domain.delete_allow_domain_service import (
    delete_allow_domain_service,
)

templates = Jinja2Templates(directory="app/web/templates")


def allow_domain_controller(request: Request):
    domains = get_allow_domains()

    return templates.TemplateResponse(
        "admin/allow_domain.html",
        {
            "request": request,
            "domains": domains,
            "user": {"name": "Fahrezi"},
        },
    )


def add_allow_domain(current_user: User, db: Session, domain: str):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "add allow-list domains"
    )
    try:
        add_allow_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def update_allow_domain(
    current_user: User, db: Session, old_domain: str, new_domain: str
):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "update allow-list domains"
    )
    try:
        update_allow_domain_service(old_domain, new_domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def delete_allow_domain(current_user: User, db: Session, domain: str):
    RBACService(db).check_permission(
        current_user, UserRole.ADMIN, "delete allow-list domains"
    )
    try:
        delete_allow_domain_service(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
