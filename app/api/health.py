from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["system"])

@router.get("/health")
async def health():
    return {"status":"ok","service":"PocketPilot","demo_only":settings.demo_only}
