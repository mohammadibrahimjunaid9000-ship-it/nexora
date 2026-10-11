"""
Nexora API - User Service
Encapsulates database operations on the existing Supabase users table.
Strictly reuses the 7 authoritative live columns: id, name, email, password, role, points, joined_at.
"""

from typing import Optional, Dict, Any, Union
import logging
from api.app.services.supabase import get_supabase_service, SupabaseService

logger = logging.getLogger("nexora.api.users")

SAFE_COLUMNS = "id,name,email,role,points,joined_at"
AUTH_COLUMNS = "id,name,email,password,role,points,joined_at"


class UserService:
    """Service layer for authoritative user operations on Supabase."""

    def __init__(self, supabase_service: Optional[SupabaseService] = None) -> None:
        self._supabase = supabase_service or get_supabase_service()

    @property
    def client(self):
        return self._supabase.client

    def get_by_id(self, user_id: Union[int, str], include_password: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch user by primary key ID, selecting safe or auth columns."""
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        cols = AUTH_COLUMNS if include_password else SAFE_COLUMNS
        try:
            res = self.client.table("users").select(cols).eq("id", user_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error fetching user by ID: {type(e).__name__}")
            raise

    def get_by_email(self, email: str, include_password: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch user case-insensitively by email."""
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        cols = AUTH_COLUMNS if include_password else SAFE_COLUMNS
        try:
            res = self.client.table("users").select(cols).ilike("email", email.strip().lower()).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error fetching user by email: {type(e).__name__}")
            raise

    def get_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user by email or name for login.
        Retrieves AUTH_COLUMNS for password verification.
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        clean_id = identifier.strip()
        try:
            # If identifier contains '@', prioritize email lookup
            if "@" in clean_id:
                res = self.client.table("users").select(AUTH_COLUMNS).ilike("email", clean_id.lower()).limit(1).execute()
                if res.data:
                    return res.data[0]
                # Fallback to name if not matched by email
                res_name = self.client.table("users").select(AUTH_COLUMNS).ilike("name", clean_id).limit(1).execute()
                return res_name.data[0] if res_name.data else None
            else:
                # Prioritize name lookup
                res_name = self.client.table("users").select(AUTH_COLUMNS).ilike("name", clean_id).limit(1).execute()
                if res_name.data:
                    return res_name.data[0]
                # Fallback to email lookup
                res = self.client.table("users").select(AUTH_COLUMNS).ilike("email", clean_id.lower()).limit(1).execute()
                return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error fetching user by identifier: {type(e).__name__}")
            raise

    def create_user(self, name: str, email: str, password_hash: str, role: str) -> Dict[str, Any]:
        """Insert new user with existing core columns."""
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        payload = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "password": password_hash,
            "role": role,
            "points": 0
        }

        try:
            res = self.client.table("users").insert(payload).execute()
            if not res.data:
                raise RuntimeError("Failed to insert user into database.")
            user = res.data[0]
            # Ensure password is never exposed in returned dict
            user.pop("password", None)
            return user
        except Exception as e:
            logger.error(f"Error creating user: {type(e).__name__}")
            raise

    def update_password(self, user_id: Union[int, str], new_password_hash: str) -> bool:
        """Update only the password hash for a specific user (transparent legacy migration)."""
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            res = self.client.table("users").update({"password": new_password_hash}).eq("id", user_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"Error updating user password: {type(e).__name__}")
            raise


# Singleton accessor
_user_service_instance: Optional[UserService] = None


def get_user_service() -> UserService:
    """Dependency provider / singleton accessor for UserService."""
    global _user_service_instance
    if _user_service_instance is None:
        _user_service_instance = UserService()
    return _user_service_instance
