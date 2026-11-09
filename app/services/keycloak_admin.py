# app/services/keycloak_admin.py
"""
Keycloak Admin API Service

Provides methods for interacting with Keycloak Admin REST API for user management,
role assignment, and other administrative operations.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# Configuration
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "supervity")
KEYCLOAK_ADMIN_USERNAME = os.getenv("KEYCLOAK_ADMIN_USERNAME", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")


def get_approved_domains() -> list[str]:
    """
    Returns list of approved email domains that get instant 'user' role.
    Reads from environment variable dynamically (updated by admin settings).
    """
    # Read dynamically to pick up changes from admin settings
    domains_str = os.getenv("APPROVED_EMAIL_DOMAINS", "supervity.ai")
    return [d.strip().lower() for d in domains_str.split(",") if d.strip()]


def is_approved_domain(email: str) -> bool:
    """Check if email belongs to an approved domain."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[1].lower()
    return domain in get_approved_domains()


class KeycloakAdminService:
    """
    Service class for Keycloak Admin REST API operations.

    Provides methods for:
    - User creation and management
    - Role assignment and removal
    - User approval workflow
    """

    def __init__(self):
        self._admin_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    @property
    def admin_api_url(self) -> str:
        """Base URL for Keycloak Admin API."""
        return f"{KEYCLOAK_SERVER_URL}/admin/realms/{KEYCLOAK_REALM}"

    async def _get_admin_token(self) -> str:
        """
        Get an admin access token for Keycloak Admin API.
        Uses password grant with the master realm's admin-cli client.
        Admin users authenticate through the master realm.
        Caches the token until it expires.
        """
        # Check if we have a valid cached token
        if self._admin_token and self._token_expiry:
            if datetime.utcnow() < self._token_expiry - timedelta(seconds=30):
                return self._admin_token

        # Admin authentication happens through the master realm
        token_url = f"{KEYCLOAK_SERVER_URL}/realms/master/protocol/openid-connect/token"

        async with httpx.AsyncClient() as client:
            # Use password grant with admin-cli client (always available in master realm)
            data = {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": KEYCLOAK_ADMIN_USERNAME,
                "password": KEYCLOAK_ADMIN_PASSWORD,
            }

            response = await client.post(token_url, data=data)

            if response.status_code != 200:
                log.error(f"Failed to get admin token: {response.text}")
                raise Exception(f"Failed to authenticate with Keycloak: {response.text}")

            token_data = response.json()
            self._admin_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 300)
            self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)

            return self._admin_token

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> httpx.Response:
        """Make an authenticated request to Keycloak Admin API."""
        token = await self._get_admin_token()
        url = f"{self.admin_api_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
            )

            return response

    async def create_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        email_verified: bool = False,
    ) -> dict:
        """
        Create a new user in Keycloak.

        Args:
            email: User's email (also used as username)
            password: User's password
            first_name: User's first name
            last_name: User's last name
            email_verified: Whether the email is pre-verified

        Returns:
            dict with user_id and role assigned

        Raises:
            Exception if user creation fails
        """
        user_data = {
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": email_verified,
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": False,
                }
            ],
        }

        response = await self._make_request("POST", "/users", json_data=user_data)

        if response.status_code == 409:
            raise Exception("A user with this email already exists")

        if response.status_code != 201:
            log.error(f"Failed to create user: {response.text}")
            raise Exception(f"Failed to create user: {response.text}")

        # Get the user ID from the Location header
        location = response.headers.get("Location", "")
        user_id = location.split("/")[-1]

        # Determine role based on email domain
        role_to_assign = "user" if is_approved_domain(email) else "pending"

        # Assign the appropriate role
        await self.assign_role(user_id, role_to_assign)

        # Note: Email verification is disabled (no SMTP configured)
        # Users are created with emailVerified=False but don't receive verification emails
        # Admins can manually verify users if needed

        return {
            "user_id": user_id,
            "email": email,
            "role": role_to_assign,
            "requires_approval": role_to_assign == "pending",
        }

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Get a user by their ID."""
        response = await self._make_request("GET", f"/users/{user_id}")

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise Exception(f"Failed to get user: {response.text}")

        return response.json()

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get a user by their email address."""
        response = await self._make_request("GET", "/users", params={"email": email, "exact": "true"})

        if response.status_code != 200:
            raise Exception(f"Failed to search users: {response.text}")

        users = response.json()
        return users[0] if users else None

    async def get_all_users(
        self,
        first: int = 0,
        max_results: int = 100,
    ) -> list[dict]:
        """Get all users with pagination."""
        response = await self._make_request(
            "GET", "/users", params={"first": first, "max": max_results}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get users: {response.text}")

        return response.json()

    async def get_user_roles(self, user_id: str) -> list[dict]:
        """Get all realm roles assigned to a user."""
        response = await self._make_request("GET", f"/users/{user_id}/role-mappings/realm")

        if response.status_code != 200:
            raise Exception(f"Failed to get user roles: {response.text}")

        return response.json()

    async def get_users_by_role(self, role_name: str) -> list[dict]:
        """Get all users who have a specific role."""
        # First, get the role to get its ID
        role = await self._get_role(role_name)
        if not role:
            return []

        response = await self._make_request("GET", f"/roles/{role_name}/users")

        if response.status_code != 200:
            raise Exception(f"Failed to get users by role: {response.text}")

        return response.json()

    async def _get_role(self, role_name: str) -> Optional[dict]:
        """Get a realm role by name."""
        response = await self._make_request("GET", f"/roles/{role_name}")

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise Exception(f"Failed to get role: {response.text}")

        return response.json()

    # =========================================================================
    # ROLE MANAGEMENT
    # =========================================================================

    async def get_all_roles(self) -> list[dict]:
        """Get all realm roles."""
        response = await self._make_request("GET", "/roles")

        if response.status_code != 200:
            raise Exception(f"Failed to get roles: {response.text}")

        return response.json()

    async def get_role_by_name(self, role_name: str) -> Optional[dict]:
        """Get a realm role by name (public wrapper for _get_role)."""
        return await self._get_role(role_name)

    async def create_role(
        self,
        name: str,
        description: str = "",
        composite: bool = False,
    ) -> dict:
        """
        Create a new realm role.

        Args:
            name: Role name (must be unique)
            description: Optional description for the role
            composite: Whether this role can contain other roles

        Returns:
            dict with role info
        """
        role_data = {
            "name": name,
            "description": description,
            "composite": composite,
        }

        response = await self._make_request("POST", "/roles", json_data=role_data)

        if response.status_code == 409:
            raise Exception(f"A role with name '{name}' already exists")

        if response.status_code != 201:
            log.error(f"Failed to create role: {response.text}")
            raise Exception(f"Failed to create role: {response.text}")

        # Get the created role to return its details
        created_role = await self._get_role(name)
        return created_role or {"name": name, "description": description}

    async def update_role(
        self,
        role_name: str,
        description: Optional[str] = None,
    ) -> dict:
        """
        Update a realm role's description.

        Args:
            role_name: The name of the role to update
            description: New description for the role

        Returns:
            dict with updated role info
        """
        role = await self._get_role(role_name)
        if not role:
            raise Exception(f"Role '{role_name}' not found")

        update_data = {"name": role_name}
        if description is not None:
            update_data["description"] = description

        response = await self._make_request(
            "PUT", f"/roles/{role_name}", json_data=update_data
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to update role: {response.text}")

        return await self._get_role(role_name) or update_data

    async def delete_role(self, role_name: str) -> bool:
        """
        Delete a realm role.

        Args:
            role_name: The name of the role to delete

        Returns:
            True if successful
        """
        # Don't allow deleting system roles
        system_roles = ["admin", "user", "pending", "offline_access", "uma_authorization", "default-roles-supervity"]
        if role_name in system_roles:
            raise Exception(f"Cannot delete system role '{role_name}'")

        response = await self._make_request("DELETE", f"/roles/{role_name}")

        if response.status_code == 404:
            raise Exception(f"Role '{role_name}' not found")

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to delete role: {response.text}")

        log.info(f"Deleted role '{role_name}'")
        return True

    async def get_role_users_count(self, role_name: str) -> int:
        """Get count of users with a specific role."""
        try:
            users = await self.get_users_by_role(role_name)
            return len(users)
        except Exception:
            return 0

    async def get_roles_with_user_counts(self) -> list[dict]:
        """
        Get all roles with their user counts.
        This is a convenience method for the admin UI.
        """
        roles = await self.get_all_roles()

        enriched_roles = []
        for role in roles:
            try:
                user_count = await self.get_role_users_count(role["name"])
                role["userCount"] = user_count
            except Exception:
                role["userCount"] = 0
            enriched_roles.append(role)

        return enriched_roles

    async def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a realm role to a user."""
        role = await self._get_role(role_name)
        if not role:
            raise Exception(f"Role '{role_name}' not found")

        response = await self._make_request(
            "POST",
            f"/users/{user_id}/role-mappings/realm",
            json_data=[role],
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to assign role: {response.text}")

        log.info(f"Assigned role '{role_name}' to user {user_id}")
        return True

    async def remove_role(self, user_id: str, role_name: str) -> bool:
        """Remove a realm role from a user."""
        role = await self._get_role(role_name)
        if not role:
            raise Exception(f"Role '{role_name}' not found")

        response = await self._make_request(
            "DELETE",
            f"/users/{user_id}/role-mappings/realm",
            json_data=[role],
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to remove role: {response.text}")

        log.info(f"Removed role '{role_name}' from user {user_id}")
        return True

    async def approve_user(self, user_id: str) -> bool:
        """
        Approve a pending user by changing their role from 'pending' to 'user'.
        """
        # Remove pending role
        try:
            await self.remove_role(user_id, "pending")
        except Exception as e:
            log.warning(f"Could not remove pending role: {e}")

        # Assign user role
        await self.assign_role(user_id, "user")

        log.info(f"Approved user {user_id}")
        return True

    async def reject_user(self, user_id: str, disable: bool = True) -> bool:
        """
        Reject a pending user. By default, disables their account.

        Args:
            user_id: The user's Keycloak ID
            disable: If True, disables the account. If False, deletes it.
        """
        if disable:
            await self.disable_user(user_id)
        else:
            await self.delete_user(user_id)

        log.info(f"Rejected user {user_id} (disabled={disable})")
        return True

    async def enable_user(self, user_id: str) -> bool:
        """Enable a user account."""
        response = await self._make_request(
            "PUT",
            f"/users/{user_id}",
            json_data={"enabled": True},
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to enable user: {response.text}")

        return True

    async def disable_user(self, user_id: str) -> bool:
        """Disable a user account."""
        response = await self._make_request(
            "PUT",
            f"/users/{user_id}",
            json_data={"enabled": False},
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to disable user: {response.text}")

        return True

    async def delete_user(self, user_id: str) -> bool:
        """Permanently delete a user."""
        response = await self._make_request("DELETE", f"/users/{user_id}")

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to delete user: {response.text}")

        return True

    async def send_verify_email(self, user_id: str) -> bool:
        """Send email verification to a user."""
        response = await self._make_request(
            "PUT",
            f"/users/{user_id}/send-verify-email",
        )

        if response.status_code not in [200, 204]:
            log.warning(f"Failed to send verification email: {response.text}")
            return False

        return True

    async def send_password_reset_email(self, user_id: str) -> bool:
        """Send password reset email to a user."""
        response = await self._make_request(
            "PUT",
            f"/users/{user_id}/execute-actions-email",
            json_data=["UPDATE_PASSWORD"],
        )

        if response.status_code not in [200, 204]:
            log.warning(f"Failed to send password reset email: {response.text}")
            return False

        return True

    async def create_user_by_admin(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        temporary_password: bool = True,
    ) -> dict:
        """
        Create a new user (admin mode - doesn't auto-assign role based on domain).

        Args:
            email: User's email (also used as username)
            password: User's password
            first_name: User's first name
            last_name: User's last name
            temporary_password: If True, user must change password on first login

        Returns:
            dict with user_id
        """
        user_data = {
            "username": email,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": False,
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": temporary_password,
                }
            ],
        }

        response = await self._make_request("POST", "/users", json_data=user_data)

        if response.status_code == 409:
            raise Exception("A user with this email already exists")

        if response.status_code != 201:
            log.error(f"Failed to create user: {response.text}")
            raise Exception(f"Failed to create user: {response.text}")

        # Get the user ID from the Location header
        location = response.headers.get("Location", "")
        user_id = location.split("/")[-1]

        return {
            "user_id": user_id,
            "email": email,
            "role": "pending",  # Default, will be changed by caller
            "requires_approval": True,
        }

    async def get_users_with_roles(
        self,
        first: int = 0,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get all users with their roles attached.
        This is a convenience method that enriches user data with role information.
        """
        users = await self.get_all_users(first=first, max_results=max_results)

        # Enrich each user with their roles
        enriched_users = []
        for user in users:
            try:
                roles = await self.get_user_roles(user["id"])
                role_names = [r["name"] for r in roles]
                user["roles"] = role_names

                # Determine user status based on enabled flag and roles
                # Priority: disabled > admin > approved > pending > needs-role
                if not user.get("enabled", True):
                    user["status"] = "revoked"
                elif "admin" in role_names:
                    user["status"] = "admin"
                elif "user" in role_names:
                    user["status"] = "approved"
                elif "pending" in role_names:
                    user["status"] = "pending"
                else:
                    user["status"] = "needs-role"

                enriched_users.append(user)
            except Exception as e:
                log.warning(f"Failed to get roles for user {user['id']}: {e}")
                user["roles"] = []
                user["status"] = "unknown"
                enriched_users.append(user)

        return enriched_users

    # =========================================================================
    # PASSWORD RESET BY ADMIN
    # =========================================================================

    async def reset_user_password(
        self,
        user_id: str,
        new_password: str,
        temporary: bool = True,
    ) -> bool:
        """
        Reset a user's password (admin action).

        Args:
            user_id: The user's Keycloak ID
            new_password: The new password to set
            temporary: If True, user must change password on next login

        Returns:
            True if successful
        """
        credential_data = {
            "type": "password",
            "value": new_password,
            "temporary": temporary,
        }

        response = await self._make_request(
            "PUT",
            f"/users/{user_id}/reset-password",
            json_data=credential_data,
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to reset password: {response.text}")

        log.info(f"Reset password for user {user_id} (temporary={temporary})")
        return True

    # =========================================================================
    # GROUPS MANAGEMENT
    # =========================================================================

    async def get_all_groups(self) -> list[dict]:
        """Get all groups in the realm."""
        response = await self._make_request("GET", "/groups")

        if response.status_code != 200:
            raise Exception(f"Failed to get groups: {response.text}")

        return response.json()

    async def get_group_by_id(self, group_id: str) -> Optional[dict]:
        """Get a group by ID."""
        response = await self._make_request("GET", f"/groups/{group_id}")

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            raise Exception(f"Failed to get group: {response.text}")

        return response.json()

    async def create_group(self, name: str, parent_id: Optional[str] = None) -> dict:
        """
        Create a new group.

        Args:
            name: Group name
            parent_id: Optional parent group ID for nested groups

        Returns:
            dict with group info
        """
        group_data = {"name": name}

        if parent_id:
            # Create as subgroup
            response = await self._make_request(
                "POST", f"/groups/{parent_id}/children", json_data=group_data
            )
        else:
            # Create as top-level group
            response = await self._make_request("POST", "/groups", json_data=group_data)

        if response.status_code == 409:
            raise Exception(f"A group with name '{name}' already exists")

        if response.status_code != 201:
            raise Exception(f"Failed to create group: {response.text}")

        # Get the group ID from Location header
        location = response.headers.get("Location", "")
        group_id = location.split("/")[-1]

        return {"id": group_id, "name": name}

    async def update_group(self, group_id: str, name: str) -> dict:
        """Update a group's name."""
        response = await self._make_request(
            "PUT", f"/groups/{group_id}", json_data={"name": name}
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to update group: {response.text}")

        return {"id": group_id, "name": name}

    async def delete_group(self, group_id: str) -> bool:
        """Delete a group."""
        response = await self._make_request("DELETE", f"/groups/{group_id}")

        if response.status_code == 404:
            raise Exception("Group not found")

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to delete group: {response.text}")

        return True

    async def get_group_members(self, group_id: str) -> list[dict]:
        """Get all members of a group."""
        response = await self._make_request("GET", f"/groups/{group_id}/members")

        if response.status_code != 200:
            raise Exception(f"Failed to get group members: {response.text}")

        return response.json()

    async def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        """Add a user to a group."""
        response = await self._make_request(
            "PUT", f"/users/{user_id}/groups/{group_id}"
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to add user to group: {response.text}")

        return True

    async def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        """Remove a user from a group."""
        response = await self._make_request(
            "DELETE", f"/users/{user_id}/groups/{group_id}"
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to remove user from group: {response.text}")

        return True

    async def get_user_groups(self, user_id: str) -> list[dict]:
        """Get all groups a user belongs to."""
        response = await self._make_request("GET", f"/users/{user_id}/groups")

        if response.status_code != 200:
            raise Exception(f"Failed to get user groups: {response.text}")

        return response.json()

    async def get_group_role_mappings(self, group_id: str) -> list[dict]:
        """Get realm roles assigned to a group."""
        response = await self._make_request(
            "GET", f"/groups/{group_id}/role-mappings/realm"
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get group roles: {response.text}")

        return response.json()

    async def assign_role_to_group(self, group_id: str, role_name: str) -> bool:
        """Assign a realm role to a group (all members inherit)."""
        role = await self._get_role(role_name)
        if not role:
            raise Exception(f"Role '{role_name}' not found")

        response = await self._make_request(
            "POST",
            f"/groups/{group_id}/role-mappings/realm",
            json_data=[role],
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to assign role to group: {response.text}")

        return True

    async def remove_role_from_group(self, group_id: str, role_name: str) -> bool:
        """Remove a realm role from a group."""
        role = await self._get_role(role_name)
        if not role:
            raise Exception(f"Role '{role_name}' not found")

        response = await self._make_request(
            "DELETE",
            f"/groups/{group_id}/role-mappings/realm",
            json_data=[role],
        )

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to remove role from group: {response.text}")

        return True

    async def get_groups_with_details(self) -> list[dict]:
        """Get all groups with member counts and roles."""
        groups = await self.get_all_groups()

        async def enrich_group(group: dict) -> dict:
            try:
                members = await self.get_group_members(group["id"])
                group["memberCount"] = len(members)
            except Exception:
                group["memberCount"] = 0

            try:
                roles = await self.get_group_role_mappings(group["id"])
                group["roles"] = [r["name"] for r in roles]
            except Exception:
                group["roles"] = []

            # Process subgroups recursively
            if "subGroups" in group and group["subGroups"]:
                for subgroup in group["subGroups"]:
                    await enrich_group(subgroup)

            return group

        enriched = []
        for group in groups:
            enriched.append(await enrich_group(group))

        return enriched

    # =========================================================================
    # USER SESSIONS MANAGEMENT
    # =========================================================================

    async def get_user_sessions(self, user_id: str) -> list[dict]:
        """Get all active sessions for a user."""
        response = await self._make_request("GET", f"/users/{user_id}/sessions")

        if response.status_code != 200:
            raise Exception(f"Failed to get user sessions: {response.text}")

        return response.json()

    async def get_all_sessions(self) -> list[dict]:
        """Get all active sessions in the realm."""
        # Get client sessions for the main client
        response = await self._make_request(
            "GET", f"/clients/{KEYCLOAK_CLIENT_ID}/sessions" if KEYCLOAK_CLIENT_ID else "/sessions"
        )

        # Fallback: aggregate from all users
        if response.status_code != 200:
            # Get all users and their sessions
            users = await self.get_all_users(max_results=500)
            all_sessions = []
            for user in users:
                try:
                    sessions = await self.get_user_sessions(user["id"])
                    for session in sessions:
                        session["userEmail"] = user.get("email", "")
                        session["userName"] = f"{user.get('firstName', '')} {user.get('lastName', '')}".strip()
                    all_sessions.extend(sessions)
                except Exception:
                    pass
            return all_sessions

        return response.json()

    async def terminate_user_session(self, session_id: str) -> bool:
        """Terminate a specific user session."""
        response = await self._make_request("DELETE", f"/sessions/{session_id}")

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to terminate session: {response.text}")

        log.info(f"Terminated session {session_id}")
        return True

    async def terminate_all_user_sessions(self, user_id: str) -> int:
        """Terminate all sessions for a user. Returns count of terminated sessions."""
        response = await self._make_request("POST", f"/users/{user_id}/logout")

        if response.status_code not in [200, 204]:
            raise Exception(f"Failed to logout user: {response.text}")

        log.info(f"Terminated all sessions for user {user_id}")
        return 1  # Keycloak doesn't return count

    async def get_session_stats(self) -> dict:
        """Get session statistics for the realm."""
        # Get active session count
        response = await self._make_request("GET", "/client-session-stats")

        stats = {"totalActiveSessions": 0, "clientStats": []}

        if response.status_code == 200:
            client_stats = response.json()
            stats["clientStats"] = client_stats
            stats["totalActiveSessions"] = sum(
                int(c.get("active", 0)) for c in client_stats
            )

        return stats

    # =========================================================================
    # LOGIN EVENTS / SECURITY EVENTS
    # =========================================================================

    async def get_events(
        self,
        event_types: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        ip_address: Optional[str] = None,
        first: int = 0,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get login/security events from Keycloak.

        Args:
            event_types: Filter by event types (LOGIN, LOGIN_ERROR, LOGOUT, etc.)
            user_id: Filter by user ID
            date_from: Filter from date (ISO format)
            date_to: Filter to date (ISO format)
            ip_address: Filter by IP address
            first: Pagination offset
            max_results: Maximum results to return

        Returns:
            List of event records
        """
        params = {"first": first, "max": max_results}

        if event_types:
            params["type"] = event_types
        if user_id:
            params["user"] = user_id
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if ip_address:
            params["ipAddress"] = ip_address

        response = await self._make_request("GET", "/events", params=params)

        if response.status_code != 200:
            raise Exception(f"Failed to get events: {response.text}")

        return response.json()

    async def get_admin_events(
        self,
        operation_types: Optional[list[str]] = None,
        resource_types: Optional[list[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        first: int = 0,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get admin events (configuration changes, user management, etc.).

        Args:
            operation_types: Filter by operation (CREATE, UPDATE, DELETE, ACTION)
            resource_types: Filter by resource type (USER, REALM_ROLE, GROUP, etc.)
            date_from: Filter from date
            date_to: Filter to date
            first: Pagination offset
            max_results: Maximum results

        Returns:
            List of admin event records
        """
        params = {"first": first, "max": max_results}

        if operation_types:
            params["operationTypes"] = operation_types
        if resource_types:
            params["resourceTypes"] = resource_types
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to

        response = await self._make_request("GET", "/admin-events", params=params)

        if response.status_code != 200:
            raise Exception(f"Failed to get admin events: {response.text}")

        return response.json()

    async def get_event_types(self) -> list[str]:
        """Get all available event types."""
        # Common Keycloak event types
        return [
            "LOGIN",
            "LOGIN_ERROR",
            "LOGOUT",
            "LOGOUT_ERROR",
            "REGISTER",
            "REGISTER_ERROR",
            "CODE_TO_TOKEN",
            "CODE_TO_TOKEN_ERROR",
            "REFRESH_TOKEN",
            "REFRESH_TOKEN_ERROR",
            "INTROSPECT_TOKEN",
            "UPDATE_PASSWORD",
            "UPDATE_PASSWORD_ERROR",
            "RESET_PASSWORD",
            "RESET_PASSWORD_ERROR",
            "SEND_RESET_PASSWORD",
            "SEND_RESET_PASSWORD_ERROR",
            "UPDATE_PROFILE",
            "UPDATE_PROFILE_ERROR",
            "FEDERATED_IDENTITY_LINK",
            "REMOVE_FEDERATED_IDENTITY",
            "TOKEN_EXCHANGE",
            "PERMISSION_TOKEN",
        ]

    async def get_login_events_summary(self, days: int = 7) -> dict:
        """Get a summary of login events for the past N days."""
        from datetime import datetime, timedelta

        date_from = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

        # Get successful logins
        success_events = await self.get_events(
            event_types=["LOGIN"],
            date_from=date_from,
            max_results=1000,
        )

        # Get failed logins
        failed_events = await self.get_events(
            event_types=["LOGIN_ERROR"],
            date_from=date_from,
            max_results=1000,
        )

        # Count unique users and IPs
        unique_users = set()
        unique_ips = set()
        for event in success_events:
            if event.get("userId"):
                unique_users.add(event["userId"])
            if event.get("ipAddress"):
                unique_ips.add(event["ipAddress"])

        failed_ips = {}
        for event in failed_events:
            ip = event.get("ipAddress", "unknown")
            failed_ips[ip] = failed_ips.get(ip, 0) + 1

        # Get top failed IPs
        top_failed_ips = sorted(failed_ips.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "period_days": days,
            "successful_logins": len(success_events),
            "failed_logins": len(failed_events),
            "unique_users": len(unique_users),
            "unique_ips": len(unique_ips),
            "top_failed_ips": [{"ip": ip, "count": count} for ip, count in top_failed_ips],
        }


# Singleton instance
keycloak_admin = KeycloakAdminService()

