"""
Unit & Integration tests for FastAPI existing Supabase service.
Tests health checks, configuration loading, error handling, and safe read-only queries.
"""

import unittest
from unittest.mock import MagicMock
from starlette.testclient import TestClient

from api.app.main import app
from api.app.config import settings
from api.app.services.supabase import SupabaseService, get_supabase_service


class TestFastAPISupabaseIntegration(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_01_health_endpoint(self):
        """Verify baseline health check endpoint returns 200 and expected schema."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), settings.APP_NAME)
        self.assertEqual(data.get("version"), settings.APP_VERSION)

    def test_02_settings_loaded_from_env(self):
        """Verify that Supabase settings are loaded from environment."""
        self.assertIsNotNone(settings.SUPABASE_URL)
        self.assertTrue(len(settings.SUPABASE_URL) > 0)
        self.assertEqual(settings.SUPABASE_BUCKET_THUMBNAILS, "course_thumbnails")
        self.assertEqual(settings.SUPABASE_BUCKET_VIDEOS, "videos")
        self.assertEqual(settings.SUPABASE_BUCKET_AVATARS, "profile_images")

    def test_03_service_initialization(self):
        """Verify SupabaseService initializes client instance safely."""
        service = get_supabase_service()
        self.assertTrue(service.is_configured)
        self.assertIsNotNone(service.client)

    def test_04_supabase_health_endpoint_response_format(self):
        """Verify /api/v1/health/supabase endpoint returns clean structure without secrets."""
        response = self.client.get("/api/v1/health/supabase")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check required fields
        self.assertIn("service", data)
        self.assertIn("status", data)
        self.assertIn("configured", data)
        self.assertIn("database", data)
        self.assertIn("storage", data)

        # Ensure no sensitive credentials leaked
        json_str = response.text.lower()
        self.assertNotIn("secret", json_str)
        self.assertNotIn("key", json_str)
        self.assertNotIn("password", json_str)
        self.assertNotIn("token", json_str)

    def test_05_mocked_successful_connection(self):
        """Verify that when Supabase is reachable, healthy diagnostics are reported."""
        service = SupabaseService()

        # Mock the underlying client
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_limit = MagicMock()
        mock_limit.execute.return_value = MagicMock(data=[{"id": 1}])
        mock_select.limit.return_value = mock_limit
        mock_table.select.return_value = mock_select
        mock_client.table.return_value = mock_table

        # Mock storage
        mock_bucket = MagicMock()
        mock_bucket.name = "course_thumbnails"
        mock_client.storage.list_buckets.return_value = [mock_bucket]

        service._client = mock_client
        service._is_initialized = True

        diag = service.get_diagnostics()
        self.assertEqual(diag.get("status"), "healthy")
        self.assertEqual(diag.get("database"), "connected")
        self.assertEqual(diag.get("storage"), "connected")
        self.assertEqual(diag.get("database_message"), "Database read query verified successfully")
        self.assertEqual(diag.get("storage_message"), "Storage service verified successfully")


if __name__ == "__main__":
    unittest.main()
