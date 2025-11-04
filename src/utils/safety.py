from typing import Any, Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import logger

class ActionType(Enum):
    SEND_EMAIL = "send_email"
    DELETE_EMAIL = "delete_email"
    CREATE_EVENT = "create_event"
    DELETE_EVENT = "delete_event"
    SHARE_FILE = "share_file"
    DELETE_FILE = "delete_file"
    MOVE_FILE = "move_file"

@dataclass
class UndoAction:
    action_type: ActionType
    timestamp: datetime
    resource_id: str
    details: Dict[str, Any]
    service: str
    undo_data: Optional[Dict[str, Any]] = None

class SafetyManager:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.undo_stack: List[UndoAction] = []
        self.max_undo_actions = 10
    def is_dry_run(self) -> bool:
        return self.dry_run
    def set_dry_run(self, enabled: bool) -> None:
        self.dry_run = enabled
        logger.info(f"Dry-run mode: {'enabled' if enabled else 'disabled'}")
    def is_destructive(self, intent: str) -> bool:
        destructive_intents = [
            "delete_email",
            "delete_event",
            "delete_file",
            "move_file",
            "send_email",  # Can't unsend
            "share_file",  # Grants access
            "update_event",
            "update_file"
        ]
        return intent in destructive_intents
    
    def requires_confirmation(self, intent: str, parameters: dict) -> bool:
        if self.is_destructive(intent):
            return True
        if intent == "send_email":
            recipients = parameters.get('to', [])
            if isinstance(recipients, list) and len(recipients) > 3:
                return True
            
        if intent == "share_file":
            email = parameters.get('email', '')
            if email and not self._is_internal_email(email):
                return True
        
        return False
    
    def _is_internal_email(self, email: str) -> bool:
        return '@example.com' in email.lower()
    def record_action(
        self,
        action_type: ActionType,
        resource_id: str,
        service: str,
        details: dict,
        undo_data: Optional[dict] = None
    ) -> None:
        action = UndoAction(
            action_type=action_type,
            timestamp=datetime.now(),
            resource_id=resource_id,
            details=details,
            service=service,
            undo_data=undo_data
        )
        self.undo_stack.append(action)
        
        if len(self.undo_stack) > self.max_undo_actions:
            self.undo_stack.pop(0)
        
        logger.debug(f"Recorded action: {action_type.value} on {resource_id}")
    
    def get_last_action(self) -> Optional[UndoAction]:
        return self.undo_stack[-1] if self.undo_stack else None
    def get_undo_stack(self) -> List[UndoAction]:
        return self.undo_stack.copy()
    def can_undo(self, action_type: Optional[ActionType] = None) -> bool:
        if not self.undo_stack:
            return False
        if action_type:
            return any(a.action_type == action_type for a in self.undo_stack)
        
        return True
    
    def pop_last_action(self) -> Optional[UndoAction]:
        return self.undo_stack.pop() if self.undo_stack else None
    def clear_undo_stack(self) -> None:
        self.undo_stack.clear()
        logger.debug("Undo stack cleared")
    def get_action_summary(self, intent: str, parameters: dict) -> str:
        if intent == "send_email":
            to = parameters.get('to', [])
            if isinstance(to, str):
                to = [to]
            subject = parameters.get('subject', 'No subject')
            return f"Send email to {len(to)} recipient(s): '{subject}'"
        elif intent == "delete_email":
            email_id = parameters.get('email_id', 'unknown')
            return f"Delete email {email_id}"
        
        elif intent == "delete_event":
            event_id = parameters.get('event_id', 'unknown')
            return f"Delete calendar event {event_id}"
        
        elif intent == "share_file":
            file_id = parameters.get('file_id', 'unknown')
            email = parameters.get('email', 'unknown')
            role = parameters.get('role', 'reader')
            return f"Share file {file_id} with {email} ({role} access)"
        
        elif intent == "delete_file":
            file_id = parameters.get('file_id', 'unknown')
            return f"Delete file {file_id}"
        
        elif intent == "create_event":
            summary = parameters.get('summary', 'Untitled')
            start = parameters.get('start_time', 'unknown time')
            return f"Create event '{summary}' at {start}"
        
        else:
            return f"Execute {intent}"
    
    def get_risk_level(self, intent: str, parameters: dict) -> str:
        if intent in ["delete_email", "delete_file", "delete_event"]:
            return "high"
        if intent in ["send_email", "share_file"]:
            return "medium"
        
        return "low"
    
    def format_dry_run_result(
        self,
        intent: str,
        parameters: dict,
        would_affect: Optional[str] = None
    ) -> str:
        summary = self.get_action_summary(intent, parameters)
        risk = self.get_risk_level(intent, parameters)
        risk_emoji = {
            "low": "??",
            "medium": "??",
            "high": "??"
        }
        
        message = f"\n[DRY RUN] {risk_emoji.get(risk, '?')} {summary}\n"
        message += f"Risk Level: {risk.upper()}\n"
        
        if would_affect:
            message += f"Would affect: {would_affect}\n"
        
        message += "\nNo changes were made (dry-run mode active)"
        
        return message

