from typing import Optional

from pydantic import BaseModel, Field

from src.llm.client import LLMClient
from src.llm.prompts import GMAIL_SYSTEM_PROMPT, CALENDAR_SYSTEM_PROMPT, DRIVE_SYSTEM_PROMPT
from src.utils.logger import logger

class Intent(BaseModel):
    intent: str = Field(..., description="The action to perform")
    parameters: dict = Field(default_factory=dict, description="Parameters for the action")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reasoning: Optional[str] = Field(None, description="Explanation if confidence is low")

class IntentParser:
    def __init__(self):
        self.llm = LLMClient()
    def parse_gmail_command(self, user_message: str) -> Optional[Intent]:
        return self.llm.parse_intent(
            user_message=user_message,
            system_prompt=GMAIL_SYSTEM_PROMPT,
            response_model=Intent
        )
    def parse_calendar_command(self, user_message: str) -> Optional[Intent]:
        return self.llm.parse_intent(
            user_message=user_message,
            system_prompt=CALENDAR_SYSTEM_PROMPT,
            response_model=Intent
        )
    def parse_drive_command(self, user_message: str) -> Optional[Intent]:
        return self.llm.parse_intent(
            user_message=user_message,
            system_prompt=DRIVE_SYSTEM_PROMPT,
            response_model=Intent
        )
    def parse_command(self, user_message: str) -> tuple[Optional[Intent], str]:
        message_lower = user_message.lower()
        calendar_keywords = ['meeting', 'event', 'schedule', 'calendar', 'appointment', 
                            'remind', 'tomorrow', 'next week', 'today at']
        if any(keyword in message_lower for keyword in calendar_keywords):
            intent = self.parse_calendar_command(user_message)
            return (intent, 'calendar')
        
        drive_keywords = ['file', 'folder', 'document', 'drive', 'upload', 'download', 
                         'share', 'pdf', 'doc', 'spreadsheet']
        if any(keyword in message_lower for keyword in drive_keywords):
            intent = self.parse_drive_command(user_message)
            return (intent, 'drive')
        
        intent = self.parse_gmail_command(user_message)
        return (intent, 'gmail')
    
    def is_confident(self, intent: Intent, threshold: float = 0.7) -> bool:
        is_conf = intent.confidence >= threshold
        if not is_conf and intent.reasoning:
            logger.warning(f"Low confidence: {intent.reasoning}")
        
        return is_conf
