# Architecture & Design

## Overview

This is a natural language orchestrator that lets you control Gmail, Google Calendar, and Google Drive using plain English commands. Built with Python 3.10, it uses GPT-4 for intent parsing and coordinates across multiple Google services.

## How It Started

Started with a simple question: what if you could manage your email, calendar, and files just by talking? Built it piece by piece:

1. Set up Google OAuth authentication
2. Integrated OpenAI's GPT-4 for understanding commands
3. Added Gmail operations (send, search, read)
4. Added Calendar operations (create, list, search)
5. Added Drive operations (search, share, upload)
6. Built multi-service workflows (e.g., "email the meeting attendees")
7. Added context memory so it remembers your conversation
8. Made it smart enough to infer what you mean
9. Added safety features (dry-run, undo)
10. Made it resilient (auto-retry, quota tracking)

Result: 4000+ lines of production code that actually works.

## Core Components

### 1. Authentication (`src/auth/`)

**google_auth.py**
- Handles OAuth 2.0 flow with Google
- Stores credentials in `credentials/token.json`
- Auto-refreshes expired tokens
- Uses the official google-auth libraries

How it works:
- First time: Opens browser, you log in, saves token
- After that: Uses saved token, refreshes automatically
- No need to log in again unless you revoke access

### 2. Configuration (`src/config/`)

**settings.py**
- Loads environment variables from `.env`
- Validates config with Pydantic
- Defines OAuth scopes for Gmail, Calendar, Drive
- Sets up paths and API keys

Uses:
- OpenAI API key for GPT-4
- Google OAuth credentials
- All kept secure in `.env` file

### 3. LLM Integration (`src/llm/`)

**client.py**
- Wrapper around OpenAI's API
- Sends commands to GPT-4
- Gets back structured JSON responses
- Handles API errors gracefully

**prompts.py**
- System prompts for different tasks
- Intent classification prompt (Gmail/Calendar/Drive)
- Parameter extraction prompt
- Multi-service workflow detection prompt

The prompts tell GPT-4 exactly what JSON structure to return, making parsing reliable.

### 4. Orchestrator (`src/orchestrator/`)

**intent_parser.py**
- Takes your command as input
- Sends it to GPT-4 via LLM client
- Parses the JSON response
- Returns structured Intent objects (service, action, parameters)

Example:
```
"search for emails from john"
? Intent(service="gmail", intent="search_email", parameters={"query": "from:john"})
```

**workflow_engine.py**
- Detects multi-service commands
- Plans execution order
- Handles dependencies between steps
- Passes data between services

Example:
```
"email the meeting attendees"
? Step 1: Get next meeting (Calendar)
? Step 2: Extract attendee emails
? Step 3: Send email (Gmail) using those emails
```

### 5. Services (`src/services/`)

These wrap the Google APIs with clean interfaces.

**gmail_service.py**
- send_email: Sends an email
- search_emails: Searches your inbox
- get_email: Gets a specific email
- delete_email: Moves email to trash
- get_profile: Gets your Gmail profile info

Uses Gmail API v1. Every method has retry logic.

**calendar_service.py**
- create_event: Creates a calendar event
- list_events: Lists upcoming events
- search_events: Searches events by query
- update_event: Updates an existing event
- delete_event: Deletes an event
- get_event: Gets a specific event

Uses Calendar API v3. Handles date parsing automatically.

**drive_service.py**
- search_files: Searches for files
- upload_file: Uploads a file
- download_file: Downloads a file
- share_file: Shares a file with someone
- create_folder: Creates a new folder
- delete_file: Moves file to trash
- move_file: Moves file between folders
- list_recent_files: Lists recently modified files

Uses Drive API v3. Handles file metadata and permissions.

### 6. Utils (`src/utils/`)

**logger.py**
- Sets up logging with the `rich` library
- Pretty-prints to console
- Structured logging for debugging

**session.py** (Context Memory)
- Stores command history (last 10 commands)
- Tracks references like "last email", "next meeting"
- Resolves pronouns: "it", "them", "that"
- Provides context to LLM for better understanding

Example:
```
You: "search for emails from boss"
    [System stores: last_email = {...}]
You: "read it"
    [System resolves: "it" = last_email]
```

