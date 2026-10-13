"""
Comprehensive Unit Tests for Phase 4 — Stage 7A: User Profile Backend Foundation
Tests:
- Pydantic schema validation: UpdateProfileRequest, UserProfileResponse, PublicUserProfileResponse
- Name trimming, length boundary enforcement, whitespace rejection, extra field forbidding
- UserService.update_name(): safe name update, id filtering, immutability of role/email/points/password
- UserService.get_public_profile(): minimal safe projection (id, name, role), non-exposure of email/password
- Database error handling and nonexistent record safety
- Security regressions: privilege escalation payload rejection, payload tampering prevention
- 100% mock-isolated from live database.
"""

import unittest
from unittest.mock import MagicMock
from datetime import datetime
from pydantic import ValidationError

from api.app.schemas.users import (
    UpdateProfileRequest,
    UserProfileResponse,
    PublicUserProfileResponse,
)
from api.app.services.users import UserService, PUBLIC_COLUMNS, SAFE_COLUMNS


class TestUserProfileSchemasStage7A(unittest.TestCase):
    """Test suite for Stage 7A Pydantic schemas."""

    # 1. Valid name accepted
    def test_01_valid_name_accepted(self):
        req = UpdateProfileRequest(name="Jane Doe")
        self.assertEqual(req.name, "Jane Doe")

    # 2. Surrounding whitespace trimmed
    def test_02_surrounding_whitespace_trimmed(self):
        req = UpdateProfileRequest(name="   Alex Smith   ")
        self.assertEqual(req.name, "Alex Smith")

    # 3. Name below 2 characters rejected
    def test_03_name_below_two_chars_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="A")
        self.assertIn("at least 2 characters", str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx2:
            UpdateProfileRequest(name=" A ")
        self.assertIn("at least 2 characters", str(ctx2.exception))

    # 4. Whitespace-only name rejected
    def test_04_whitespace_only_name_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="     ")
        self.assertIn("at least 2 characters", str(ctx.exception))

    # 5. Name over 150 characters rejected
    def test_05_name_over_150_chars_rejected(self):
        long_name = "x" * 151
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name=long_name)
        self.assertIn("150", str(ctx.exception))

        # 150 characters exactly is accepted
        req = UpdateProfileRequest(name="x" * 150)
        self.assertEqual(len(req.name), 150)

    # 6. Extra fields are rejected (extra="forbid")
    def test_06_extra_fields_strictly_forbidden(self):
        # Attempting to inject role
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="Jane Doe", role="admin")  # type: ignore
        self.assertIn("Extra inputs are not permitted", str(ctx.exception))

        # Attempting to inject points
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="Jane Doe", points=999999)  # type: ignore
        self.assertIn("Extra inputs are not permitted", str(ctx.exception))

        # Attempting to inject email
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="Jane Doe", email="hacker@example.com")  # type: ignore
        self.assertIn("Extra inputs are not permitted", str(ctx.exception))

        # Attempting to inject password
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(name="Jane Doe", password="new-password")  # type: ignore
        self.assertIn("Extra inputs are not permitted", str(ctx.exception))

    # 7. Profile response contains only safe fields and never exposes password
    def test_07_user_profile_response_safe_fields(self):
        data = {
            "id": 42,
            "name": "Jane Learner",
            "email": "jane@example.com",
            "role": "learner",
            "points": 150,
            "joined_at": "2026-10-13T00:00:00Z"
        }
        res = UserProfileResponse(**data)
        res_dict = res.model_dump()

        self.assertEqual(res_dict["id"], 42)
        self.assertEqual(res_dict["name"], "Jane Learner")
        self.assertEqual(res_dict["email"], "jane@example.com")
        self.assertEqual(res_dict["role"], "learner")
        self.assertEqual(res_dict["points"], 150)
        self.assertEqual(res_dict["joined_at"], "2026-10-13T00:00:00Z")
        self.assertNotIn("password", res_dict)
        self.assertNotIn("password_hash", res_dict)

        # Extra ignored fields like password are not serialized
        data_with_secret = dict(data, password="hashed-bcrypt-secret", secret_token="xyz")
        res_ignored = UserProfileResponse(**data_with_secret)
        self.assertNotIn("password", res_ignored.model_dump())
        self.assertNotIn("secret_token", res_ignored.model_dump())

    # 8. Public profile response contains only intended public fields
    def test_08_public_profile_response_minimal_fields(self):
        data = {
            "id": 10,
            "name": "Prof. Turing",
            "role": "creator"
        }
        res = PublicUserProfileResponse(**data)
        res_dict = res.model_dump()

        self.assertEqual(res_dict["id"], 10)
        self.assertEqual(res_dict["name"], "Prof. Turing")
        self.assertEqual(res_dict["role"], "creator")
        self.assertNotIn("email", res_dict)
        self.assertNotIn("password", res_dict)
        self.assertNotIn("points", res_dict)
        self.assertNotIn("joined_at", res_dict)


