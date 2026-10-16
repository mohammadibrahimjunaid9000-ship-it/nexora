"""
Nexora API - Routes Package
"""

from api.app.routes.auth import router as auth_router
from api.app.routes.users import router as users_router
from api.app.routes.courses import router as courses_router
from api.app.routes.enrollments import router as enrollments_router

__all__ = ["auth_router", "users_router", "courses_router", "enrollments_router"]
