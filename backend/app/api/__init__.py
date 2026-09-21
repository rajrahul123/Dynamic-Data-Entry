from app.api.routes.auth import router as auth_router
from app.api.routes.forms import router as forms_router
from app.api.routes.health import router as health_router
from app.api.routes.records import router as records_router
from app.api.routes.submissions import router as submissions_router
from app.api.routes.subscriptions import billing_router, router as subscriptions_router
from app.api.routes.users import router as users_router

__all__ = [
    "auth_router",
    "billing_router",
    "forms_router",
    "health_router",
    "records_router",
    "submissions_router",
    "subscriptions_router",
    "users_router",
]