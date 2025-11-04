import json
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config.settings import settings
from src.utils.logger import logger

class GoogleAuthenticator:
    def __init__(self, scopes: Optional[list[str]] = None):
        self.scopes = scopes or settings.all_scopes
        self.token_path = settings.token_path
        self.credentials: Optional[Credentials] = None
    def authenticate(self) -> Credentials:
        self.credentials = self._load_token()
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            logger.info("Refreshing expired token...")
            self.credentials.refresh(Request())
            self._save_token()
            logger.info("Token refreshed successfully")
        
        if not self.credentials or not self.credentials.valid:
            logger.info("No valid credentials found. Starting OAuth flow...")
            self.credentials = self._run_oauth_flow()
            self._save_token()
            logger.info("Authentication successful!")
        
        return self.credentials
    
    def _load_token(self) -> Optional[Credentials]:
        if not self.token_path.exists():
            return None
        try:
            return Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
        except Exception as e:
            logger.warning(f"Failed to load token: {e}")
            return None
    
    def _save_token(self) -> None:
        if not self.credentials:
            return
        token_data = {
            'token': self.credentials.token,
            'refresh_token': self.credentials.refresh_token,
            'token_uri': self.credentials.token_uri,
            'client_id': self.credentials.client_id,
            'client_secret': self.credentials.client_secret,
            'scopes': self.credentials.scopes
        }
        
        self.token_path.write_text(json.dumps(token_data, indent=2))
        logger.debug(f"Token saved to {self.token_path}")
    
    def _run_oauth_flow(self) -> Credentials:
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError(
                "Google OAuth credentials not configured. "
                "Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
            )
        client_config = {
            "installed": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
        credentials = flow.run_local_server(port=0)
        
        return credentials
    
    def revoke(self) -> None:
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Token revoked and deleted")
