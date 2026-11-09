# app/security.py
import json
import logging
import os
import re

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from .auth import get_auth_provider
from .authz import AuthzEngine

# --- Logger Setup ---
log = logging.getLogger(__name__)

IS_AUTH_DEBUG = os.getenv("SUPERVITY_AUTH_DEBUG", "false").lower() == "true"

# Token validation is delegated to the configured auth provider
# (AUTH_PROVIDER=keycloak | dev_mock). See app/auth/.

# auto_error=False is critical. It makes the "Authorization" header optional.
# This allows the same dependency (`verify_access`) to process requests for
# both public and protected routes without immediately failing if a token is not present.
# The decision to require a token is deferred to the authorization engine.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# --- Singleton Engine Instance ---
# We create one instance of the engine when the application starts.
# This is efficient as policies are loaded from disk only once.
# This instance is imported by main.py for manual, context-aware checks.
authz_engine = AuthzEngine()


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict | None:
    """
    This is the primary AUTHENTICATION dependency.
    Its only job is to validate the token (via the configured provider) and
    return its claims. It does NOT perform any authorization.
    """
    if token is None:
        return None
    return get_auth_provider().authenticate(token)


def verify_access(
    request: Request, current_user: dict | None = Depends(get_current_user)
):
    """
    This is the global AUTHORIZATION dependency, applied to the main router.
    It acts as a "first pass" filter. It automatically protects simple endpoints.
    If it detects a rule that requires runtime context, it "steps aside" and lets the
    endpoint perform the check manually.
    """
    request_path = request.url.path

    # Dynamically get the base_path from the environment (same as in authz.py)
    base_path = os.getenv("BASE_PATH", "")

    # Check if the path is whitelisted as public (same logic as AuthzEngine.check)
    if any(
        re.fullmatch(f"{base_path}{p}", request_path)
        for p in authz_engine._public_paths
    ):
        return

    for rule_path, rule in authz_engine._authz_rules.items():
        # Construct the full, expected path from the base_path and the rule key (same as in authz.py)
        full_rule_path = f"{base_path}{rule_path}"
        if re.fullmatch(full_rule_path, request_path):
            rule_str = json.dumps(rule)
            # If the rule contains placeholders, it's a "context-aware" rule.
            # Its logic depends on runtime data (e.g., the owner of a document).
            # We cannot decide now, so we "step aside" and delegate the final check
            # to the endpoint function, which is responsible for fetching the data
            # and building the context.
            if "{context" in rule_str or "{path" in rule_str:
                if IS_AUTH_DEBUG:
                    log.debug(
                        f"Rule for '{request_path}' requires context. Deferring check to endpoint."
                    )
                return
            else:
                # This is a "simple" rule that only depends on the user's token (e.g., roles).
                # The engine has all the information it needs, so it can make the final
                # authorization decision right now, before the endpoint code is ever executed.
                if IS_AUTH_DEBUG:
                    log.debug(
                        f"Performing automatic check for simple rule at '{request_path}'."
                    )
                authz_engine.check(request, current_user)
                return

    # If the path is not public and no rule is found, deny access by default.
    if current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this resource is not configured in authz.map.",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
