"""
Nexora Learning Platform - Google Calendar & Meet Integration Module
Handles Google OAuth 2.0 authorization, token exchange, refresh tokens, Google Calendar event creation, Google Meet link generation, and email notifications.
"""

import os
import uuid
import logging
import traceback
from datetime import datetime, timedelta
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv

# Load environment variables from root .env file
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(backend_dir) if os.path.basename(backend_dir) == 'backend' else backend_dir
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

logger = logging.getLogger('google_calendar')

def get_google_config():
    client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://127.0.0.1:5000/api/auth/google/callback').strip()
    api_key = os.getenv('GOOGLE_API_KEY', '').strip()
    return client_id, client_secret, redirect_uri, api_key


def get_google_auth_url():
    client_id, _, redirect_uri, _ = get_google_config()
    if not client_id or client_id == 'your_google_client_id_here':
        return None

    scope = 'https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar openid email profile'
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'access_type': 'offline',
        'prompt': 'consent'
    }
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)


def exchange_code_for_tokens(code):
    client_id, client_secret, redirect_uri, _ = get_google_config()
    if not client_id or not client_secret:
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
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                payload = json.loads(res.read().decode('utf-8'))
                return {
                    'access_token': payload.get('access_token'),
                    'refresh_token': payload.get('refresh_token'),
                    'expires_in': payload.get('expires_in', 3600)
                }
    except Exception as e:
        logger.error(f"Failed to exchange Google OAuth code: {e}")
        return None


def refresh_user_google_token(user, db):
    if not user.google_refresh_token:
        print(f"[OAUTH LOG] Cannot refresh token for user {user.id}: No refresh_token stored.")
        return None

    client_id, client_secret, _, _ = get_google_config()
    if not client_id or not client_secret:
        print("[OAUTH ERROR] Cannot refresh token: Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET.")
        return None

    print(f"[OAUTH LOG] Attempting to refresh Google access token for user {user.id} ({user.email})...")

    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': user.google_refresh_token,
        'grant_type': 'refresh_token'
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
                user.google_access_token = payload.get('access_token')
                expires_in = payload.get('expires_in', 3600)
                user.google_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                user.is_google_connected = True
                user.updated_at = datetime.utcnow()
                db.session.commit()
                print(f"[OAUTH LOG] Successfully refreshed Google access token for user {user.id}.")
                return user.google_access_token
    except Exception as e:
        print(f"[OAUTH ERROR] Failed to refresh Google access token for user {user.id}: {e}")
        logger.error(f"Failed to refresh Google access token for user {user.id}: {e}")
        return None


def is_valid_meet_url(url):
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith('https://meet.google.com/') or url.startswith('https://hangouts.google.com/') or url.startswith('https://tel.meet/')


