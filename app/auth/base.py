# app/auth/base.py
"""
Pluggable auth layer: the provider contract.

An AuthProvider turns a bearer token into a claims dict shaped like the
Keycloak introspection result (sub, preferred_username, email, name,
realm_access.roles). The authorization engine (authz.py) only needs that shape,
so any provider that returns it can be swapped in with AUTH_PROVIDER=<name>.
"""

from abc import ABC, abstractmethod

from fastapi import HTTPException, status


def unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


class AuthProvider(ABC):
    name: str = "base"

    @abstractmethod
    def authenticate(self, token: str) -> dict:
        """Return the user's claims, or raise an HTTP 401. Never log the token."""