**context_inference.py** (Smart Inference)
- Infers parameters from command text
- "unread emails" ? adds "is:unread" filter
- "next meeting" ? fetches from calendar automatically
- "last 5 days" ? converts to "newer_than:5d"
- Extracts attendees from calendar events

Makes commands feel natural without explicit syntax.

**safety.py** (Safety Features)
- Dry-run mode: Simulates actions without executing
- Action recording: Tracks last 10 actions
- Undo capability: Reverses actions where possible
- Risk assessment: Flags high-risk operations
- Enhanced previews: Shows exactly what will happen

**resilience.py** (Error Recovery)
- Retry logic with exponential backoff
- Detects transient errors (network, rate limits)
- Quota tracking for all services
- Friendly error messages
- Actionable suggestions

### 7. Main Orchestrator (`src/main.py`)

The glue that holds everything together. 850+ lines.

**Key classes:**
- `Orchestrator`: Main controller

**What it does:**
1. Initializes all services
2. Handles authentication
3. Parses commands via IntentParser
4. Routes to appropriate service handler
5. Manages context and session
6. Provides CLI interface (click)

**Modes:**
- Single command: `python -m src.main -c "your command"`
- Interactive: `python -m src.main -i`
- Dry-run: `python -m src.main --dry-run -c "..."`
- Auth only: `python -m src.main --auth`

## How Components Connect

```
User Command
    ?
main.py (Orchestrator)
    ?
intent_parser.py ? llm/client.py ? OpenAI GPT-4
    ?                                      ?
Intent Object ???????????????????????????????
    ?
Orchestrator routes to service:
    ?
??? gmail_service.py ? Gmail API
??? calendar_service.py ? Calendar API
??? drive_service.py ? Drive API
    ?
Results stored in session
    ?
Response to user
```

## Data Flow Examples

### Example 1: Simple Gmail Search

```
Input: "search for emails from google"

1. main.py receives command
2. Checks if smart query (no, it's not)
3. Sends to intent_parser.py
4. intent_parser sends to GPT-4:
   {
     "command": "search for emails from google",
     "context": <session history>
   }
5. GPT-4 returns:
   {
     "service": "gmail",
     "intent": "search_email",
     "parameters": {"query": "from:google"}
   }
6. context_inference enhances: no changes needed
7. Orchestrator calls gmail_service.search_emails("from:google")
8. Gmail API returns results
9. Results displayed + stored in session
10. User sees 20 emails from Google
```

### Example 2: Smart Query

```
Input: "what's my next meeting?"

1. main.py receives command
2. Detects smart query pattern
3. Directly calls calendar_service.list_events(days_ahead=30)
4. Finds next event
5. Extracts: title, time, attendees
6. Formats and displays
7. Stores in session.references['next_meeting']
8. User sees: "Q4 Planning at 2pm tomorrow with 4 attendees"

No LLM call needed! Faster and cheaper.
```

### Example 3: Multi-Service Workflow

```
Input: "email the meeting attendees"

1. main.py receives command
2. Sends to intent_parser
3. GPT-4 detects multi-service workflow:
   {
     "multi_service": true,
     "operations": [
       {
         "service": "calendar",
         "intent": "list_events",
         "step": 1
       },
       {
         "service": "gmail",
         "intent": "send_email",
         "depends_on": 1,
         "step": 2
       }
     ]
   }
4. workflow_engine.py executes:
   Step 1: calendar_service.list_events() ? gets next event
   Step 2: Extracts attendee emails from event
   Step 3: gmail_service.send_email(to=attendees, ...)
5. Both operations complete
6. User sees: "? Sent email to 4 attendees"
```

### Example 4: Context-Aware Command

```
First command: "find files with Q4 report"
? Returns 5 files, stores first one as 'last_file'

Second command: "share it with john@company.com"

1. main.py receives command
2. context_inference.py detects pronoun "it"
3. Resolves: "it" ? session.references['last_file']
4. Gets file_id from last_file
5. intent_parser extracts: email = "john@company.com"
6. drive_service.share_file(file_id, "john@company.com")
7. User sees: "? Shared Q4_Report.pdf with john@company.com"

The system remembered the file from the previous command!
```

### Example 5: Date Filtering

```
Input: "search for emails from last 5 days"

1. main.py ? intent_parser
2. GPT-4 returns: {"query": ""}
3. context_inference.py detects "last 5 days"
4. Converts to Gmail syntax: "newer_than:5d"
5. Updates query: "newer_than:5d"
6. gmail_service.search_emails("newer_than:5d")
7. Returns emails from last 5 days only
```

