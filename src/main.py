import sys
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.auth.google_auth import GoogleAuthenticator
from src.orchestrator.intent_parser import IntentParser
from src.orchestrator.workflow_engine import WorkflowEngine, WorkflowContext
from src.services.gmail_service import GmailService
from src.services.calendar_service import CalendarService
from src.services.drive_service import DriveService
from src.utils.logger import logger
from src.utils.session import SessionManager, SessionContext
from src.utils.context_inference import ContextInferenceEngine
from src.utils.safety import SafetyManager, ActionType, ActionPreview

console = Console()

class Orchestrator:
    def __init__(self, auto_confirm: bool = False, dry_run: bool = False):
        self.authenticator = GoogleAuthenticator()
        self.intent_parser = IntentParser()
        self.workflow_engine = WorkflowEngine()
        self.gmail_service: Optional[GmailService] = None
        self.calendar_service: Optional[CalendarService] = None
        self.drive_service: Optional[DriveService] = None
        self.authenticated = False
        self.auto_confirm = auto_confirm
        self.session_manager = SessionManager()
        self.session: Optional[SessionContext] = None
        
        self.inference_engine: Optional[ContextInferenceEngine] = None
        
        self.safety_manager = SafetyManager(dry_run=dry_run)
    
    def authenticate(self) -> bool:
        try:
            console.print("[yellow]Authenticating with Google...[/yellow]")
            credentials = self.authenticator.authenticate()
            self.gmail_service = GmailService(credentials)
            self.calendar_service = CalendarService(credentials)
            self.drive_service = DriveService(credentials)
            
            profile = self.gmail_service.get_profile()
            if profile:
                email = profile.get('emailAddress', 'Unknown')
                console.print(f"[green]?[/green] Authenticated as: {email}")
                console.print(f"[green]?[/green] Services: Gmail, Calendar, Drive")
                self.authenticated = True
                
                self.session = self.session_manager.start_session(session_id=email)
                logger.info(f"Session started for {email}")
                
                self.inference_engine = ContextInferenceEngine(
                    session=self.session,
                    gmail_service=self.gmail_service,
                    calendar_service=self.calendar_service,
                    drive_service=self.drive_service
                )
                logger.info("Context inference engine initialized")
                
                return True
            else:
                console.print("[red]?[/red] Failed to verify authentication")
                return False
                
        except Exception as e:
            console.print(f"[red]?[/red] Authentication failed: {e}")
            logger.error(f"Authentication error: {e}")
            return False
    
    def process_command(self, command: str) -> None:
        if not self.authenticated:
            console.print("[red]Error:[/red] Not authenticated. Run with --auth first.")
            return
        console.print(f"\n[cyan]Processing:[/cyan] {command}")
        
        smart_result = self._handle_smart_queries(command)
        if smart_result:
            return
        
        if self.session:
            ref_type, ref_value = self.session.resolve_reference(command)
            if ref_type and ref_value:
                console.print(f"[dim]Resolved reference: {ref_type}[/dim]")
                logger.debug(f"Reference resolved: {ref_type} -> {ref_value}")
        
        multi_intent = self.workflow_engine.detect_multi_service(command)
        
        if multi_intent and multi_intent.multi_service:
            console.print(f"[magenta]?? Multi-Service Workflow Detected![/magenta]")
            console.print(f"[green]?[/green] Services: {', '.join(multi_intent.services).upper()}")
            console.print(f"[green]?[/green] Operations: {len(multi_intent.operations)}")
            console.print(f"[dim]Reasoning: {multi_intent.reasoning}[/dim]")
            
            self._execute_workflow(multi_intent)
            return
        
        intent, service = self.intent_parser.parse_command(command)
        
        if not intent:
            console.print("[red]?[/red] Could not understand the command")
            return
        
        if not self.intent_parser.is_confident(intent):
            console.print(f"[yellow]?[/yellow] Low confidence ({intent.confidence:.2f})")
            if not self.auto_confirm and not click.confirm("Continue anyway?", default=True):
                return
        
        if self.inference_engine:
            original_params = intent.parameters.copy()
            intent.parameters = self.inference_engine.infer_parameters(
                command=command,
                intent=intent.intent,
                parameters=intent.parameters
            )
            
            if intent.parameters != original_params:
                inferred_keys = [k for k in intent.parameters if k not in original_params or intent.parameters[k] != original_params.get(k)]
                if inferred_keys:
                    console.print(f"[dim]Inferred: {', '.join(inferred_keys)}[/dim]")
        
        console.print(f"[green]?[/green] Service: {service.upper()}")
        console.print(f"[green]?[/green] Intent: {intent.intent}")
        console.print(f"[green]?[/green] Parameters: {intent.parameters}")
        
        result = None
        success = False
        error_msg = None
        
        try:
            if service == 'gmail':
                result = self._handle_gmail_intent(intent)
                success = True
            elif service == 'calendar':
                result = self._handle_calendar_intent(intent)
                success = True
            elif service == 'drive':
                result = self._handle_drive_intent(intent)
                success = True
            else:
                console.print(f"[red]?[/red] Unknown service: {service}")
                error_msg = f"Unknown service: {service}"
        except Exception as e:
            console.print(f"[red]?[/red] Error executing command: {e}")
            logger.error(f"Execution error: {e}", exc_info=True)
            error_msg = str(e)
        
        if self.session:
            self.session.add_command(
                command=command,
                service=service,
                intent=intent.intent,
                parameters=intent.parameters,
                result=result,
                success=success,
                error=error_msg
            )
            logger.debug(f"Command stored in session. History length: {len(self.session.history)}")
    
    def _execute_workflow(self, multi_intent) -> None:
        steps = self.workflow_engine.create_workflow(multi_intent)
        context = WorkflowContext()
        console.print(f"\n[bold cyan]Executing Workflow:[/bold cyan]")
        
        for i, step in enumerate(steps):
            console.print(f"\n[yellow]Step {i+1}/{len(steps)}:[/yellow] {step.service.upper()} - {step.intent}")
            
            if not self.workflow_engine.can_execute_step(step, context.completed_steps):
                console.print(f"[yellow]?[/yellow] Waiting for dependencies...")
                continue
            
            step = self.workflow_engine.inject_context(step, context.results)
            
            try:
                result = self._execute_step(step)
                context.add_result(i, result)
                if result is not None:
                    console.print(f"[green]?[/green] Step {i+1} completed")
                else:
                    console.print(f"[yellow]?[/yellow] Step {i+1} completed (no result)")
            except Exception as e:
                console.print(f"[red]?[/red] Step {i+1} failed: {e}")
                context.mark_failed(i)
                logger.error(f"Step {i} failed: {e}")
                
                if not self.auto_confirm and not click.confirm("Continue with remaining steps?", default=True):
                    break
        
        console.print(f"\n[bold]Workflow Summary:[/bold]")
        console.print(f"[green]?[/green] Completed: {len(context.completed_steps)}/{len(steps)}")
        if context.failed_steps:
            console.print(f"[red]?[/red] Failed: {len(context.failed_steps)}")
    
    def _execute_step(self, step):
        from src.orchestrator.intent_parser import Intent
        intent = Intent(
            intent=step.intent,
            parameters=step.parameters,
            confidence=0.9
        )
        
        if step.service == 'gmail':
            return self._execute_gmail_step(intent)
        elif step.service == 'calendar':
            return self._execute_calendar_step(intent)
        elif step.service == 'drive':
            return self._execute_drive_step(intent)
        else:
            raise ValueError(f"Unknown service: {step.service}")
    
    def _execute_gmail_step(self, intent):
        intent_name = intent.intent.lower().replace('_', '')
        
        if intent_name in ["sendemail", "send"]:
            params = intent.parameters
            result = self.gmail_service.send_email(
                to=params.get('to', params.get('emails', [])),
                subject=params['subject'],
                body=params['body']
            )
            return result
        elif intent_name in ["searchemail", "searchemails", "search"]:
            params = intent.parameters
            query = params.get('query', '')
            if not query and 'is:unread' not in query:
                query = "is:unread"
            if 'from' in params:
                query += f" from:{params['from']}"
            if 'emails' in params or 'email' in params:
                email_list = params.get('emails') or [params.get('email')]
                if email_list:
                    email_filter = ' OR '.join([f"from:{email}" for email in email_list if email])
                    query = f"{query} ({email_filter})" if query else f"({email_filter})"
            return self.gmail_service.search_emails(query, max_results=20)
        else:
            return self._handle_gmail_intent(intent)
    def _execute_calendar_step(self, intent):
        if intent.intent == "create_event":
            params = intent.parameters
            result = self.calendar_service.create_event(
                summary=params['summary'],
                start_time=params['start_time'],
                end_time=params.get('end_time'),
                description=params.get('description'),
                attendees=params.get('attendees')
            )
            return result
        elif intent.intent == "search_event":
            return self.calendar_service.search_events(
                query=intent.parameters.get('query'),
                max_results=20
            )
        elif intent.intent == "list_events":
            return self.calendar_service.list_events(
                days_ahead=intent.parameters.get('days', 7)
            )
        else:
            self._handle_calendar_intent(intent)
            return None
    def _execute_drive_step(self, intent):
        intent_name = intent.intent.lower().replace('_', '')
        
        if intent_name in ["searchfile", "searchfiles", "searchdocument", "search"]:
            query = intent.parameters.get('query', '')
            if 'email' in query.lower() or 'doc' in query.lower():
                query = query.replace('email', '').replace('doc', '').strip()
            return self.drive_service.search_files(
                query=query,
                max_results=20
            )
        elif intent_name in ["sharefile", "share"]:
            params = intent.parameters
            file_ids = []
            if 'file_id' in params:
                file_ids = [params['file_id']]
            elif 'items' in params:
                file_ids = [item.get('id') for item in params['items'] if 'id' in item]
            emails = params.get('emails', params.get('email', []))
            if isinstance(emails, str):
                emails = [emails]
            
            results = []
            for file_id in file_ids[:1]:
                for email in emails:
                    success = self.drive_service.share_file(
                        file_id=file_id,
                        email=email,
                        role=params.get('role', 'reader')
                    )
                    results.append(success)
            return results
        else:
            return self._handle_drive_intent(intent)
    
    
    def _handle_gmail_intent(self, intent):
        if intent.intent == "send_email":
            return self._handle_send_email(intent)
        elif intent.intent == "search_email":
            return self._handle_search_email(intent)
        elif intent.intent == "read_email":
            return self._handle_read_email(intent)
        elif intent.intent == "delete_email":
            return self._handle_delete_email(intent)
        else:
            console.print(f"[yellow]?[/yellow] Gmail intent '{intent.intent}' not implemented yet")
            return None
    def _handle_send_email(self, intent) -> None:
        params = intent.parameters
        if not all(k in params for k in ['to', 'subject', 'body']):
            console.print("[red]?[/red] Missing required parameters (to, subject, body)")
            return
        
        preview = ActionPreview.preview_email(params)
        console.print(preview)
        
        if self.safety_manager.is_dry_run():
            dry_result = self.safety_manager.format_dry_run_result(
                "send_email",
                params,
                would_affect=f"{len(params.get('to', []))} recipient(s)"
            )
            console.print(f"[yellow]{dry_result}[/yellow]")
            return
        
        if not self.auto_confirm and not click.confirm("Send this email?", default=True):
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        result = self.gmail_service.send_email(
            to=params['to'],
            subject=params['subject'],
            body=params['body']
        )
        
        self.safety_manager.record_action(
            action_type=ActionType.SEND_EMAIL,
            resource_id=result['id'],
            service='gmail',
            details={'to': params['to'], 'subject': params['subject']},
            undo_data=None
        )
        
        console.print(f"[green]?[/green] Email sent! Message ID: {result['id']}")
    
    def _handle_search_email(self, intent):
        params = intent.parameters
        query_parts = []
        if 'query' in params and params['query']:
            query_parts.append(params['query'])
        if 'from' in params:
            query_parts.append(f"from:{params['from']}")
        if 'after' in params:
            query_parts.append(f"after:{params['after']}")
        if 'before' in params:
            query_parts.append(f"before:{params['before']}")
        
        query = ' '.join(query_parts) if query_parts else params.get('query', '')
        
        if not query:
            console.print("[red]?[/red] No search query provided")
            return None
        
        console.print(f"[cyan]Searching for:[/cyan] {query}")
        emails = self.gmail_service.search_emails(query, max_results=20)
        
        if not emails:
            console.print("[yellow]No emails found[/yellow]")
            return []
        
        console.print(f"\n[green]Found {len(emails)} email(s):[/green]\n")
        for i, email in enumerate(emails, 1):
            headers = {h['name']: h['value'] for h in email['payload']['headers']}
            subject = headers.get('Subject', 'No subject')
            from_addr = headers.get('From', 'Unknown')
            
            console.print(f"{i}. [bold]{subject}[/bold]")
            console.print(f"   From: {from_addr}")
            console.print(f"   ID: {email['id']}\n")
        
        return emails
    
    def _handle_read_email(self, intent) -> None:
        console.print("[yellow]?[/yellow] read_email not fully implemented yet")
    def _handle_delete_email(self, intent) -> None:
        console.print("[yellow]?[/yellow] delete_email not fully implemented yet")
    
    def _handle_calendar_intent(self, intent):
        if intent.intent == "create_event":
            return self._handle_create_event(intent)
        elif intent.intent == "search_event":
            return self._handle_search_event(intent)
        elif intent.intent == "list_events":
            return self._handle_list_events(intent)
        elif intent.intent == "update_event":
            return self._handle_update_event(intent)
        elif intent.intent == "delete_event":
            return self._handle_delete_event(intent)
        else:
            console.print(f"[yellow]?[/yellow] Calendar intent '{intent.intent}' not implemented yet")
            return None
    def _handle_create_event(self, intent) -> None:
        params = intent.parameters
        if 'summary' not in params or 'start_time' not in params:
            console.print("[red]?[/red] Missing required parameters (summary, start_time)")
            return
        
        console.print(Panel.fit(
            f"[bold]Event:[/bold] {params['summary']}\n"
            f"[bold]Start:[/bold] {params['start_time']}\n"
            f"[bold]End:[/bold] {params.get('end_time', 'Auto (1 hour)')}\n"
            f"[bold]Description:[/bold] {params.get('description', 'None')}",
            title="Event Preview"
        ))
        
        if not self.auto_confirm and not click.confirm("Create this event?", default=True):
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        result = self.calendar_service.create_event(
            summary=params['summary'],
            start_time=params['start_time'],
            end_time=params.get('end_time'),
            description=params.get('description'),
            location=params.get('location'),
            attendees=params.get('attendees')
        )
        
        console.print(f"[green]?[/green] Event created! ID: {result['id']}")
        if 'htmlLink' in result:
            console.print(f"[cyan]Link:[/cyan] {result['htmlLink']}")
    
    def _handle_search_event(self, intent) -> None:
        params = intent.parameters
        events = self.calendar_service.search_events(
            query=params.get('query'),
            time_min=params.get('time_min'),
            time_max=params.get('time_max'),
            max_results=20
        )
        
        if not events:
            console.print("[yellow]No events found[/yellow]")
            return
        
        console.print(f"\n[green]Found {len(events)} event(s):[/green]\n")
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            console.print(f"{i}. [bold]{event['summary']}[/bold]")
            console.print(f"   When: {start}")
            console.print(f"   ID: {event['id']}\n")
    
    def _handle_list_events(self, intent):
        params = intent.parameters
        days = params.get('days', 7)
        console.print(f"[cyan]Listing events for next {days} days...[/cyan]")
        events = self.calendar_service.list_events(days_ahead=days)
        
        if not events:
            console.print("[yellow]No upcoming events[/yellow]")
            return []
        
        console.print(f"\n[green]Found {len(events)} event(s):[/green]\n")
        for i, event in enumerate(events, 1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            console.print(f"{i}. [bold]{event['summary']}[/bold]")
            console.print(f"   When: {start}\n")
        
        return events
    
    def _handle_update_event(self, intent) -> None:
        console.print("[yellow]?[/yellow] update_event not fully implemented yet")
    def _handle_delete_event(self, intent) -> None:
        console.print("[yellow]?[/yellow] delete_event not fully implemented yet")
    
    def _handle_drive_intent(self, intent):
        if intent.intent == "search_file":
            return self._handle_search_file(intent)
        elif intent.intent == "upload_file":
            return self._handle_upload_file(intent)
        elif intent.intent == "download_file":
            return self._handle_download_file(intent)
        elif intent.intent == "share_file":
            return self._handle_share_file(intent)
        elif intent.intent == "create_folder":
            return self._handle_create_folder(intent)
        else:
            console.print(f"[yellow]?[/yellow] Drive intent '{intent.intent}' not implemented yet")
            return None
    def _handle_search_file(self, intent):
        params = intent.parameters
        console.print(f"[cyan]Searching for:[/cyan] {params.get('query', 'files')}")
        files = self.drive_service.search_files(
            query=params.get('query'),
            mime_type=params.get('mime_type'),
            max_results=20
        )
        
        if not files:
            console.print("[yellow]No files found[/yellow]")
            return []
        
        console.print(f"\n[green]Found {len(files)} file(s):[/green]\n")
        for i, file in enumerate(files, 1):
            console.print(f"{i}. [bold]{file['name']}[/bold]")
            console.print(f"   Type: {file.get('mimeType', 'Unknown')}")
            console.print(f"   ID: {file['id']}\n")
        
        return files
    
    def _handle_upload_file(self, intent) -> None:
        params = intent.parameters
        if 'local_path' not in params:
            console.print("[red]?[/red] Missing required parameter: local_path")
            return
        
        result = self.drive_service.upload_file(
            file_path=params['local_path'],
            name=params.get('name'),
            folder_id=params.get('folder_id')
        )
        
        if result:
            console.print(f"[green]?[/green] File uploaded! ID: {result['id']}")
            if 'webViewLink' in result:
                console.print(f"[cyan]Link:[/cyan] {result['webViewLink']}")
        else:
            console.print("[red]?[/red] Upload failed")
    
    def _handle_download_file(self, intent) -> None:
        console.print("[yellow]?[/yellow] download_file not fully implemented yet")
    def _handle_share_file(self, intent) -> None:
        params = intent.parameters
        if 'file_id' not in params or 'email' not in params:
            console.print("[red]?[/red] Missing required parameters (file_id, email)")
            return
        
        success = self.drive_service.share_file(
            file_id=params['file_id'],
            email=params['email'],
            role=params.get('role', 'reader')
        )
        
        if success:
            console.print(f"[green]?[/green] File shared with {params['email']}")
        else:
            console.print("[red]?[/red] Sharing failed")
    
    def _handle_create_folder(self, intent) -> None:
        params = intent.parameters
        if 'name' not in params:
            console.print("[red]?[/red] Missing required parameter: name")
            return
        
        result = self.drive_service.create_folder(
            name=params['name'],
            parent_id=params.get('parent_id')
        )
        
        if result:
            console.print(f"[green]?[/green] Folder created! ID: {result['id']}")
        else:
            console.print("[red]?[/red] Folder creation failed")
    
    def _handle_smart_queries(self, command: str) -> bool:
        command_lower = command.lower()
        if any(phrase in command_lower for phrase in ["next meeting", "upcoming meeting", "next event"]):
            if self.calendar_service:
                try:
                    events = self.calendar_service.list_events(days_ahead=7, max_results=1)
                    if events:
                        event = events[0]
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        summary = event['summary']
                        
                        console.print(f"\n[green]?[/green] Your next meeting:")
                        console.print(f"  [bold]{summary}[/bold]")
                        console.print(f"  [cyan]When:[/cyan] {start}")
                        
                        if 'attendees' in event:
                            console.print(f"  [cyan]Attendees:[/cyan] {len(event['attendees'])} people")
                        
                        if self.session:
                            self.session.references['next_meeting'] = event
                            self.session.add_command(
                                command=command,
                                service="calendar",
                                intent="get_next_meeting",
                                parameters={},
                                result=event,
                                success=True
                            )
                        
                        return True
                    else:
                        console.print("[yellow]No upcoming meetings found[/yellow]")
                        return True
                except Exception as e:
                    logger.error(f"Failed to get next meeting: {e}")
                    return False
        
        if any(phrase in command_lower for phrase in ["unread emails", "unread messages", "any unread"]):
            if self.gmail_service:
                try:
                    unread = self.gmail_service.search_emails("is:unread", max_results=20)
                    if unread:
                        console.print(f"\n[green]?[/green] You have {len(unread)} unread email(s):")
                        for i, email in enumerate(unread[:3], 1):
                            headers = {h['name']: h['value'] for h in email['payload']['headers']}
                            subject = headers.get('Subject', 'No subject')
                            from_addr = headers.get('From', 'Unknown')
                            console.print(f"  {i}. {subject}")
                            console.print(f"     From: {from_addr}")
                        
                        if len(unread) > 3:
                            console.print(f"  ... and {len(unread) - 3} more")
                        
                        return True
                    else:
                        console.print("[green]?[/green] No unread emails!")
                        return True
                except Exception as e:
                    logger.error(f"Failed to check unread emails: {e}")
                    return False
        
        return False
    
    def show_history(self) -> None:
        if not self.session or not self.session.history:
            console.print("[yellow]No command history[/yellow]")
            return
        console.print(f"\n[bold cyan]Command History:[/bold cyan] ({len(self.session.history)} commands)\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Service", width=8)
        table.add_column("Intent", width=15)
        table.add_column("Command", width=40)
        table.add_column("Status", width=6)
        
        for i, cmd in enumerate(self.session.history, 1):
            time_str = cmd.timestamp.strftime("%H:%M:%S")
            status = "[green]?[/green]" if cmd.success else "[red]?[/red]"
            command_short = cmd.command[:40] + "..." if len(cmd.command) > 40 else cmd.command
            
            table.add_row(
                str(i),
                time_str,
                cmd.service.upper(),
                cmd.intent,
                command_short,
                status
            )
        
        console.print(table)
        
        if self.session.references:
            console.print(f"\n[bold]Available References:[/bold]")
            if "last_email" in self.session.references:
                console.print("  ? last_email / that email")
            if "next_meeting" in self.session.references:
                console.print("  ? next_meeting / that meeting")
            if "last_file" in self.session.references:
                console.print("  ? last_file / that file")
            console.print()
    
    def show_suggestions(self) -> None:
        if not self.inference_engine:
            console.print("[yellow]Suggestions not available[/yellow]")
            return
        console.print(f"\n[bold cyan]Smart Suggestions:[/bold cyan]\n")
        
        suggestions = self.inference_engine.get_smart_suggestions()
        
        if suggestions:
            for suggestion in suggestions:
                console.print(f"  ? {suggestion}")
        else:
            console.print("[dim]No suggestions at this time[/dim]")
        
        if self.session and self.session.history:
            last_cmd = self.session.get_last_command()
            if last_cmd and last_cmd.success:
                console.print(f"\n[dim]Based on your last command, you could:[/dim]")
                
                if last_cmd.service == "calendar" and last_cmd.intent in ["list_events", "get_next_meeting"]:
                    console.print("  ? 'email the attendees'")
                    console.print("  ? 'share a file with them'")
                
                elif last_cmd.service == "gmail" and last_cmd.intent == "search_email":
                    console.print("  ? 'read the first one'")
                    console.print("  ? 'delete that email'")
                
                elif last_cmd.service == "drive" and last_cmd.intent == "search_file":
                    console.print("  ? 'share it with someone@email.com'")
                    console.print("  ? 'download that file'")
        
        console.print()
    
    def show_recent_actions(self) -> None:
        actions = self.safety_manager.get_undo_stack()
        if not actions:
            console.print("[yellow]No recent actions[/yellow]")
            return
        
        console.print(f"\n[bold cyan]Recent Actions:[/bold cyan] ({len(actions)} recorded)\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Action", width=15)
        table.add_column("Service", width=8)
        table.add_column("Resource ID", width=25)
        table.add_column("Can Undo", width=8)
        
        for i, action in enumerate(actions, 1):
            time_str = action.timestamp.strftime("%H:%M:%S")
            can_undo = "?" if action.undo_data else "?"
            resource_short = action.resource_id[:22] + "..." if len(action.resource_id) > 22 else action.resource_id
            
            table.add_row(
                str(i),
                time_str,
                action.action_type.value,
                action.service.upper(),
                resource_short,
                can_undo
            )
        
        console.print(table)
        console.print(f"\n[dim]Use 'undo' to undo the last action (if possible)[/dim]\n")
    
    def undo_last_action(self) -> None:
        last_action = self.safety_manager.get_last_action()
        if not last_action:
            console.print("[yellow]No actions to undo[/yellow]")
            return
        
        if not last_action.undo_data:
            console.print(f"[red]?[/red] Cannot undo {last_action.action_type.value}")
            console.print(f"[dim]This action type cannot be reversed[/dim]")
            return
        
        console.print(f"\n[yellow]Undo:[/yellow] {last_action.action_type.value}")
        console.print(f"[dim]Resource: {last_action.resource_id}[/dim]")
        
        if not click.confirm("Proceed with undo?", default=True):
            console.print("[yellow]Cancelled[/yellow]")
            return
        
        try:
            if last_action.action_type == ActionType.DELETE_EMAIL:
                console.print("[yellow]??  Email undo not fully implemented yet[/yellow]")
                
            elif last_action.action_type == ActionType.DELETE_EVENT:
                console.print("[yellow]??  Event undo not fully implemented yet[/yellow]")
                
            elif last_action.action_type == ActionType.SHARE_FILE:
                console.print("[yellow]??  File share undo not fully implemented yet[/yellow]")
                
            else:
                console.print(f"[yellow]??  Undo for {last_action.action_type.value} not implemented[/yellow]")
            
            self.safety_manager.pop_last_action()
            
        except Exception as e:
            console.print(f"[red]?[/red] Undo failed: {e}")
            logger.error(f"Undo error: {e}")

@click.command()
@click.option('--auth', is_flag=True, help='Authenticate with Google')
@click.option('--command', '-c', help='Execute a single command')
@click.option('--interactive', '-i', is_flag=True, help='Start interactive mode')
@click.option('--dry-run', is_flag=True, help='Simulate actions without executing (Phase 5.4)')
def main(auth: bool, command: Optional[str], interactive: bool, dry_run: bool):
    console.print(Panel.fit(
        "[bold cyan]Intelligent Natural Language Orchestrator[/bold cyan]\n"
        "Control Gmail, Calendar, and Drive with natural language\n"
        "[dim]Phase 2, 3 & 4 Complete: Multi-Service Workflows![/dim]",
        border_style="cyan"
    ))
    orchestrator = Orchestrator(auto_confirm=bool(command), dry_run=dry_run)
    
    if dry_run:
        console.print("[yellow]??  DRY-RUN MODE: No changes will be made[/yellow]\n")
    
    if auth or command or interactive:
        if not orchestrator.authenticate():
            sys.exit(1)
    else:
        console.print("\nUse --help to see available options")
        return
    
    if command:
        orchestrator.process_command(command)
        return
    
    if interactive:
        console.print("\n[cyan]Interactive mode[/cyan] - Type commands (or 'quit' to exit)\n")
        console.print("[dim]Try:[/dim]")
        console.print("  ? 'search for emails from google'")
        console.print("  ? 'what's my next meeting?'  [Phase 5.2]")
        console.print("  ? 'do I have any unread emails?'  [Phase 5.2]")
        console.print("\n[dim]Special commands:[/dim]")
        console.print("  ? 'history' - Show command history")
        console.print("  ? 'suggestions' - Get smart suggestions  [Phase 5.2]")
        console.print("  ? 'actions' - Show recent actions  [Phase 5.4 NEW!]")
        console.print("  ? 'undo' - Undo last action  [Phase 5.4 NEW!]")
        console.print("  ? 'clear' - Clear history\n")
        
        while True:
            try:
                user_input = Prompt.ask("[bold green]You[/bold green]")
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                
                if not user_input.strip():
                    continue
                
                if user_input.lower() == 'history':
                    orchestrator.show_history()
                    continue
                
                if user_input.lower() == 'clear':
                    if orchestrator.session:
                        orchestrator.session.clear_history()
                        console.print("[green]?[/green] History cleared")
                    continue
                
                if user_input.lower() in ['suggestions', 'suggest', 'tips']:
                    orchestrator.show_suggestions()
                    continue
                
                if user_input.lower() == 'undo':
                    orchestrator.undo_last_action()
                    continue
                
                if user_input.lower() in ['actions', 'recent']:
                    orchestrator.show_recent_actions()
                    continue
                
                orchestrator.process_command(user_input)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")

if __name__ == '__main__':
    main()
