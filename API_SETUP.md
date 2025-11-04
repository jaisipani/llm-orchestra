# API Setup & Testing Guide

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start API Server
```bash
# Option 1: Direct Python
python -m src.api.main

# Option 2: Uvicorn
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Option 3: Docker
docker-compose up
```

### 3. Access API
- **API Base**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health Endpoints
- `GET /` - Root endpoint
- `GET /health` - Health check

### Authentication
- `POST /api/v1/auth` - Authenticate with Google OAuth

### Commands
- `POST /api/v1/command` - Process natural language command

### Session
- `GET /api/v1/session` - Get current session
- `GET /api/v1/history` - Get command history

### Gmail
- `POST /api/v1/gmail/search` - Search emails
- `POST /api/v1/gmail/send` - Send email

### Calendar
- `GET /api/v1/calendar/events` - List events
- `POST /api/v1/calendar/events` - Create event

### Drive
- `GET /api/v1/drive/files` - Search files
- `POST /api/v1/drive/files/share` - Share file

## Testing

### Run Test Suite
```bash
# Make sure API server is running first
python test_api.py
```

### Test with curl
```bash
# Health check
curl http://localhost:8000/health

# Process command (requires auth)
curl -X POST http://localhost:8000/api/v1/command \
  -H "Authorization: Bearer test-user-123" \
  -H "Content-Type: application/json" \
  -d '{"command": "what'\''s my next meeting?", "dry_run": true}'
```

### Test with Swagger UI
1. Open http://localhost:8000/docs
2. Click "Authorize" button
3. Enter token: `test-user-123`
4. Test endpoints interactively

## Authentication

Currently uses simple Bearer token. For production:
- Replace with JWT token validation
- Implement proper OAuth callback flow
- Add token refresh mechanism

## OpenAPI Specification

The OpenAPI spec is available at:
- **JSON**: http://localhost:8000/openapi.json
- **YAML**: `openapi.yaml` (in project root)

Use the spec to:
- Generate client SDKs
- Import into Postman/Insomnia
- Document API contracts
- Generate API documentation

## Docker

See `README_DOCKER.md` for Docker setup instructions.

## Notes

- All endpoints require `Authorization: Bearer <token>` header
- Some endpoints require Google OAuth authentication first
- Use `dry_run: true` for testing without executing actions
- Check `/health` endpoint to verify API is running