### Example 6: Dry-Run Mode

```
Input: python -m src.main --dry-run -c "delete all emails"

1. safety_manager detects dry_run=True
2. Command processed normally up to execution
3. At execution point:
   - safety_manager.is_dry_run() returns True
   - Instead of deleting, creates preview
   - Shows: "Would delete 150 emails"
   - Risk level: HIGH
4. No actual deletion happens
5. User sees what would happen safely
```

## Key Design Decisions

### Why GPT-4 for Intent Parsing?

Traditional NLP would require:
- Training data
- Regular expressions
- Keyword matching
- Constant maintenance

GPT-4 gives us:
- Natural language understanding out of the box
- Easy to add new commands (just update prompts)
- Handles variations ("search emails" vs "find messages")
- Returns structured JSON

Trade-off: API cost and latency (1-2 seconds). Worth it for the flexibility.

### Why Not Use LangChain?

Started evaluating LangChain but decided against it:
- Too much abstraction for what we need
- Adds complexity and dependencies
- Direct OpenAI API calls are simpler
- Full control over prompts and parsing

Built our own thin wrapper instead. 50 lines vs 500.

### Why Session-Based Context?

Could have used a database, but session-based is:
- Simpler (no DB setup)
- Fast (in-memory)
- Sufficient for single-user CLI
- Resets on restart (actually a feature)

Stored in SessionContext dataclass. Last 10 commands max.

### Why Dry-Run Mode?

Learned from experience: people are scared of automation. Dry-run mode:
- Lets you test safely
- Builds confidence
- Shows exactly what will happen
- Prevents costly mistakes

Now users test first, then execute. Much better UX.

### Why Auto-Retry?

Google APIs can be flaky:
- Network blips
- Rate limits
- Temporary server errors

Auto-retry with exponential backoff:
- Handles transient failures automatically
- User doesn't even notice
- System feels more reliable
- Up to 3 attempts, then fail

Decorator pattern makes it clean: just add `@retry_with_backoff()`.

## Module Dependencies

```
main.py
  ??? auth.google_auth
  ??? config.settings
  ??? llm.client
  ??? orchestrator.intent_parser
  ??? orchestrator.workflow_engine
  ??? services.gmail_service
  ??? services.calendar_service
  ??? services.drive_service
  ??? utils.logger
  ??? utils.session
  ??? utils.context_inference
  ??? utils.safety
  ??? utils.resilience

orchestrator.intent_parser
  ??? llm.client
  ??? llm.prompts

orchestrator.workflow_engine
  ??? utils.logger

services.gmail_service
  ??? utils.logger
  ??? utils.resilience

services.calendar_service
  ??? utils.logger

services.drive_service
  ??? utils.logger

utils.context_inference
  ??? utils.session
  ??? utils.logger

utils.safety
  ??? utils.logger

utils.resilience
  ??? utils.logger
```

Clean dependency tree. No circular dependencies.

## Testing Strategy

Unit tests for each major feature:
- `test_phase_5_1_context_memory.py`: Session storage, references
- `test_phase_5_2_smart_inference.py`: Parameter inference
- `test_phase_5_4_safety.py`: Dry-run, undo, previews
- `test_phase_6_1_error_recovery.py`: Retry logic, quota

Integration testing via:
- `example_demo.py`: Shows intent parsing
- `validate_system.py`: Checks all components
- `test_all_phases.sh`: Runs everything

Real-world testing: Actually using it daily.

## Performance Characteristics

Latency breakdown for typical command:
- Intent parsing (GPT-4): 1-2s
- Google API call: 0.3-0.8s
- Context processing: <10ms
- Display formatting: <50ms

Total: 2-3 seconds average

Smart queries skip GPT-4, so they're faster: 0.5-1s

Caching could improve this but adds complexity. Current speed is acceptable.

## Security Model

Credentials:
- `.env` file for API keys (gitignored)
- `credentials/token.json` for OAuth token (gitignored)
- No secrets in code
- File permissions: 600 (owner read/write only)

OAuth scopes requested:
- Gmail: Read, send, modify
- Calendar: Read, write
- Drive: Read, write, share

Principle of least privilege: Only request what's needed.

API communication:
- HTTPS only (enforced by Google client libraries)
- Token auto-refresh
- No credential logging

