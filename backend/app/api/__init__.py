from app.api.routes.auth import router as auth_router
from app.api.routes.forms import router as forms_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router

__all__ = ["auth_router", "forms_router", "health_router", "users_router"]