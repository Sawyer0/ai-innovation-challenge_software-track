# BMCC Academic Advisement Backend

AI-powered backend for BMCC course recommendations, prerequisite checking, and academic advisement. Built with FastAPI, SQLite, and OpenAI.

## Features

- **Session-based student tracking** — No login required, just a session ID
- **Transcript parsing** — Upload images, PDFs, or CSVs to auto-extract courses
- **Prerequisite engine** — Check eligibility, view prerequisite chains
- **AI advisement** — Personalized course recommendations with context
- **Financial aid compliance** — Warnings for enrollment status violations

## Quick Start

```bash
# 1. Navigate to backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 5. Initialize database and import catalog
python -m app.scripts.import_catalog

# 6. Run server
uvicorn app.main:app --reload

# 7. Open API docs
open http://localhost:8000/docs
```

## API Overview

| Endpoint | Description |
|----------|-------------|
| `POST /api/session` | Create a new student session |
| `POST /api/session/{id}/transcript` | Upload transcript (image/PDF/CSV) |
| `POST /api/session/{id}/profile` | Set student standing (program, aid type, etc.) |
| `POST /api/advisement` | Get AI-generated advisement message |
| `GET /api/advisement/eligible` | List courses student can take now |
| `GET /api/courses` | Browse all courses (paginated) |
| `GET /api/programs` | List all academic programs |

See full API documentation at `/docs` when the server is running.

## Example Usage

### Create a Session

```bash
curl -X POST http://localhost:8000/api/session
# Returns: {"session_id": "abc-123-def", "created_at": "..."}
```

### Set Student Profile

```bash
curl -X POST http://localhost:8000/api/session/abc-123-def/profile \
  -H "Content-Type: application/json" \
  -d '{
    "school": "BMCC",
    "program_code": "CSC-AS",
    "enrollment_status": "full-time",
    "financial_aid_type": "pell",
    "graduation_year": 2026,
    "graduation_semester": "Spring"
  }'
```

### Get AI Advisement

```bash
curl -X POST http://localhost:8000/api/advisement \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123-def", "message": "What should I take next?"}'
```

**Sample Response:**
```json
{
  "message": "Since you've already completed MAT157 in the Summer, you are now able to register MAT206 which is available in the Fall. Does that sound like a plan?",
  "suggested_courses": ["MAT206", "CSC103", "ENG201"],
  "warnings": ["Remember: To keep your Pell Grant, stay at 6+ credits."],
  "total_credits": 12
}
```

## Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...

# Optional (defaults shown)
DATABASE_URL=sqlite:///./bmcc_catalog.db
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
PORT=8000
```

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── models.py            # SQLAlchemy database models
│   ├── schemas.py           # Pydantic request/response models
│   ├── database.py          # DB connection & session management
│   ├── config.py            # Environment settings
│   ├── routers/
│   │   ├── courses.py       # /api/courses endpoints
│   │   ├── programs.py      # /api/programs endpoints
│   │   ├── session.py       # Student session management
│   │   ├── transcript.py    # File upload & parsing
│   │   └── advisement.py    # AI recommendation endpoints
│   ├── services/
│   │   ├── catalog_loader.py    # Import bmcc-catalog.json
│   │   ├── prerequisites.py     # Prerequisite checking
│   │   ├── enrollment_rules.py  # Financial aid & status checks
│   │   └── openai_client.py     # AI integration
│   └── parsers/
│       ├── image_parser.py      # OCR for transcript images
│       ├── pdf_parser.py        # PDF text extraction
│       └── csv_parser.py        # CSV transcript parsing
├── data/
│   └── bmcc-catalog.json        # Course catalog (seed data)
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

## Database Schema

**Core Tables:**
- `courses` — 3,467 courses from catalog
- `programs` — 111 academic programs
- `course_prerequisites` — Normalized prereq relationships
- `student_sessions` — Session tracking (no auth)
- `student_profiles` — Academic standing & aid info
- `student_courses` — Completed/planned courses
- `enrollment_status_rules` — Full-time/half-time definitions
- `financial_aid_constraints` — Aid compliance rules

## Development

### Run Tests

```bash
pytest
```

### Import Fresh Catalog Data

```bash
python -m app.scripts.import_catalog --fresh
```

### Add a New API Endpoint

1. Add route in `app/routers/`
2. Add schema in `app/schemas.py` if needed
3. Register router in `app/main.py`
4. Document in this README

## Deployment

### Render (Recommended)

1. Push to GitHub
2. Connect repo to Render
3. Set environment variables:
   - `OPENAI_API_KEY`
   - `DATABASE_URL` (Render PostgreSQL or keep SQLite)
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Docker (Optional)

```bash
docker build -t bmcc-backend .
docker run -p 8000:8000 --env-file .env bmcc-backend
```

## Tech Stack

| Component | Choice |
|-----------|--------|
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (dev) → PostgreSQL (prod) |
| AI | Google Gemini 2.5 Flash|
| Validation | Pydantic v2 |

## Frontend Integration

The API is CORS-enabled for local development. Use these headers:

```javascript
fetch('http://localhost:8000/api/session', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})
```

Store the returned `session_id` in localStorage for persistence.

## License

MIT
