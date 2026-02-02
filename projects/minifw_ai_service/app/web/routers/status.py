from fastapi import APIRouter
from app.minifw_ai import policy, events

router = APIRouter()

@router.get("/")
def system_status():
    return {
        "policy_loaded": True,
        "events_active": True
    }
