from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }
