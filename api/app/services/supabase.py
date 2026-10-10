"""
Nexora API - Supabase Service & Client Integration
Provides safe, reusable access to the existing Nexora Supabase PostgreSQL & Storage.
Strictly reuses existing infrastructure without altering tables, schemas, or buckets.
"""

import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from api.app.config import settings

logger = logging.getLogger("nexora.api.supabase")


class SupabaseService:
    """
    Encapsulates connection and safe operations for the existing Nexora Supabase project.
    Strictly reuses existing PostgreSQL database and Storage buckets.
    """

    def __init__(self) -> None:
        self._client: Optional[Client] = None
        self._anon_client: Optional[Client] = None
        self._is_initialized: bool = False
        self._init_error: Optional[str] = None
        self._init_clients()

    def _init_clients(self) -> None:
        """Initialize Supabase clients safely using existing environment configuration."""
        if not settings.SUPABASE_URL:
            self._init_error = "SUPABASE_URL is not configured"
            logger.warning("Supabase initialization skipped: SUPABASE_URL not configured")
            return

        # Prioritize service-role key for backend operations, fallback to anon key
        auth_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        if not auth_key:
            self._init_error = "Neither SUPABASE_SERVICE_ROLE_KEY nor SUPABASE_ANON_KEY is configured"
            logger.warning("Supabase initialization skipped: Supabase API key not configured")
            return

        try:
            self._client = create_client(settings.SUPABASE_URL, auth_key)
            if settings.SUPABASE_ANON_KEY and settings.SUPABASE_ANON_KEY != auth_key:
                self._anon_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
            else:
                self._anon_client = self._client
            self._is_initialized = True
            self._init_error = None
            logger.info("Supabase client initialized successfully against existing project")
        except Exception as e:
            self._is_initialized = False
            self._init_error = "Failed to initialize Supabase client"
            logger.error(f"Error initializing Supabase client: {type(e).__name__}")

    @property
    def is_configured(self) -> bool:
        """Returns True if the required credentials exist and client was created."""
        return self._is_initialized and self._client is not None

    @property
    def client(self) -> Optional[Client]:
        """Returns the primary Supabase client."""
        return self._client

    @property
    def anon_client(self) -> Optional[Client]:
        """Returns the public anon Supabase client."""
        return self._anon_client

    def check_database_read_only(self) -> Dict[str, Any]:
        """
        Executes a safe, harmless read-only query on an existing table (users).
        Does NOT expose any actual user records or sensitive data.
        """
        if not self.is_configured or self._client is None:
            return {
                "status": "unconfigured",
                "connected": False,
                "message": self._init_error or "Supabase client is not configured"
            }

        try:
            # Query existing table 'users' with a harmless select('id').limit(1)
            response = self._client.table("users").select("id").limit(1).execute()
            return {
                "status": "connected",
                "connected": True,
                "message": "Database read query verified successfully"
            }
        except Exception as e:
            logger.warning(f"Supabase database verification query failed: {type(e).__name__}")
            return {
                "status": "unavailable",
                "connected": False,
                "message": "Database service is currently unreachable or inactive"
            }

    def check_storage_read_only(self) -> Dict[str, Any]:
        """
        Executes a safe, non-destructive read-only check on existing storage buckets.
        Does NOT create, delete, upload, or modify any buckets or objects.
        """
        if not self.is_configured or self._client is None:
            return {
                "status": "unconfigured",
                "connected": False,
                "message": self._init_error or "Supabase client is not configured"
            }

        try:
            # Safe read-only check of storage buckets
            buckets = self._client.storage.list_buckets()
            bucket_names: List[str] = [b.name for b in buckets] if buckets else []
            return {
                "status": "connected",
                "connected": True,
                "buckets_detected": bucket_names,
                "message": "Storage service verified successfully"
            }
        except Exception as e:
            logger.warning(f"Supabase storage verification check failed: {type(e).__name__}")
            return {
                "status": "unavailable",
                "connected": False,
                "message": "Storage service is currently unreachable or inactive"
            }

    def get_diagnostics(self) -> Dict[str, Any]:
        """
        Aggregates safe diagnostic status for health check endpoints.
        Never returns secrets, internal tokens, or user data.
        """
        db_check = self.check_database_read_only()
        storage_check = self.check_storage_read_only()

        if db_check.get("connected") and storage_check.get("connected"):
            overall_status = "healthy"
        elif db_check.get("connected") or storage_check.get("connected"):
            overall_status = "degraded"
        else:
            overall_status = "unavailable"

        return {
            "service": "Nexora Supabase Service",
            "status": overall_status,
            "configured": self.is_configured,
            "database": db_check.get("status"),
            "storage": storage_check.get("status"),
            "database_message": db_check.get("message"),
            "storage_message": storage_check.get("message"),
        }


# Singleton instance
_supabase_service_instance: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """Dependency provider / singleton accessor for SupabaseService."""
    global _supabase_service_instance
    if _supabase_service_instance is None:
        _supabase_service_instance = SupabaseService()
    return _supabase_service_instance


def get_supabase_client() -> Optional[Client]:
    """Dependency provider for the primary Supabase client."""
    service = get_supabase_service()
    return service.client
