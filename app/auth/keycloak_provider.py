# app/auth/keycloak_provider.py
"""
Keycloak SSO provider (production path).

This is the template's original validation logic (JWKS signature check, then
back-channel introspection), moved here unchanged so that security.py can
delegate to whichever provider is configured.
"""

import logging
import os
from functools import lru_cache

import requests
from fastapi import HTTPException, status
from jose import JWTError, jwt

from .base import AuthProvider, unauthorized

log = logging.getLogger(__name__)


def _cfg() -> dict:
    server = (os.getenv("KEYCLOAK_SERVER_URL") or "").rstrip("/")
    return {
        "server": server,
        "realm": os.getenv("KEYCLOAK_REALM"),
        "audience": os.getenv("KEYCLOAK_AUDIENCE"),
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
        "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
    }


def _urls() -> tuple[str, str]:
    c = _cfg()
    if not c["server"] or not c["realm"]:
        raise ValueError(
            "Keycloak configuration is incomplete. "
            "Set KEYCLOAK_SERVER_URL and KEYCLOAK_REALM environment variables."
        )
    base = f"{c['server']}/realms/{c['realm']}/protocol/openid-connect"
    return f"{base}/certs", f"{base}/token/introspect"


@lru_cache(maxsize=1)
def get_jwks():
    jwks_url, _ = _urls()
    log.info(f"Fetching JWKS from: {jwks_url}")
    try:
        response = requests.get(jwks_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Could not fetch JWKS from Keycloak: {e}")


def introspect_token(token: str) -> dict:
    _, introspection_url = _urls()
    c = _cfg()
    payload = {
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "token": token,
    }
    try:
        response = requests.post(introspection_url, data=payload)
        response.raise_for_status()
        result = response.json()
        if not result.get("active"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is not active"
            )
        return result
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token introspection failed: {e}",
        )


class KeycloakProvider(AuthProvider):
    name = "keycloak"

    def authenticate(self, token: str) -> dict:
        c = _cfg()
        try:
            header = jwt.get_unverified_header(token)
            jwks = get_jwks()
            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == header["kid"]:
                    rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
                    break
            if not rsa_key:
                raise unauthorized()

            jwt.decode(
                token,
                rsa_key,
                algorithms=[header["alg"]],
                audience=c["audience"],
                issuer=f"{c['server']}/realms/{c['realm']}",
            )
            return introspect_token(token)
        except JWTError as e:
            log.warning(f"JWT validation error: {e}")
            raise unauthorized()
