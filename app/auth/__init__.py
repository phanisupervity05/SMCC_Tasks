# app/auth/__init__.py
"""
Pluggable auth layer.

AUTH_PROVIDER selects how a bearer token becomes a user:
    keycloak  (default)  Keycloak SSO
    dev_mock             dev-only mock login, see dev_mock_provider.py

Add another provider by subclassing AuthProvider and registering it below.
"""

import os
from functools import lru_cache

from .base import AuthProvider
from .service_token import require_intake_token, require_output_token


@lru_cache(maxsize=1)
def get_auth_provider() -> AuthProvider:
    name = os.getenv("AUTH_PROVIDER", "keycloak").lower()
    if name == "keycloak":
        from .keycloak_provider import KeycloakProvider

        return KeycloakProvider()
    if name == "dev_mock":  # DEV ONLY
        from .dev_mock_provider import DevMockProvider

        return DevMockProvider()
    raise RuntimeError(f"Unknown AUTH_PROVIDER '{name}'")


__all__ = [
    "AuthProvider",
    "get_auth_provider",
    "require_intake_token",
    "require_output_token",
]
