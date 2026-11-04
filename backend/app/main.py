"""FastAPI application entry point.

Run from the `backend` directory with:
    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import flows, health, info, qos

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
)

# Allow the Vite dev server (http://localhost:5173) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(info.router)
app.include_router(health.router)
app.include_router(flows.router)  # Phase 1 — traffic classifier
app.include_router(qos.router)    # Phase 1 — QoS marking policy
