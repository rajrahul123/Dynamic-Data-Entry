"""FastAPI application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api import (
    auth_router,
    billing_router,
    forms_router,
    health_router,
    records_router,
    submissions_router,
    subscriptions_router,
    users_router,
)
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.api_version,
    description="Generic dynamic data-entry platform API.",
)

app.state.limiter = limiter


async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clear 429 with rate-limit headers for throttled endpoints."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": (
                "Too many requests. Please slow down and try again later "
                f"(limit: {exc.detail})."
            )
        },
    )
    response = limiter._inject_headers(response, request.state.view_rate_limit)
    return response


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(subscriptions_router, prefix="/api", tags=["subscription"])
app.include_router(billing_router, prefix="/api", tags=["billing"])


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