import base64
from email.mime.text import MIMEText
from typing import Any, Optional, Union

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.logger import logger
from src.utils.resilience import retry_with_backoff, quota_tracker, get_friendly_error_message

class GmailService:
    def __init__(self, credentials: Credentials):
        self.service = build('gmail', 'v1', credentials=credentials)
        self.user_id = 'me'
    def send_email(
        self,
        to: Union[str, list[str]],
        subject: str,
        body: str,
        cc: Optional[Union[str, list[str]]] = None
    ) -> dict[str, Any]:
        try:
            if isinstance(to, str):
                to = [to]
            message = MIMEText(body)
            message['to'] = ', '.join(to)
            message['subject'] = subject
            
            if cc:
                if isinstance(cc, str):
                    cc = [cc]
                message['cc'] = ', '.join(cc)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            result = self.service.users().messages().send(
                userId=self.user_id,
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {', '.join(to)}")
            logger.debug(f"Message ID: {result['id']}")
            
            return result
            
        except HttpError as e:
            logger.error(f"Failed to send email: {e}")
            raise
    
    def search_emails(
        self,
        query: str,
        max_results: int = 10,
        label_ids: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        try:
            results = self.service.users().messages().list(
                userId=self.user_id,
                q=query,
                maxResults=max_results,
                labelIds=label_ids
            ).execute()
            messages = results.get('messages', [])
            
            if not messages:
                logger.info(f"No emails found for query: {query}")
                return []
            
            detailed_messages = []
            for msg in messages:
                full_msg = self.get_email(msg['id'])
                if full_msg:
                    detailed_messages.append(full_msg)
            
            logger.info(f"Found {len(detailed_messages)} emails")
            return detailed_messages
            
        except HttpError as e:
            logger.error(f"Failed to search emails: {e}")
            return []
    
    def get_email(self, message_id: str) -> Optional[dict[str, Any]]:
        try:
            message = self.service.users().messages().get(
                userId=self.user_id,
                id=message_id,
                format='full'
            ).execute()
            return message
            
        except HttpError as e:
            logger.error(f"Failed to get email {message_id}: {e}")
            return None
    
    def delete_email(self, message_id: str) -> bool:
        try:
            self.service.users().messages().trash(
                userId=self.user_id,
                id=message_id
            ).execute()
            logger.info(f"Email {message_id} moved to trash")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to delete email {message_id}: {e}")
            return False
    
    def get_profile(self) -> Optional[dict[str, Any]]:
        try:
            profile = self.service.users().getProfile(userId=self.user_id).execute()
            return profile
        except HttpError as e:
            logger.error(f"Failed to get profile: {e}")
            return None
