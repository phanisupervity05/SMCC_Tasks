# app/auth/dev_mock_provider.py
"""
=============================================================================
DEV-ONLY MOCK LOGIN.  NOT FOR PRODUCTION.
=============================================================================
Stands in for Keycloak SSO while no realm is available. It is active only when
BOTH are set:

    AUTH_PROVIDER=dev_mock
    DEV_AUTH_ENABLED=true

and it refuses to load at all when APP_ENV=production.

How it works: the frontend's dev sign-in (see frontend/src/lib/auth) issues a
token of the form  devmock.<base64url(claims json)>.<hex hmac-sha256>  signed
with DEV_AUTH_SECRET. This provider checks the signature and expiry and returns
the claims. Without DEV_AUTH_SECRET nothing can be authenticated.

To remove: delete this file, the DEV_AUTH_* lines in .env.example, the
credentials provider in frontend/src/lib/auth/dev-mock.ts, and the dev branch
in app/auth/__init__.py.
=============================================================================
"""

import base64
import hashlib
import hmac
import json
import os
import time

from .base import AuthProvider, unauthorized

PREFIX = "devmock"


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class DevMockProvider(AuthProvider):
    name = "dev_mock"

    def __init__(self) -> None:
        if os.getenv("APP_ENV", "development").lower() == "production":
            raise RuntimeError("The dev_mock auth provider must not run in production.")
        if os.getenv("DEV_AUTH_ENABLED", "false").lower() != "true":
            raise RuntimeError("dev_mock auth requires DEV_AUTH_ENABLED=true.")

    def authenticate(self, token: str) -> dict:
        secret = os.getenv("DEV_AUTH_SECRET", "")
        if not secret:
            raise unauthorized("Dev auth is not configured (DEV_AUTH_SECRET is empty).")
        try:
            prefix, payload, sig = token.split(".")
        except ValueError:
            raise unauthorized()
        if prefix != PREFIX:
            raise unauthorized()
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            raise unauthorized()
        try:
            claims = json.loads(_b64d(payload))
        except Exception:
            raise unauthorized()
        if not isinstance(claims, dict) or not claims.get("sub"):
            raise unauthorized()
        if claims.get("exp") and claims["exp"] < time.time():
            raise unauthorized("Token expired")
        return claims
