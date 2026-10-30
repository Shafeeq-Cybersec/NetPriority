"""Application configuration for the NetPriority backend.

Keeps project metadata and CORS settings in one place so the rest of the
application can import a single `settings` instance.
"""


class Settings:
    """Central configuration. Edit values here to change app behavior."""

    PROJECT_NAME = "NetPriority"
    PROJECT_DESCRIPTION = (
        "NetPriority is a Quality of Service (QoS) network priority "
        "management system. This starter interface verifies the connection "
        "between the React frontend and the FastAPI backend before the full "
        "QoS traffic-control system is built."
    )
    VERSION = "0.1.0"

    # Origins allowed to call the API. Vite dev server runs on 5173.
    BACKEND_CORS_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


settings = Settings()
