from typing import Any, Optional, Dict, List
from datetime import datetime

from src.utils.logger import logger

class ContextInferenceEngine:
    def __init__(self, session=None, gmail_service=None, calendar_service=None, drive_service=None):
        self.session = session
        self.gmail_service = gmail_service
        self.calendar_service = calendar_service
        self.drive_service = drive_service
    def infer_parameters(self, command: str, intent: str, parameters: dict) -> dict:
        enhanced_params = parameters.copy()
        command_lower = command.lower()
        if intent in ["search_event", "update_event", "delete_event", "list_events"]:
            enhanced_params = self._infer_meeting_params(command_lower, enhanced_params)
        
        if intent in ["send_email", "read_email", "delete_email", "search_email"]:
            enhanced_params = self._infer_email_params(command_lower, enhanced_params)
        
        if intent == "send_email" and "attendees" in command_lower:
            enhanced_params = self._infer_attendees(command_lower, enhanced_params)
        
        enhanced_params = self._resolve_pronouns(command_lower, intent, enhanced_params)
        
        return enhanced_params
    
    def _infer_meeting_params(self, command: str, params: dict) -> dict:
        if "next meeting" in command or "upcoming meeting" in command:
            if self.calendar_service:
                try:
                    events = self.calendar_service.list_events(days_ahead=7, max_results=1)
                    if events:
                        next_event = events[0]
                        logger.info(f"Inferred next meeting: {next_event.get('summary')}")
                        if self.session:
                            self.session.references['next_meeting'] = next_event
                        
                        params['inferred_event'] = next_event
                        params['event_id'] = next_event.get('id')
                        params['summary'] = next_event.get('summary')
                        
                except Exception as e:
                    logger.warning(f"Failed to infer next meeting: {e}")
        
        if "today" in command and "meeting" in command:
            params['days'] = 1
        elif "this week" in command:
            params['days'] = 7
        elif "next week" in command:
            params['days'] = 14
        
        return params
    
    def _infer_email_params(self, command: str, params: dict) -> dict:
        if "last email" in command and "from" in command:
            from_idx = command.find("from")
            if from_idx != -1:
                sender_part = command[from_idx + 5:].strip()
                sender = sender_part.split()[0] if sender_part else None
                if sender and self.gmail_service:
                    try:
                        emails = self.gmail_service.search_emails(
                            f"from:{sender}",
                            max_results=1
                        )
                        if emails:
                            last_email = emails[0]
                            logger.info(f"Inferred last email from {sender}")
                            
                            params['inferred_email'] = last_email
                            params['email_id'] = last_email.get('id')
                            
                    except Exception as e:
                        logger.warning(f"Failed to infer last email: {e}")
        
        if "unread" in command:
            if 'query' in params and params['query']:
                params['query'] += " is:unread"
            else:
                params['query'] = "is:unread"
        
        if "important" in command or "priority" in command:
            if 'query' in params and params['query']:
                params['query'] += " is:important"
            else:
                params['query'] = "is:important"
        
        import re
        
        days_match = re.search(r'last\s+(\d+)\s+days?', command)
        if days_match:
            days = days_match.group(1)
            date_filter = f"newer_than:{days}d"
            if 'query' in params and params['query']:
                params['query'] += f" {date_filter}"
            else:
                params['query'] = date_filter
        
        weeks_match = re.search(r'last\s+(\d+)\s+weeks?', command)
        if weeks_match:
            weeks = int(weeks_match.group(1))
            days = weeks * 7
            date_filter = f"newer_than:{days}d"
            if 'query' in params and params['query']:
                params['query'] += f" {date_filter}"
            else:
                params['query'] = date_filter
        
        months_match = re.search(r'last\s+(\d+)\s+months?', command)
        if months_match:
            months = int(months_match.group(1))
            days = months * 30
            date_filter = f"newer_than:{days}d"
            if 'query' in params and params['query']:
                params['query'] += f" {date_filter}"
            else:
                params['query'] = date_filter
        
        if "last week" in command and not weeks_match:
            date_filter = "newer_than:7d"
            if 'query' in params and params['query']:
                params['query'] += f" {date_filter}"
            else:
                params['query'] = date_filter
        
        if "last month" in command and not months_match:
            date_filter = "newer_than:30d"
            if 'query' in params and params['query']:
                params['query'] += f" {date_filter}"
            else:
                params['query'] = date_filter
        
        return params
    
    def _infer_attendees(self, command: str, params: dict) -> dict:
        attendees = []
        if "meeting attendees" in command or "event attendees" in command:
            if self.session:
                last_event = self.session.references.get('next_meeting') or \
                             self.session.references.get('last_event')
                
                if last_event and 'attendees' in last_event:
                    attendees = [
                        attendee.get('email') 
                        for attendee in last_event['attendees'] 
                        if 'email' in attendee
                    ]
                    logger.info(f"Inferred {len(attendees)} attendees from event")
        
        elif "the attendees" in command or "all attendees" in command:
            if self.session:
                last_cmd = self.session.get_last_command()
                if last_cmd and last_cmd.service == "calendar":
                    if last_cmd.result and isinstance(last_cmd.result, list):
                        for event in last_cmd.result:
                            if 'attendees' in event:
                                attendees.extend([
                                    a.get('email') 
                                    for a in event['attendees'] 
                                    if 'email' in a
                                ])
                        logger.info(f"Inferred {len(attendees)} attendees from last calendar command")
        
        if attendees:
            if 'to' not in params or not params['to']:
                params['to'] = attendees
            elif isinstance(params['to'], list):
                params['to'].extend(attendees)
            else:
                params['to'] = [params['to']] + attendees
            
            params['inferred_attendees'] = True
        
        return params
    
    def _resolve_pronouns(self, command: str, intent: str, params: dict) -> dict:
        if not self.session:
            return params
        if command in ["it", "that", "this"] or \
           " it " in f" {command} " or " that " in f" {command} " or " this " in f" {command} ":
            
            if intent in ["share_file", "download_file", "delete_file"]:
                last_file = self.session.references.get('last_file')
                if last_file:
                    params['file_id'] = last_file.get('id')
                    params['inferred_file'] = last_file
                    logger.info(f"Resolved 'it' to file: {last_file.get('name', last_file.get('id'))}")
            
            elif intent in ["read_email", "delete_email"]:
                last_email = self.session.references.get('last_email')
                if last_email:
                    params['email_id'] = last_email.get('id')
                    params['inferred_email'] = last_email
                    logger.info(f"Resolved 'it' to email: {last_email.get('id')}")
            
            elif intent in ["update_event", "delete_event"]:
                last_event = self.session.references.get('last_event')
                if last_event:
                    params['event_id'] = last_event.get('id')
                    params['inferred_event'] = last_event
                    logger.info(f"Resolved 'it' to event: {last_event.get('summary')}")
        
        if " them " in f" {command} " or command.startswith("them"):
            last_event = self.session.references.get('next_meeting') or \
                        self.session.references.get('last_event')
            
            if last_event and 'attendees' in last_event:
                attendees = [
                    a.get('email') 
                    for a in last_event['attendees'] 
                    if 'email' in a
                ]
                
                if attendees:
                    if intent == "send_email":
                        params['to'] = attendees
                        logger.info(f"Resolved 'them' to {len(attendees)} attendees")
                    elif intent == "share_file":
                        params['emails'] = attendees
                        params['email'] = attendees[0] if len(attendees) == 1 else attendees
                        logger.info(f"Resolved 'them' to {len(attendees)} attendees for sharing")
        
        return params
    
    def get_smart_suggestions(self) -> List[str]:
        suggestions = []
        if not self.session:
            return suggestions
        
        if self.gmail_service:
            try:
                unread = self.gmail_service.search_emails("is:unread", max_results=1)
                if unread:
                    suggestions.append("You have unread emails")
            except:
                pass
        
        if self.calendar_service:
            try:
                events = self.calendar_service.list_events(days_ahead=1, max_results=1)
                if events:
                    next_event = events[0]
                    summary = next_event.get('summary', 'Meeting')
                    suggestions.append(f"Upcoming: {summary}")
            except:
                pass
        
        return suggestions