class TestUserServiceStage7A(unittest.TestCase):
    """Test suite for Stage 7A UserService methods."""

    def setUp(self):
        self.mock_supabase = MagicMock()
        self.mock_client = MagicMock()
        self.mock_table = MagicMock()
        self.mock_supabase.client = self.mock_client
        self.mock_client.table.return_value = self.mock_table

        self.service = UserService(supabase_service=self.mock_supabase)

    # 9. update_name() updates only name
    def test_09_update_name_updates_only_name(self):
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = [{"id": 1, "name": "Clean Name"}]

        self.mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_exec

        # Mock get_by_id return
        self.service.get_by_id = MagicMock(return_value={
            "id": 1,
            "name": "Clean Name",
            "email": "user@example.com",
            "role": "learner",
            "points": 50,
            "joined_at": "2026-10-13T00:00:00Z"
        })

        result = self.service.update_name(user_id=1, name="   Clean Name   ")

        # Verify update payload contains exclusively {"name": "Clean Name"}
        self.mock_table.update.assert_called_once_with({"name": "Clean Name"})
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Clean Name")

    # 10. update_name() filters by authenticated user ID
    def test_10_update_name_filters_by_id(self):
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = [{"id": 42, "name": "Updated"}]

        self.mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_exec

        self.service.get_by_id = MagicMock(return_value={"id": 42, "name": "Updated"})

        self.service.update_name(user_id=42, name="Updated")
        mock_update.eq.assert_called_once_with("id", 42)

    # 11. update_name() never sends email/role/points/password/joined_at
    def test_11_update_name_never_sends_forbidden_attributes(self):
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = [{"id": 7, "name": "Safe Name"}]

        self.mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_exec
        self.service.get_by_id = MagicMock(return_value={"id": 7, "name": "Safe Name"})

        self.service.update_name(user_id=7, name="Safe Name")

        # Inspect dictionary passed to update
        update_args = self.mock_table.update.call_args[0][0]
        self.assertEqual(list(update_args.keys()), ["name"])
        self.assertNotIn("email", update_args)
        self.assertNotIn("role", update_args)
        self.assertNotIn("points", update_args)
        self.assertNotIn("password", update_args)
        self.assertNotIn("joined_at", update_args)

    # 12. Nonexistent user handled correctly (returns None)
    def test_12_update_name_nonexistent_user_returns_none(self):
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = []  # No rows updated

        self.mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_exec

        result = self.service.update_name(user_id=999, name="Ghost User")
        self.assertIsNone(result)

    # 13. Supabase failure handled correctly
    def test_13_update_name_supabase_failure(self):
        # Database service unavailable
        unavail_service = UserService(supabase_service=MagicMock(client=None))
        with self.assertRaises(RuntimeError) as ctx:
            unavail_service.update_name(user_id=1, name="Valid Name")
        self.assertIn("Database service is currently unavailable", str(ctx.exception))

        # Query exception propagates cleanly
        mock_update = MagicMock()
        self.mock_table.update.return_value = mock_update
        mock_update.eq.side_effect = RuntimeError("PostgREST connection pool timeout")

        with self.assertRaises(RuntimeError):
            self.service.update_name(user_id=1, name="Valid Name")

    # 14. get_public_profile() queries only id,name,role
    def test_14_get_public_profile_queries_only_public_columns(self):
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_limit = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = [{"id": 5, "name": "Ada Lovelace", "role": "creator"}]

        self.mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_exec

        res = self.service.get_public_profile(user_id=5)

        self.mock_table.select.assert_called_once_with(PUBLIC_COLUMNS)
        self.assertEqual(PUBLIC_COLUMNS, "id,name,role")
        mock_select.eq.assert_called_once_with("id", 5)
        self.assertEqual(res, {"id": 5, "name": "Ada Lovelace", "role": "creator"})

    # 15. get_public_profile() does not request email/password
    def test_15_get_public_profile_does_not_request_sensitive_columns(self):
        self.assertNotIn("email", PUBLIC_COLUMNS.split(","))
        self.assertNotIn("password", PUBLIC_COLUMNS.split(","))
        self.assertNotIn("points", PUBLIC_COLUMNS.split(","))
        self.assertNotIn("joined_at", PUBLIC_COLUMNS.split(","))

    # 16. Nonexistent public user handled correctly (returns None)
    def test_16_get_public_profile_nonexistent_user(self):
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_limit = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = []

        self.mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_exec

        res = self.service.get_public_profile(user_id=999)
        self.assertIsNone(res)

        # None on invalid ID
        self.assertIsNone(self.service.get_public_profile(user_id=None))  # type: ignore

    # 17. Supabase failure handled correctly in get_public_profile()
    def test_17_get_public_profile_supabase_failure(self):
        unavail_service = UserService(supabase_service=MagicMock(client=None))
        with self.assertRaises(RuntimeError) as ctx:
            unavail_service.get_public_profile(user_id=1)
        self.assertIn("Database service is currently unavailable", str(ctx.exception))

        mock_select = MagicMock()
        self.mock_table.select.return_value = mock_select
        mock_select.eq.side_effect = RuntimeError("Database unreachable")

        with self.assertRaises(RuntimeError):
            self.service.get_public_profile(user_id=1)

    # 18. Security regression test: privilege escalation payload rejected
    def test_18_security_regression_tampered_payload_cannot_mutate_privileged_fields(self):
        malicious_raw_payload = {
            "name": "New Name",
            "role": "admin",
            "points": 999999,
            "email": "attacker@example.com",
            "password": "attacker-password"
        }

        # 1. Verify schema blocks the tampered payload
        with self.assertRaises(ValidationError) as ctx:
            UpdateProfileRequest(**malicious_raw_payload)
        err_msg = str(ctx.exception)
        self.assertIn("Extra inputs are not permitted", err_msg)

        # 2. Verify service boundary only ever updates {"name": "New Name"}
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_exec = MagicMock()
        mock_exec.data = [{"id": 1, "name": "New Name"}]

        self.mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_exec
        self.service.get_by_id = MagicMock(return_value={"id": 1, "name": "New Name"})

        # Even if an untrusted caller tried to extract only name:
        self.service.update_name(user_id=1, name=malicious_raw_payload["name"])

        # Update payload passed to database client must be exclusively {"name": "New Name"}
        called_payload = self.mock_table.update.call_args[0][0]
        self.assertEqual(called_payload, {"name": "New Name"})
        self.assertNotIn("role", called_payload)
        self.assertNotIn("points", called_payload)
        self.assertNotIn("email", called_payload)
        self.assertNotIn("password", called_payload)

    # 19. Service boundary input validation
    def test_19_service_boundary_name_validation(self):
        # Empty string
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=1, name="")

        # Whitespace-only string
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=1, name="   ")

        # Below 2 chars
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=1, name="A")

        # Over 150 chars
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=1, name="x" * 151)

        # Missing user_id
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=None, name="Valid Name")  # type: ignore

        # None name
        with self.assertRaises(ValueError):
            self.service.update_name(user_id=1, name=None)  # type: ignore


if __name__ == "__main__":
    unittest.main()
