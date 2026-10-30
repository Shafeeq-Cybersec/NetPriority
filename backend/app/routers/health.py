"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Return backend health status and the current server timestamp."""
    return {
        "status": "healthy",
        "service": "NetPriority Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
