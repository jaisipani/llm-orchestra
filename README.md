# Natural Language Orchestrator

Control Gmail, Google Calendar, and Drive with plain English commands.

## What is this?

A Python CLI that lets you manage your Google services by typing what you want in natural language. No clicking through UIs, no remembering syntax. Just type and it figures out what to do.

Examples:
- "search for emails from john"
- "what's my next meeting?"
- "find files with Q4 report"
- "email the meeting attendees"

It understands context, remembers your conversation, and can work across multiple services at once.

## Quick Start

```bash
# Go to project folder
cd /Users/test/Desktop/ass

# Activate environment
source venv/bin/activate

# Authenticate with Google (first time only)
python -m src.main --auth

# Start using it
python -m src.main -i
```

That's it. Now you can type commands.

## Usage

### Interactive Mode (recommended)

```bash
python -m src.main -i
```

Type commands and it responds. It remembers what you did so you can say things like "share it with john" and it knows what "it" means.

Special commands:
- `history` - see what you've done
- `suggestions` - get ideas based on context
- `actions` - see recent actions
- `undo` - undo last action (when possible)
- `clear` - clear history
- `quit` - exit

### Single Command Mode

```bash
python -m src.main -c "search for emails from google"
```

Good for scripts or automation.

### Dry Run Mode

Test without making changes:

```bash
python -m src.main --dry-run -c "delete all emails"
```

Shows what would happen without actually doing it. Use this when you're not sure.

## What You Can Do

### Gmail

```bash
# Search
"search for emails from john"
"find unread emails"
"show me emails from last 5 days"

# Quick checks
"do I have any unread emails?"

# Send (use dry-run first!)
"send email to user@example.com about meeting tomorrow"
```

### Calendar

```bash
# List
"list my events this week"
"show me my schedule for tomorrow"

# Quick check
"what's my next meeting?"

# Create (use dry-run first!)
"schedule meeting tomorrow at 2pm about Q4 planning"
```

### Drive

```bash
# Search
"find files with budget"
"search for PDF files"
"show me recent files"

# Share (use dry-run first!)
"share file <id> with user@example.com"

# Upload
"upload file /path/to/report.pdf"
```

### Multi-Service Workflows

```bash
"email the meeting attendees"
? Gets next meeting, extracts emails, sends message

"share the Q4 report with them"
? Finds file, shares with people from last context
```

Context-aware. It remembers what you were doing.

## Commands That Work

### Date Filters

- "last 5 days" ? emails from last 5 days
- "last week" ? last 7 days
- "last month" ? last 30 days

### Smart Queries

These skip the AI and go straight to the service (faster):

- "what's my next meeting?"
- "do I have unread emails?"

### Filters

Combine them:
- "unread emails from last 5 days"
- "important emails from boss"

## Configuration

Create a `.env` file:

```bash
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

That's all you need. Don't commit this file.

## Authentication

First time:

```bash
python -m src.main --auth
```

Opens browser, you log in to Google, it saves a token. Token refreshes automatically after that.

Token stored in `credentials/token.json`. Also don't commit this.

## System Requirements

- Python 3.10+
- Google account
- OpenAI API key
- Internet connection

## How It Works

1. You type a command
2. GPT-4 figures out what you want (intent parsing)
3. System enhances it with context if needed
4. Calls the appropriate Google API
5. Stores result in session for future reference
6. Shows you the response

For multi-service commands, it plans the steps and executes them in order.

See ARCHITECTURE.md for technical details.

## Safety Features

- **Dry-run mode**: Test without executing (`--dry-run`)
- **Previews**: See what will happen before confirming
- **Undo**: Reverse actions when possible
- **Risk assessment**: Warns you about dangerous operations
- **Auto-retry**: Handles temporary failures automatically

## Performance

Typical command takes 2-3 seconds:
- 1-2s for GPT-4 to understand it
- 0.3-0.8s for Google API
- Rest is processing

Smart queries (like "what's my next meeting?") skip GPT-4 and are faster (0.5-1s).

## Quotas & Limits

Google APIs have daily quotas:
- Gmail: 1 billion requests/day
- Calendar: 1 million requests/day
- Drive: 1 billion requests/day

You'll never hit these. System tracks usage and warns at 95%.

Auto-retry handles rate limits with exponential backoff.

## Troubleshooting

**"Module not found"**
```bash
source venv/bin/activate
```

**"Authentication failed"**
```bash
rm credentials/token.json
python -m src.main --auth
```

**"Command doesn't work"**

Test with dry-run first:
```bash
python -m src.main --dry-run -c "your command"
```

**Need more results?**

System returns up to 20 results by default. That's usually enough. If you need more, modify `max_results` in the code.

## Project Structure

```
src/
??? auth/           # Google OAuth
??? config/         # Settings
??? llm/            # OpenAI integration
??? orchestrator/   # Intent parsing & workflows
??? services/       # Gmail, Calendar, Drive
??? utils/          # Helpers (logging, session, safety, etc.)
??? main.py         # Main entry point

tests/              # Test suites
credentials/        # OAuth token (don't commit)
.env               # API keys (don't commit)
requirements.txt   # Dependencies
```

## Dependencies

Key libraries:
- `openai` - GPT-4 integration
- `google-api-python-client` - Google APIs
- `google-auth-oauthlib` - OAuth
- `pydantic` - Data validation
- `rich` - Terminal UI
- `click` - CLI framework

Install with:
```bash
pip install -r requirements.txt
```

## Development

To add a new command:

1. Add the intent to prompts in `src/llm/prompts.py`
2. Add handler method in `src/main.py`
3. Implement the service method if needed
4. Test it with dry-run

The system is designed to be extended easily.

## Testing

Run all tests:
```bash
./test_all_phases.sh
```

Or run specific test files:
```bash
python tests/test_phase_5_1_context_memory.py
python tests/test_phase_5_2_smart_inference.py
```

Validate system:
```bash
python validate_system.py
```

## Examples

Real workflow:

```bash
$ python -m src.main -i

> what's my next meeting?
Q4 Planning at 2pm tomorrow with 4 attendees:
- john@company.com
- jane@company.com
- bob@company.com
- alice@company.com

> email the attendees
Subject: Re: Q4 Planning
Send to 4 people? (y/n): y
? Email sent to 4 attendees

> find Q4 report file
Found 3 files:
1. Q4_Report_Final.pdf
2. Q4_Budget.xlsx
3. Q4_Summary.docx

> share the first one with them
? Shared Q4_Report_Final.pdf with 4 people

> history
Command History:
1. what's my next meeting?
2. email the attendees
3. find Q4 report file
4. share the first one with them

> quit
```

See how it remembers context? "the attendees", "them", "the first one" - it knows what you mean.

## Production Use

This runs locally on your machine. To use it:

1. Keep terminal open or run in background (tmux/screen)
2. Or just start it when you need it
3. Could deploy to a server if you want it always available

For now, local is fine. It's fast enough.

## Security

- API keys in `.env` (never commit)
- OAuth token in `credentials/` (never commit)
- Both files are gitignored by default
- Set file permissions to 600 (owner read/write only)
- All API communication over HTTPS

Don't share your `.env` or `credentials/token.json` files. That's it.

## Contributing

Want to add features? Go ahead:

1. Fork it
2. Make changes
3. Test thoroughly
4. Submit PR

Keep it clean and simple.

## License

Do what you want with it. No restrictions.

## Credits

Built with Python, OpenAI's GPT-4, and Google APIs.

No fancy frameworks. Just code that works.

---

Questions? Issues? Check ARCHITECTURE.md for technical details.

Otherwise, just use it. That's what it's for.