class ActionPreview:
    @staticmethod
    def preview_email(parameters: dict) -> str:
        to = parameters.get('to', [])
        if isinstance(to, str):
            to = [to]
        cc = parameters.get('cc', [])
        if isinstance(cc, str):
            cc = [cc]
        
        subject = parameters.get('subject', '(No subject)')
        body = parameters.get('body', '')
        
        if len(body) > 200:
            body = body[:200] + "..."
        
        preview = f"\n?? Email Preview:\n"
        preview += f"  To: {', '.join(to)}\n"
        
        if cc:
            preview += f"  CC: {', '.join(cc)}\n"
        
        preview += f"  Subject: {subject}\n"
        preview += f"  Body:\n    {body}\n"
        
        return preview
    
    @staticmethod
    def preview_event(parameters: dict) -> str:
        summary = parameters.get('summary', 'Untitled Event')
        start = parameters.get('start_time', 'Unknown')
        end = parameters.get('end_time', 'Auto (1 hour)')
        location = parameters.get('location', 'Not specified')
        description = parameters.get('description', 'None')
        attendees = parameters.get('attendees', [])
        preview = f"\n?? Event Preview:\n"
        preview += f"  Title: {summary}\n"
        preview += f"  Start: {start}\n"
        preview += f"  End: {end}\n"
        preview += f"  Location: {location}\n"
        
        if description and description != 'None':
            desc_short = description[:100] + "..." if len(description) > 100 else description
            preview += f"  Description: {desc_short}\n"
        
        if attendees:
            preview += f"  Attendees: {len(attendees)} people\n"
        
        return preview
    
    @staticmethod
    def preview_file_share(parameters: dict, file_name: Optional[str] = None) -> str:
        email = parameters.get('email', parameters.get('emails', 'Unknown'))
        role = parameters.get('role', 'reader')
        file_id = parameters.get('file_id', 'Unknown')
        preview = f"\n?? File Sharing Preview:\n"
        preview += f"  File: {file_name or file_id}\n"
        preview += f"  Share with: {email}\n"
        preview += f"  Access level: {role}\n"
        
        if role == 'writer':
            preview += f"  ??  This grants edit permissions\n"
        elif role == 'owner':
            preview += f"  ??  This transfers ownership\n"
        
        return preview
    
    @staticmethod
    def preview_deletion(resource_type: str, resource_id: str, details: Optional[str] = None) -> str:
        preview = f"\n???  Deletion Preview:\n"
        preview += f"  Type: {resource_type}\n"
        preview += f"  ID: {resource_id}\n"
        if details:
            preview += f"  Details: {details}\n"
        
        preview += f"\n  ??  This action cannot be undone!\n"
        
        return preview
