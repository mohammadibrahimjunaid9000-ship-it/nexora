"""
Nexora Learning Platform - Automated Authentication System Test Suite
Verifies all authentication requirements: Email signup/login, Google OAuth endpoints,
Bcrypt hashing, Role Onboarding, Returning User auto-redirection, Forgot Password, and Duplicate Prevention.
"""

import sys
import os
import unittest
import json

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_dir)

from app import create_app
from models import db, User
from utils.auth import check_password, hash_password, is_valid_email


class TestNexoraAuthSystem(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_01_email_validation_and_hashing(self):
        """Test email format validation and Bcrypt password hashing."""
        self.assertTrue(is_valid_email("learner@nexora.com"))
        self.assertFalse(is_valid_email("invalid-email"))

        pwd = "SecretPassword123!"
        hashed = hash_password(pwd)
        self.assertTrue(hashed.startswith("$2b$"))
        self.assertTrue(check_password(pwd, hashed))
        self.assertFalse(check_password("WrongPassword", hashed))

    def test_02_email_registration(self):
        """Test unified email registration without initial role."""
        payload = {
            "full_name": "Alice Tester",
            "email": "alice@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        response = self.client.post('/api/auth/register', json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data['requires_role_selection'])
        self.assertIsNone(data['user']['role'])
        self.assertEqual(data['user']['email'], "alice@example.com")

    def test_03_duplicate_email_prevention(self):
        """Test preventing registration with duplicate email."""
        payload = {
            "full_name": "Bob Duplicate",
            "email": "bob@example.com",
            "password": "password123"
        }
        self.client.post('/api/auth/register', json=payload)
        response = self.client.post('/api/auth/register', json=payload)
        self.assertEqual(response.status_code, 409)
        self.assertIn("already exists", response.get_json()['error'])

    def test_04_first_time_role_selection(self):
        """Test assigning Learner or Creator role permanently during onboarding."""
        # 1. Register
        reg_res = self.client.post('/api/auth/register', json={
            "full_name": "Charlie Learner",
            "email": "charlie@example.com",
            "password": "password123"
        })
        self.assertEqual(reg_res.status_code, 201)

        # 2. Assign role
        role_res = self.client.post('/api/auth/set-role', json={"role": "learner"})
        self.assertEqual(role_res.status_code, 200)
        data = role_res.get_json()
        self.assertEqual(data['user']['role'], "learner")

        # 3. Check me endpoint
        me_res = self.client.get('/api/auth/me')
        self.assertEqual(me_res.get_json()['user']['role'], "learner")

    def test_05_returning_user_login(self):
        """Test returning user login automatically retrieves assigned role."""
        with self.app.app_context():
            user = User(
                name="Diana Creator",
                email="diana@example.com",
                password=hash_password("creatorpass"),
                role="creator"
            )
            db.session.add(user)
            db.session.commit()

        login_res = self.client.post('/api/auth/login', json={
            "email": "diana@example.com",
            "password": "creatorpass"
        })
        self.assertEqual(login_res.status_code, 200)
        data = login_res.get_json()
        self.assertFalse(data['requires_role_selection'])
        self.assertEqual(data['user']['role'], "creator")

    def test_06_forgot_and_reset_password(self):
        """Test forgot password request and resetting password."""
        with self.app.app_context():
            user = User(
                name="Evan Reset",
                email="evan@example.com",
                password=hash_password("oldpassword")
            )
            db.session.add(user)
            db.session.commit()

        # Request reset
        forgot_res = self.client.post('/api/auth/forgot-password', json={"email": "evan@example.com"})
        self.assertEqual(forgot_res.status_code, 200)
        reset_token = forgot_res.get_json()['reset_token']

        # Reset password
        reset_res = self.client.post('/api/auth/reset-password', json={
            "email": "evan@example.com",
            "token": reset_token,
            "new_password": "newpassword123"
        })
        self.assertEqual(reset_res.status_code, 200)

        # Login with new password
        login_res = self.client.post('/api/auth/login', json={
            "email": "evan@example.com",
            "password": "newpassword123"
        })
        self.assertEqual(login_res.status_code, 200)

    def test_07_google_oauth_url_endpoint(self):
        """Test generating Google OAuth authorization URL with credentials from .env."""
        res = self.client.get('/api/auth/google/url')
        self.assertEqual(res.status_code, 200)
        url = res.get_json().get('url')
        self.assertIn("accounts.google.com", url)
        self.assertIn("response_type=code", url)
        self.assertIn("scope=", url)


if __name__ == '__main__':
    unittest.main()