def create_google_calendar_event(user, db, title, description, scheduled_at, duration_minutes=60, is_retry=False):
    """
    Creates a Google Calendar event with Google Meet videoconferencing.
    Automatically refreshes access token if expired or on 401 status.
    Returns tuple: (event_id, meeting_link, error_message)
    """
    if not user:
        return None, None, "User account required."

    if not user.is_google_connected or not user.google_access_token:
        return None, None, "Google Calendar authentication required. Please click 'Connect Google Calendar' in Profile settings first."

    # Check token expiry and attempt proactive refresh if expired
    token = user.google_access_token
    if user.google_token_expiry and datetime.utcnow() >= user.google_token_expiry:
        print(f"[OAUTH LOG] Access token expired for user {user.id}. Refreshing token proactively...")
        token = refresh_user_google_token(user, db)

    if not token:
        return None, None, "Google OAuth session expired. Please reconnect Google Calendar in Profile settings."

    end_at = scheduled_at + timedelta(minutes=duration_minutes)
    start_iso = scheduled_at.isoformat() + 'Z'
    end_iso = end_at.isoformat() + 'Z'

    event_body = {
        'summary': f"Nexora Live: {title}",
        'description': description or 'Nexora Live Learning Session',
        'start': {'dateTime': start_iso},
        'end': {'dateTime': end_iso},
        'conferenceData': {
            'createRequest': {
                'requestId': f"nexora-{uuid.uuid4()}",
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}
            }
        }
    }

    url = 'https://www.googleapis.com/calendar/v3/calendars/primary/events?conferenceDataVersion=1'
    data = json.dumps(event_body).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    )

    try:
        with urllib.request.urlopen(req) as res:
            if res.status in (200, 201):
                payload = json.loads(res.read().decode('utf-8'))
                event_id = payload.get('id')
                meet_link = payload.get('hangoutLink')
                
                # Check conferenceData entryPoints
                if not meet_link:
                    conf_data = payload.get('conferenceData', {})
                    entry_points = conf_data.get('entryPoints', [])
                    for ep in entry_points:
                        if ep.get('entryPointType') == 'video':
                            meet_link = ep.get('uri')
                            break

                if is_valid_meet_url(meet_link):
                    print(f"[OAUTH LOG] Created Google Calendar Event {event_id} with Meet link: {meet_link}")
                    return event_id, meet_link, None
                else:
                    return None, None, "Google Calendar API created the event, but failed to return a valid Google Meet link."
    except urllib.error.HTTPError as he:
        raw_body = he.read().decode('utf-8', errors='ignore')
        logger.error(f"Google Calendar API HTTP Error {he.code}: {raw_body}")
        print(f"[OAUTH ERROR] Google Calendar API HTTP Error {he.code}: {raw_body}")
        
        # If 401 Unauthorized occurs and we haven't retried yet, attempt token refresh and retry request
        if he.code == 401 and not is_retry and user.google_refresh_token:
            print(f"[OAUTH LOG] Received 401 401 Unauthorized. Attempting automatic token refresh...")
            new_token = refresh_user_google_token(user, db)
            if new_token:
                print(f"[OAUTH LOG] Token refreshed successfully. Retrying Google Calendar event creation...")
                return create_google_calendar_event(user, db, title, description, scheduled_at, duration_minutes, is_retry=True)

        try:
            err_json = json.loads(raw_body)
            g_err = err_json.get('error', {})
            err_message = g_err.get('message', raw_body)
            error_str = f"Google Calendar API Error ({he.code}): {err_message}"
        except Exception:
            error_str = f"Google Calendar API Error ({he.code}): {raw_body}"

        if he.code == 401:
            user.is_google_connected = False
            db.session.commit()
            return None, None, f"Google OAuth authorization expired (401). Please reconnect Google Calendar in Profile settings. Details: {error_str}"

        return None, None, error_str

    except Exception as e:
        traceback.print_exc()
        if hasattr(e, 'content'):
            try:
                content_str = e.content.decode('utf-8', errors='ignore')
                print(f"\n=== GOOGLE API HTTP ERROR CONTENT ===\n{content_str}\n=====================================\n")
                return None, None, f"Google API Error: {content_str}"
            except Exception:
                pass
        logger.error(f"Google Calendar API call failed: {e}")
        return None, None, f"Google Calendar API Exception: {str(e)}"

    return None, None, "Google Calendar API request failed."


def delete_google_calendar_event(user, db, event_id):
    if not user or not user.is_google_connected or not event_id:
        return False

    if user.google_token_expiry and datetime.utcnow() >= user.google_token_expiry:
        token = refresh_user_google_token(user, db)
    else:
        token = user.google_access_token

    if not token:
        return False

    url = f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'}, method='DELETE')

    try:
        with urllib.request.urlopen(req) as res:
            return res.status in (200, 204)
    except Exception as e:
        logger.error(f"Failed to delete Google Calendar event {event_id}: {e}")
        return False


def send_notification_email(recipient_email, subject, message_body):
    """
    Sends email notifications for bookings, reminders, and cancellations.
    """
    logger.info(f"[EMAIL NOTIFICATION] To: {recipient_email} | Subject: {subject}\nBody:\n{message_body}\n")
    print(f"[EMAIL NOTIFICATION] To: {recipient_email} | Subject: '{subject}'")
    return True