User safety:
- Dry-run mode for testing
- Confirmations for destructive operations
- Risk assessment for dangerous actions

## Scalability Considerations

Current design:
- Single user
- CLI-based
- In-memory session
- Synchronous execution

To scale to multiple users:
- Add user database
- Store sessions in Redis
- Add web interface (Flask/FastAPI)
- Async execution (asyncio)
- Rate limiting per user
- Multi-tenancy support

But for a personal assistant? Current design is perfect.

## Future Enhancements (If You Want)

Could add:
- Voice interface (Whisper API)
- Slack/Discord bot
- Web dashboard
- Mobile app
- More services (Notion, Trello, etc.)
- Scheduled tasks (cron-like)
- Webhooks for real-time notifications
- Search across all services
- AI summaries of your day

But honestly? It works great as-is. Ship it and use it.

## Production Deployment

Running locally:
```bash
cd /Users/test/Desktop/ass
source venv/bin/activate
python -m src.main -i
```

For always-on deployment:
- Run in tmux/screen session
- Set up systemd service
- Deploy to EC2/DigitalOcean
- Add monitoring (sentry.io)
- Set up log rotation

Or keep it simple: just run it on your laptop when you need it.

## Lessons Learned

1. **Start simple**: Gmail first, then Calendar, then Drive. Incrementally.
2. **Test early**: Caught bugs in Phase 0 that would have been painful later.
3. **GPT-4 is magic**: Intent parsing "just works" without training.
4. **Context matters**: Session memory made it feel way smarter.
5. **Users need safety**: Dry-run mode was essential for adoption.
6. **Retries are critical**: Network is unreliable, handle it gracefully.
7. **Don't over-engineer**: Built exactly what was needed, nothing more.

## Code Statistics

- Total lines: 4000+ (src only)
- Python files: 20+
- Services: 3 (Gmail, Calendar, Drive)
- Operations: 18+ distinct actions
- Tests: 8 test suites, 25+ unit tests
- Documentation: 2 files (this + README)

## Architecture Diagram

```
???????????????????????????????????????????????????????????????
?                         User                                 ?
?                   (CLI Interface)                            ?
???????????????????????????????????????????????????????????????
                        ?
                        ?
???????????????????????????????????????????????????????????????
?                   Orchestrator (main.py)                     ?
?  ? Command routing                                           ?
?  ? Session management                                        ?
?  ? Safety checks                                             ?
?  ? Context enhancement                                       ?
???????????????????????????????????????????????????????????????
        ?               ?               ?
        ?               ?               ?
???????????????? ??????????????? ???????????????
?IntentParser  ? ?WorkflowEngine? ?SessionMgr   ?
?              ? ?              ? ?             ?
? ? GPT-4      ? ? ? Multi-svc  ? ? ? History   ?
? ? Parsing    ? ? ? Deps       ? ? ? References?
???????????????? ??????????????? ???????????????
       ?                ?
       ?                ?
????????????????????????????????????????
?         LLM Client (OpenAI)          ?
?    ? Intent classification           ?
?    ? Parameter extraction            ?
????????????????????????????????????????
       ?
       ?
????????????????????????????????????????
?            Services Layer             ?
?  ??????????????????????????????????  ?
?  ? GmailService                   ?  ?
?  ? ? send, search, read, delete   ?  ?
?  ??????????????????????????????????  ?
?  ??????????????????????????????????  ?
?  ? CalendarService                ?  ?
?  ? ? create, list, search, update ?  ?
?  ??????????????????????????????????  ?
?  ??????????????????????????????????  ?
?  ? DriveService                   ?  ?
?  ? ? search, share, upload, delete?  ?
?  ??????????????????????????????????  ?
????????????????????????????????????????
            ?
            ?
????????????????????????????????????????
?        Google APIs                    ?
?  ? Gmail API v1                       ?
?  ? Calendar API v3                    ?
?  ? Drive API v3                       ?
????????????????????????????????????????
```

## Summary

Built a working natural language interface to Google services. Uses GPT-4 for understanding, clean service layer for APIs, context memory for smarter conversations, and safety features for confidence.

4000 lines of Python that actually work in production. No fluff, just functionality.

The key insight: You don't need fancy frameworks or complex architectures. Just clean code, good abstractions, and solve real problems.

Ship it.
