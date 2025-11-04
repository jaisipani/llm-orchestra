from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field

@dataclass
class CommandResult:
    command: str
    timestamp: datetime
    service: str
    intent: str
    parameters: dict
    result: Any
    success: bool
    error: Optional[str] = None

@dataclass
class SessionContext:
    session_id: str
    started_at: datetime = field(default_factory=datetime.now)
    history: list[CommandResult] = field(default_factory=list)
    references: dict[str, Any] = field(default_factory=dict)
    
    def add_command(
        self,
        command: str,
        service: str,
        intent: str,
        parameters: dict,
        result: Any,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        cmd_result = CommandResult(
            command=command,
            timestamp=datetime.now(),
            service=service,
            intent=intent,
            parameters=parameters,
            result=result,
            success=success,
            error=error
        )
        self.history.append(cmd_result)
        self._update_references(cmd_result)
    
    def _update_references(self, cmd_result: CommandResult) -> None:
        self.references[f"last_{cmd_result.service}_command"] = cmd_result
        self.references["last_command"] = cmd_result
        if cmd_result.success and cmd_result.result:
            if cmd_result.service == "gmail":
                if cmd_result.intent == "search_email":
                    self.references["last_emails"] = cmd_result.result
                    if isinstance(cmd_result.result, list) and len(cmd_result.result) > 0:
                        self.references["last_email"] = cmd_result.result[0]
                elif cmd_result.intent == "send_email":
                    self.references["last_sent_email"] = cmd_result.result
            
            elif cmd_result.service == "calendar":
                if cmd_result.intent == "list_events" or cmd_result.intent == "search_event":
                    self.references["last_events"] = cmd_result.result
                    if isinstance(cmd_result.result, list) and len(cmd_result.result) > 0:
                        self.references["last_event"] = cmd_result.result[0]
                        self.references["next_meeting"] = cmd_result.result[0]
                elif cmd_result.intent == "create_event":
                    self.references["last_created_event"] = cmd_result.result
            
            elif cmd_result.service == "drive":
                if cmd_result.intent == "search_file":
                    self.references["last_files"] = cmd_result.result
                    if isinstance(cmd_result.result, list) and len(cmd_result.result) > 0:
                        self.references["last_file"] = cmd_result.result[0]
    
    def get_last_command(self) -> Optional[CommandResult]:
        return self.history[-1] if self.history else None
    def get_last_n_commands(self, n: int = 5) -> list[CommandResult]:
        return self.history[-n:] if self.history else []
    def get_reference(self, key: str) -> Optional[Any]:
        return self.references.get(key)
    def resolve_reference(self, text: str) -> tuple[Optional[str], Optional[Any]]:
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in ["that email", "the email", "this email"]):
            return ("email", self.references.get("last_email"))
        
        if "last email" in text_lower:
            return ("email", self.references.get("last_email"))
        
        if any(phrase in text_lower for phrase in ["that meeting", "the meeting", "this meeting"]):
            return ("event", self.references.get("last_event"))
        
        if any(phrase in text_lower for phrase in ["next meeting", "upcoming meeting"]):
            return ("event", self.references.get("next_meeting"))
        
        if any(phrase in text_lower for phrase in ["that file", "the file", "this file"]):
            return ("file", self.references.get("last_file"))
        
        if text_lower in ["it", "that", "this"]:
            last_cmd = self.get_last_command()
            if last_cmd:
                if last_cmd.service == "gmail":
                    return ("email", self.references.get("last_email"))
                elif last_cmd.service == "calendar":
                    return ("event", self.references.get("last_event"))
                elif last_cmd.service == "drive":
                    return ("file", self.references.get("last_file"))
        
        if "first one" in text_lower or "first" in text_lower:
            last_cmd = self.get_last_command()
            if last_cmd and last_cmd.result:
                if isinstance(last_cmd.result, list) and len(last_cmd.result) > 0:
                    return (last_cmd.service, last_cmd.result[0])
        
        if "second one" in text_lower or "second" in text_lower:
            last_cmd = self.get_last_command()
            if last_cmd and last_cmd.result:
                if isinstance(last_cmd.result, list) and len(last_cmd.result) > 1:
                    return (last_cmd.service, last_cmd.result[1])
        
        return (None, None)
    
    def get_context_summary(self) -> str:
        if not self.history:
            return "No previous commands in this session."
        recent = self.get_last_n_commands(3)
        summary_parts = ["Recent commands:"]
        
        for i, cmd in enumerate(recent, 1):
            status = "?" if cmd.success else "?"
            summary_parts.append(
                f"{i}. {status} [{cmd.service}] {cmd.intent}: {cmd.command}"
            )
        
        if self.references:
            summary_parts.append("\nAvailable references:")
            if "last_email" in self.references:
                summary_parts.append("- last_email")
            if "next_meeting" in self.references:
                summary_parts.append("- next_meeting")
            if "last_file" in self.references:
                summary_parts.append("- last_file")
        
        return "\n".join(summary_parts)
    
    def clear_history(self) -> None:
        self.history.clear()
        self.references.clear()

class SessionManager:
    def __init__(self):
        self.current_session: Optional[SessionContext] = None
    def start_session(self, session_id: str = "default") -> SessionContext:
        self.current_session = SessionContext(session_id=session_id)
        return self.current_session
    def get_session(self) -> Optional[SessionContext]:
        return self.current_session
    def end_session(self) -> None:
        self.current_session = None
