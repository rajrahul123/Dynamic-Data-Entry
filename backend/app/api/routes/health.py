"""Health check endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_database

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]
    api_version: str
    environment: str
    database: Literal["connected", "unavailable", "not_configured"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    db_status = check_database()
    database: str = (
        "not_configured"
        if db_status is None
        else "connected"
        if db_status
        else "unavailable"
    )
    return HealthResponse(
        status="ok",
        api_version=settings.api_version,
        environment=settings.environment,
        database=database,
    )