import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-4-1106-preview"
    
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    
    log_level: str = "INFO"
    dry_run: bool = False
    
    base_dir: Path = Path(__file__).parent.parent.parent
    credentials_dir: Path = base_dir / "credentials"
    token_path: Path = credentials_dir / "token.json"
    
    gmail_scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify"
    ]
    
    calendar_scopes: list[str] = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    
    drive_scopes: list[str] = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file"
    ]
    
    @property
    def all_scopes(self) -> list[str]:
        return self.gmail_scopes + self.calendar_scopes + self.drive_scopes
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

settings.credentials_dir.mkdir(parents=True, exist_ok=True)
