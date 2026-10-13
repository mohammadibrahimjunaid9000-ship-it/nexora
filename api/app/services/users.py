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
PUBLIC_COLUMNS = "id,name,role"


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

    def update_role(self, user_id: Union[int, str], new_role: str) -> Optional[Dict[str, Any]]:
        """Update only the role column for a specific user and return safe user record."""
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            res = self.client.table("users").update({"role": new_role}).eq("id", user_id).execute()
            if not res.data:
                return None
            return self.get_by_id(user_id)
        except Exception as e:
            logger.error(f"Error updating user role: {type(e).__name__}")
            raise

    def resolve_google_account(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves or creates a Nexora user from a verified Google email.
        Invariants:
        - Email is stripped and lowercased.
        - If user exists by email, returns the authoritative user (preserving id, name, email, password, role, points, joined_at).
        - If user does not exist, inserts a new user with:
            name: provided Google name or fallback to email local part
            email: normalized email
            password: None
            role: None
            points: 0
        - Safely handles concurrent account creation race where a simultaneous insert triggers a unique email constraint violation.
        - Returns safe user dict (never exposing password hash).
        """
        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        clean_email = email.strip().lower()

        # 1. Authoritative lookup of existing user
        try:
            existing = self.get_by_email(clean_email)
            if existing:
                return existing
        except Exception as e:
            logger.error(f"Error querying user by email during Google resolution: {type(e).__name__}")
            raise

        # 2. Determine safe display name
        clean_name = (name or "").strip()
        if not clean_name:
            clean_name = clean_email.split("@")[0].replace(".", " ").title() or "Nexora User"

        payload = {
            "name": clean_name[:150],
            "email": clean_email,
            "password": None,
            "role": None,
            "points": 0
        }

        # 3. Insert new Google user row
        try:
            res = self.client.table("users").insert(payload).execute()
            if not res.data:
                raise RuntimeError("Failed to insert Google user into database.")
            user = res.data[0]
            user.pop("password", None)
            return user
        except Exception as e:
            err_str = str(e).lower()
            # 4. Handle concurrent account-creation race condition (unique constraint on email)
            if "unique" in err_str or "duplicate" in err_str or "23505" in err_str:
                logger.info(f"Unique email constraint triggered during concurrent Google signup for {clean_email}. Fetching existing record.")
                existing = self.get_by_email(clean_email)
                if existing:
                    return existing
            logger.error(f"Error creating Google user: {type(e).__name__}")
            raise

    def update_name(self, user_id: Union[int, str], name: str) -> Optional[Dict[str, Any]]:
        """
        Safely update ONLY the name column for a specific user ID.
        Invariants:
        - Accepts only user_id and cleaned name.
        - Trims whitespace and validates length (2-150 chars) at the service boundary.
        - Updates strictly {"name": clean_name}.
        - Filters strictly by id = user_id.
        - Never mutates email, password, role, points, or joined_at.
        - Returns safe authoritative user record (SAFE_COLUMNS), or None if user not found.
        """
        if not user_id:
            raise ValueError("user_id is required to update name.")

        if name is None or not isinstance(name, str):
            raise ValueError("name must be a valid string.")

        clean_name = name.strip()
        if len(clean_name) < 2:
            raise ValueError("Name must be at least 2 characters long.")
        if len(clean_name) > 150:
            raise ValueError("Name must not exceed 150 characters.")

        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            res = self.client.table("users").update({"name": clean_name}).eq("id", user_id).execute()
            if not res.data:
                return None
            return self.get_by_id(user_id)
        except Exception as e:
            logger.error(f"Error updating user name: {type(e).__name__}")
            raise

    def get_public_profile(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Fetch minimal non-sensitive public user profile (id, name, role).
        Strictly queries only PUBLIC_COLUMNS ("id,name,role").
        Never queries or exposes password, email, points, or joined_at.
        Returns normalized dictionary or None if user not found.
        """
        if not user_id:
            return None

        if not self.client:
            raise RuntimeError("Database service is currently unavailable.")

        try:
            res = self.client.table("users").select(PUBLIC_COLUMNS).eq("id", user_id).limit(1).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            logger.error(f"Error fetching public user profile: {type(e).__name__}")
            raise


# Singleton accessor
_user_service_instance: Optional[UserService] = None


def get_user_service() -> UserService:
    """Dependency provider / singleton accessor for UserService."""
    global _user_service_instance
    if _user_service_instance is None:
        _user_service_instance = UserService()
    return _user_service_instance
