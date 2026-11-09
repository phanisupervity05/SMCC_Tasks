# app/routers/auth.py
"""
Authentication and registration endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import UserRegistration, UserRegistrationResponse
from ..security import get_current_user
from ..services.keycloak_admin import keycloak_admin
from .admin import validate_password_strength

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserRegistrationResponse)
async def register_user(registration: UserRegistration):
    """
    Register a new user.

    - Users from approved domains (e.g., @supervity.ai) get instant access with 'user' role.
    - Users from other domains get 'pending' role and require admin approval.
    - All users receive an email verification link.

    This endpoint is public (defined in public.map.json).
    """
    # Validate password strength
    is_valid, error_msg = validate_password_strength(registration.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        result = await keycloak_admin.create_user(
            email=registration.email,
            password=registration.password,
            first_name=registration.first_name,
            last_name=registration.last_name,
            email_verified=False,
        )

        if result["requires_approval"]:
            message = (
                "Registration successful! Your account is pending admin approval. "
                "You will be notified once your access is granted."
            )
        else:
            message = (
                "Registration successful! You now have full access. "
                "You can sign in with your credentials."
            )

        return UserRegistrationResponse(
            user_id=result["user_id"],
            email=result["email"],
            role=result["role"],
            requires_approval=result["requires_approval"],
            message=message,
        )
    except Exception as e:
        log.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/pending-status")
async def get_pending_status(user: dict = Depends(get_current_user)):
    """
    Check if the current user is pending approval.
    Returns the user's status and whether they need admin approval.
    """
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    roles = user.get("realm_access", {}).get("roles", [])
    is_pending = "pending" in roles and "user" not in roles and "admin" not in roles

    return {
        "is_pending": is_pending,
        "roles": roles,
        "message": "Your account is awaiting admin approval."
        if is_pending
        else "Your account is active.",
    }

