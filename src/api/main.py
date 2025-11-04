from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from src.main import Orchestrator
from src.utils.logger import logger

app = FastAPI(
    title="LLM Orchestra API",
    description="Natural Language Orchestrator for Gmail, Calendar, and Drive",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandRequest(BaseModel):
    command: str = Field(..., description="Natural language command")
    dry_run: Optional[bool] = Field(False, description="Simulate without executing")
    auto_confirm: Optional[bool] = Field(False, description="Skip confirmation prompts")

class CommandResponse(BaseModel):
    task_id: Optional[str] = Field(None, description="Task ID for async operations")
    status: str = Field(..., description="Status: queued, processing, completed, failed")
    service: Optional[str] = Field(None, description="Service used")
    intent: Optional[str] = Field(None, description="Detected intent")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Extracted parameters")
    result: Optional[Any] = Field(None, description="Command result")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.now)

class SessionInfo(BaseModel):
    session_id: str
    started_at: datetime
    command_count: int
    last_command: Optional[str] = None

class HistoryItem(BaseModel):
    command: str
    timestamp: datetime
    service: str
    intent: str
    success: bool
    error: Optional[str] = None

orchestrators: Dict[str, Orchestrator] = {}
sessions: Dict[str, Dict[str, Any]] = {}

def get_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    user_id = authorization.replace("Bearer ", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authorization token")
    
    return user_id

def get_orchestrator(user_id: str) -> Orchestrator:
    if user_id not in orchestrators:
        orchestrators[user_id] = Orchestrator(auto_confirm=True)
        sessions[user_id] = {"authenticated": False}
    
    return orchestrators[user_id]

@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "LLM Orchestra API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/api/v1/auth", tags=["Authentication"])
async def authenticate(user_id: str = Depends(get_user_id)):
    orchestrator = get_orchestrator(user_id)
    
    try:
        success = orchestrator.authenticate()
        
        if success:
            sessions[user_id]["authenticated"] = True
            return {
                "status": "authenticated",
                "message": "Successfully authenticated with Google"
            }
        else:
            raise HTTPException(status_code=401, detail="Authentication failed")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/command", response_model=CommandResponse, tags=["Commands"])
async def process_command(
    request: CommandRequest,
    user_id: str = Depends(get_user_id),
    background_tasks: BackgroundTasks = None
):
    orchestrator = get_orchestrator(user_id)
    
    if not sessions[user_id].get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated. Call /api/v1/auth first")
    
    try:
        orchestrator.safety_manager.dry_run = request.dry_run
        
        result = None
        error = None
        service = None
        intent = None
        parameters = None
        
        try:
            orchestrator.process_command(request.command)
            
            if orchestrator.session:
                last_cmd = orchestrator.session.get_last_command()
                if last_cmd:
                    service = last_cmd.service
                    intent = last_cmd.intent
                    parameters = last_cmd.parameters
                    result = last_cmd.result
                    error = last_cmd.error
        except Exception as e:
            error = str(e)
            logger.error(f"Command processing error: {e}")
        
        return CommandResponse(
            status="completed" if not error else "failed",
            service=service,
            intent=intent,
            parameters=parameters,
            result=result,
            error=error
        )
    
    except Exception as e:
        logger.error(f"API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/session", response_model=SessionInfo, tags=["Session"])
async def get_session(user_id: str = Depends(get_user_id)):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.session:
        raise HTTPException(status_code=404, detail="No active session")
    
    try:
        session = orchestrator.session
        last_cmd = session.get_last_command()
        
        return SessionInfo(
            session_id=session.session_id,
            started_at=session.started_at,
            command_count=len(session.history),
            last_command=last_cmd.command if last_cmd else None
        )
    except Exception as e:
        logger.error(f"Session error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/history", response_model=List[HistoryItem], tags=["Session"])
async def get_history(
    limit: Optional[int] = 10,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.session:
        return []
    
    history = orchestrator.session.get_last_n_commands(limit)
    
    return [
        HistoryItem(
            command=cmd.command,
            timestamp=cmd.timestamp,
            service=cmd.service,
            intent=cmd.intent,
            success=cmd.success,
            error=cmd.error
        )
        for cmd in history
    ]

class GmailSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 10

@app.post("/api/v1/gmail/search", tags=["Gmail"])
async def gmail_search(
    request: GmailSearchRequest,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.gmail_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        results = orchestrator.gmail_service.search_emails(request.query, max_results=request.max_results)
        return {"count": len(results), "emails": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GmailSendRequest(BaseModel):
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None

@app.post("/api/v1/gmail/send", tags=["Gmail"])
async def gmail_send(
    request: GmailSendRequest,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.gmail_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        result = orchestrator.gmail_service.send_email(
            to=request.to,
            subject=request.subject,
            body=request.body,
            cc=request.cc
        )
        return {"status": "sent", "message_id": result.get("id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/calendar/events", tags=["Calendar"])
async def calendar_list_events(
    days_ahead: Optional[int] = 7,
    max_results: Optional[int] = 10,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.calendar_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        events = orchestrator.calendar_service.list_events(
            days_ahead=days_ahead,
            max_results=max_results
        )
        return {"count": len(events), "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CalendarEventRequest(BaseModel):
    summary: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None

@app.post("/api/v1/calendar/events", tags=["Calendar"])
async def calendar_create_event(
    request: CalendarEventRequest,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.calendar_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        result = orchestrator.calendar_service.create_event(
            summary=request.summary,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
            location=request.location,
            attendees=request.attendees
        )
        return {"status": "created", "event_id": result.get("id"), "event": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/drive/files", tags=["Drive"])
async def drive_search_files(
    query: Optional[str] = None,
    mime_type: Optional[str] = None,
    max_results: Optional[int] = 10,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.drive_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        files = orchestrator.drive_service.search_files(
            query=query,
            mime_type=mime_type,
            max_results=max_results
        )
        return {"count": len(files), "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DriveShareRequest(BaseModel):
    file_id: str
    email: str
    role: Optional[str] = "reader"

@app.post("/api/v1/drive/files/share", tags=["Drive"])
async def drive_share_file(
    request: DriveShareRequest,
    user_id: str = Depends(get_user_id)
):
    orchestrator = get_orchestrator(user_id)
    
    if not orchestrator.drive_service:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        success = orchestrator.drive_service.share_file(
            file_id=request.file_id,
            email=request.email,
            role=request.role
        )
        return {"status": "shared" if success else "failed", "file_id": request.file_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
