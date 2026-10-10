"""
Nexora Learning Platform - Authentication Helpers
Provides Bcrypt password hashing, email validation, Google OAuth 2.0 token verification & user profile fetching.
"""

import os
import re
import json
import uuid
import bcrypt
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir) if os.path.basename(backend_dir) == 'backend' else backend_dir
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path, override=True)


def get_google_config():
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/auth/google/callback').strip()
    return client_id, client_secret, redirect_uri


def is_valid_email(email):
    if not email or not isinstance(email, str):
        return False
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(regex, email.strip()))


def hash_password(password):
    """Hashes a plain text password using bcrypt."""
    if not password:
        return None
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def check_password(password, hashed_password):
    """Verifies a plain text password against a bcrypt (or legacy werkzeug) hashed password."""
    if not password or not hashed_password:
        return False
    try:
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$') or hashed_password.startswith('$2y$'):
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        # Legacy werkzeug password check fallback
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, password)
    except Exception:
        return False


def generate_google_auth_url(state=None):
    """Generates the Google OAuth 2.0 authorization URL."""
    client_id, _, redirect_uri = get_google_config()
    if not client_id:
        return None

    scopes = [
        'openid',
        'email',
        'profile',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/calendar'
    ]
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(scopes),
        'access_type': 'offline',
        'prompt': 'consent'
    }
    if state:
        params['state'] = state
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)


def exchange_google_code(code):
    """Exchanges an authorization code for Google access token and ID token."""
    client_id, client_secret, redirect_uri = get_google_config()
    print(f"[OAUTH LOG] Initiating OAuth token exchange...")
    print(f"[OAUTH LOG] client_id: {client_id[:12]}...")
    print(f"[OAUTH LOG] redirect_uri: {redirect_uri}")

    if not client_id or not client_secret or not code:
        print("[OAUTH ERROR] Missing client_id, client_secret, or authorization code.")
        return None

    data = urllib.parse.urlencode({
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            if res.status == 200:
                payload = json.loads(res.read().decode('utf-8'))
                print(f"[OAUTH LOG] Token exchange successful. Access token acquired.")
                if 'refresh_token' in payload:
                    print(f"[OAUTH LOG] Refresh token acquired.")
                else:
                    print(f"[OAUTH LOG] Note: No refresh_token in response (re-consent may be required for a new refresh token).")
                return payload
    except urllib.error.HTTPError as he:
        body = he.read().decode('utf-8', errors='ignore')
        print(f"[OAUTH ERROR] HTTP Error {he.code} during token exchange: {body}")
        return None
    except Exception as e:
        print(f"[OAUTH ERROR] Exception during token exchange: {e}")
        return None


def fetch_google_user_info(access_token):
    """Retrieves Google user profile info using access token."""
    if not access_token:
        print("[OAUTH ERROR] Cannot fetch userinfo: access_token is empty.")
        return None

    req = urllib.request.Request(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f'Bearer {access_token}'}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            if res.status == 200:
                user_info = json.loads(res.read().decode('utf-8'))
                print(f"[OAUTH LOG] Fetched user profile for email: {user_info.get('email')}")
                return user_info
    except Exception as e:
        print(f"[OAUTH ERROR] Error fetching Google userinfo: {e}")
        return None


def generate_reset_token():
    return str(uuid.uuid4())
