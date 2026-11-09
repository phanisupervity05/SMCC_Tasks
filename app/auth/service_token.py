# app/auth/service_token.py
"""
Shared-secret token check for the two webhook routes (machine to machine).

    INTAKE_WEBHOOK_TOKEN   protects POST /api/webhooks/intake
    OUTPUT_WEBHOOK_TOKEN   protects POST /api/webhooks/output

The token is read from the "X-Webhook-Token" header only. (Not from
"Authorization: Bearer": the global user-login check runs first on every /api
route and would try to read a service token as a user JWT.)
A missing, wrong, or unconfigured token returns 401 before the body is read, so
nothing is saved. Token values are never logged.
"""

import hmac
import logging
import os

from fastapi import HTTPException, Request, status

log = logging.getLogger(__name__)


def _presented_token(request: Request) -> str:
    return (request.headers.get("x-webhook-token") or "").strip()


def _make_dependency(env_name: str):
    def dependency(request: Request) -> None:
        expected = os.getenv(env_name, "")
        if not expected:
            # Fail closed: an unconfigured token never lets anyone in.
            log.warning("%s is not configured; rejecting webhook call", env_name)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )
        presented = _presented_token(request)
        if not presented or not hmac.compare_digest(
            presented.encode(), expected.encode()
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return dependency


require_intake_token = _make_dependency("INTAKE_WEBHOOK_TOKEN")
require_output_token = _make_dependency("OUTPUT_WEBHOOK_TOKEN")
