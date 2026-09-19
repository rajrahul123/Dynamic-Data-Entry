"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth_router,
    forms_router,
    health_router,
    records_router,
    submissions_router,
    users_router,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description="Generic dynamic data-entry platform API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(users_router, prefix="/api", tags=["users"])
app.include_router(forms_router, prefix="/api", tags=["forms"])
app.include_router(submissions_router, prefix="/api", tags=["submissions"])
app.include_router(records_router, prefix="/api", tags=["records"])


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
        "login": "/api/auth/login",
        "me": "/api/auth/me",
        "forms": "/api/forms",
    }