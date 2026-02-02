from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/web/templates")


def events_controller(request: Request):
    """
    Events/Logs controller
    Shows real-time security events page
    """
    return templates.TemplateResponse(
        "admin/events.html",
        {
            "request": request,
            "user": {"name": "Fahrezi"}
        }
    )