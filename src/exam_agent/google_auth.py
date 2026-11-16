"""OAuth login for Google APIs (Gmail, Calendar). No passwords: login happens in the browser.

Each service gets its own token file with only its own permission, so the Gmail
token stays read-only even though the Calendar token can write.
"""

import os
from pathlib import Path

PROJECT = Path(__file__).parents[2]
SECRETS = PROJECT / ".secrets"  # gitignored


def connect(api: str, version: str, scopes: list[str], token_file: Path):
    """Return a Google API service, logging in through the browser if needed."""
    # Imported here so that tests and --fake runs don't need the Google libraries loaded.
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None  # refresh token expired or revoked: log in again
    if not creds or not creds.valid:
        client_config = {
            "installed": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, scopes)
        print(f"Opening the browser to allow {api} access ({', '.join(s.rsplit('/', 1)[-1] for s in scopes)})...")
        creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(mode=0o700, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        token_file.chmod(0o600)
    return build(api, version, credentials=creds, cache_discovery=False)
