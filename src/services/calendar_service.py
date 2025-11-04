from datetime import datetime, timedelta
from typing import Any, Optional, Union
import dateparser
import pytz

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.utils.logger import logger

class CalendarService:
    def __init__(self, credentials: Credentials):
        self.service = build('calendar', 'v3', credentials=credentials)
        self.calendar_id = 'primary'
    def create_event(
        self,
        summary: str,
        start_time: Union[str, datetime],
        end_time: Optional[Union[str, datetime]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None
    ) -> dict[str, Any]:
        try:
            if isinstance(start_time, str):
                start_dt = dateparser.parse(start_time)
                if not start_dt:
                    raise ValueError(f"Could not parse start time: {start_time}")
            else:
                start_dt = start_time
            if end_time:
                if isinstance(end_time, str):
                    end_dt = dateparser.parse(end_time)
                    if not end_dt:
                        raise ValueError(f"Could not parse end time: {end_time}")
                else:
                    end_dt = end_time
            else:
                end_dt = start_dt + timedelta(hours=1)
            
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'UTC',
                },
            }
            
            if description:
                event['description'] = description
            
            if location:
                event['location'] = location
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            result = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event,
                sendUpdates='all' if attendees else 'none'
            ).execute()
            
            logger.info(f"Event created: {summary}")
            logger.debug(f"Event ID: {result['id']}")
            
            return result
            
        except HttpError as e:
            logger.error(f"Failed to create event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise
    
    def search_events(
        self,
        query: Optional[str] = None,
        time_min: Optional[Union[str, datetime]] = None,
        time_max: Optional[Union[str, datetime]] = None,
        max_results: int = 10
    ) -> list[dict[str, Any]]:
        try:
            if not time_min:
                time_min = datetime.now()
            elif isinstance(time_min, str):
                time_min = dateparser.parse(time_min)
            if time_max and isinstance(time_max, str):
                time_max = dateparser.parse(time_max)
            
            request_params = {
                'calendarId': self.calendar_id,
                'timeMin': time_min.isoformat() + 'Z',
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime',
            }
            
            if time_max:
                request_params['timeMax'] = time_max.isoformat() + 'Z'
            
            if query:
                request_params['q'] = query
            
            events_result = self.service.events().list(**request_params).execute()
            events = events_result.get('items', [])
            
            if not events:
                logger.info("No events found")
                return []
            
            logger.info(f"Found {len(events)} event(s)")
            return events
            
        except HttpError as e:
            logger.error(f"Failed to search events: {e}")
            return []
    
    def list_events(
        self,
        days_ahead: int = 7,
        max_results: int = 10
    ) -> list[dict[str, Any]]:
        now = datetime.now()
        future = now + timedelta(days=days_ahead)
        return self.search_events(
            time_min=now,
            time_max=future,
            max_results=max_results
        )
    
    def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        try:
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            return event
            
        except HttpError as e:
            logger.error(f"Failed to get event {event_id}: {e}")
            return None
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[Union[str, datetime]] = None,
        end_time: Optional[Union[str, datetime]] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        try:
            event = self.get_event(event_id)
            if not event:
                logger.error(f"Event {event_id} not found")
                return None
            if summary:
                event['summary'] = summary
            
            if start_time:
                if isinstance(start_time, str):
                    start_dt = dateparser.parse(start_time)
                else:
                    start_dt = start_time
                event['start'] = {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'UTC',
                }
            
            if end_time:
                if isinstance(end_time, str):
                    end_dt = dateparser.parse(end_time)
                else:
                    end_dt = end_time
                event['end'] = {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'UTC',
                }
            
            if description:
                event['description'] = description
            
            if location:
                event['location'] = location
            
            result = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"Event updated: {event_id}")
            return result
            
        except HttpError as e:
            logger.error(f"Failed to update event: {e}")
            return None
    
    def delete_event(self, event_id: str) -> bool:
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            logger.info(f"Event deleted: {event_id}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to delete event {event_id}: {e}")
            return False
