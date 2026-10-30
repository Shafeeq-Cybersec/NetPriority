"""Project information endpoint."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["info"])


@router.get("/")
def get_project_info() -> dict:
    """Return basic project information describing the NetPriority service."""
    return {
        "name": settings.PROJECT_NAME,
        "description": settings.PROJECT_DESCRIPTION,
        "version": settings.VERSION,
        "status": "running",
    }
