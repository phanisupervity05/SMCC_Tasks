# app/routers/__init__.py
"""
API Routers - Modular endpoint organization.

Note: File endpoints are defined in main.py to maintain proper path ordering.
"""

from .admin import router as admin_router
from .ai import router as ai_router
from .audit import router as audit_router
from .calls import router as calls_router
from .auth import router as auth_router
from .examples import router as examples_router
from .health import router as health_router
from .items import router as items_router
from .webhooks import router as webhooks_router

__all__ = [
    "health_router",
    "auth_router",
    "admin_router",
    "ai_router",
    "audit_router",
    "items_router",
    "examples_router",
    "calls_router",
    "webhooks_router",
]

