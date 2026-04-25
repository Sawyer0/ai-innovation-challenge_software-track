# Project DJA — Backend

FastAPI backend for compliance-aware AI academic advising. Implements deterministic compliance guardrails, Claude-powered course recommendations with Gemini fallback, and transcript parsing via vision AI.

---

## Quick Start

```bash
# 1. Enter backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Required — edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GEMINI_API_KEY=...

# 5. Import catalog (also seeds compliance policy rules)
python -m app.scripts.import_catalog

# 6. Start development server
uvicorn app.main:app --reload

# 7. Open interactive API docs
open http://localhost:8000/docs
```

---

## Environment Variables

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...        # Claude (primary AI)
GEMINI_API_KEY=...                  # Gemini 2.5 Flash (fallback AI)

# Optional (defaults shown)
CLAUDE_MODEL=claude-sonnet-4-6
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./bmcc_catalog.db
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## API Reference

### Sessions

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/session` | Create a new student session |
| `GET` | `/api/session/{session_id}` | Get session with profile and courses |
| `POST` | `/api/session/{session_id}/profile` | Set student profile |
| `POST` | `/api/session/{session_id}/courses` | Add a course manually |
| `DELETE` | `/api/session/{session_id}/courses/{code}` | Remove a course |

**Set profile request body:**
```json
{
  "school": "BMCC",
  "program_code": "CSC-AS",
  "enrollment_status": "full-time",
  "student_type": "international",
  "financial_aid_type": "tap",
  "graduation_year": 2027,
  "graduation_semester": "Spring",
  "career_goal": "I want to work as a robotics engineer"
}
```

`student_type` values: `"domestic"` | `"international"`
`financial_aid_type` values: `"pell"` | `"tap"` | `"both"` | `null`

---

### Transcript Parsing

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/session/{session_id}/transcript` | Upload and parse transcript |

Accepts: `image/jpeg`, `image/png`, `image/webp`, `image/gif`, `application/pdf`

Parses via **Claude Vision** first, falls back to **Gemini Vision** automatically. Returns a list of extracted courses and adds them to the session.

---

### Advisement

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/advisement/` | Get AI-generated course plan |
| `GET` | `/api/advisement/eligible` | List prerequisite-cleared courses |

**Advisement request:**
```json
{ "message": "What should I take next semester?" }
```

Pass `session_id` as a query parameter or header (see `/docs` for auth scheme).

**Advisement response:**
```json
{
  "next_semester": "Fall 2026",
  "total_planned_credits": 15.0,
  "compliance_cleared": true,
  "advisor_message": "Since you've completed MAT 206 and CSC 103...",
  "recommended_courses": [
    {
      "course_code": "CSC 215",
      "course_title": "Data Structures",
      "credits": 3.0,
      "requirement_satisfied": "Required: Year 2 Fall",
      "compliance_status": "compliant",
      "compliance_note": null,
      "career_rationale": "Algorithm design is foundational to robotics path planning.",
      "why_now": "You've completed CSC 103, making this the natural next step."
    }
  ],
  "pell_proration": {
    "planned_credits": 15.0,
    "percentage": 1.0,
    "percentage_display": "100%",
    "enrollment_tier": "full-time",
    "note": "At 15.0 credits (full-time) you receive your full Pell award."
  },
  "disclaimer": "Always confirm your final schedule with your advisor and DegreeWorks before registering."
}
```

`compliance_status` per course: `"compliant"` | `"warning"` | `"blocked"`

**Compliance violation response (422):**
```json
{
  "detail": {
    "type": "visa_compliance_violation",
    "student_type": "international",
    "planned_credits": 9.0,
    "message": "F-1 visa requires full-time enrollment of at least 12 credits..."
  }
}
```

`type` values: `"compliance_violation"` | `"visa_compliance_violation"`

---

### Courses & Programs

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/courses` | Browse all 3,467 courses (paginated) |
| `GET` | `/api/courses/{course_code}` | Get course detail with prerequisites |
| `GET` | `/api/programs` | List all 111 programs |
| `GET` | `/api/programs/{program_code}` | Get program with degree map |

---

## Compliance Guardrail Logic

All guardrails run **before** the AI — the LLM cannot override them.

### Pre-AI Hard Blocks (return 422)

| Rule | Condition | Applies To |
|---|---|---|
| F-1 credit minimum | `planned_credits < 12` | `student_type = "international"` |
| F-1 online limit | `online_courses > 1` | `student_type = "international"` |
| TAP credit minimum | `planned_credits < 12` | `financial_aid_type = "tap"` or `"both"` |
| Pell credit minimum | `planned_credits < 6` | `financial_aid_type = "pell"` or `"both"` |

### Post-AI Annotations (warnings on individual courses)

| Rule | Condition | Applies To |
|---|---|---|
| TAP elective check | Course not in program's allowable elective list | `financial_aid_type = "tap"` or `"both"` |
| Pell proration | Calculates award % at current credit load | `financial_aid_type = "pell"` or `"both"` |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py               # FastAPI app + startup seed
│   ├── config.py             # Settings (Anthropic, Gemini, DB)
│   ├── models.py             # SQLAlchemy ORM (12 tables)
│   ├── schemas.py            # Pydantic request/response models
│   ├── database.py           # DB connection + session factory
│   ├── dependencies.py       # FastAPI dependency injection
│   ├── exceptions.py         # Custom exception classes
│   ├── routers/
│   │   ├── advisement.py     # POST /api/advisement (main feature)
│   │   ├── sessions.py       # Student session CRUD
│   │   ├── transcript.py     # File upload + parsing
│   │   ├── courses.py        # Course catalog browsing
│   │   └── programs.py       # Program listing
│   ├── services/
│   │   ├── ai_service.py     # Claude-first, Gemini-fallback advisement
│   │   ├── catalog_loader.py # Import catalog JSON + seed policy data
│   │   ├── prerequisite_service.py
│   │   ├── session_service.py
│   │   ├── course_service.py
│   │   └── program_service.py
│   ├── parsers/
│   │   └── transcript_parser.py  # Claude Vision → Gemini fallback
│   ├── prompts/
│   │   ├── advisement.py     # System + user prompt templates
│   │   ├── eligibility.py
│   │   └── transcript.py
│   ├── utils/
│   │   └── academic_utils.py # All compliance guardrail functions
│   ├── repositories/
│   │   ├── course_repository.py
│   │   ├── program_repository.py
│   │   └── session_repository.py
│   └── scripts/
│       └── import_catalog.py # CLI: python -m app.scripts.import_catalog
└── tests/
    ├── conftest.py           # Fixtures + test DB seeding
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `courses` | 3,467 BMCC courses with credits, subject, `instruction_mode` |
| `course_prerequisites` | Prerequisite graph (logic_group handles OR/AND) |
| `programs` | 111 degree programs |
| `program_requirements` | Degree maps — `is_required=False` rows are TAP-allowable electives |
| `student_sessions` | UUID-based sessions (no login required) |
| `student_profiles` | Academic + compliance profile per session |
| `student_courses` | Completed / in-progress / planned courses per session |
| `enrollment_status_rules` | Full-time (12–18), half-time (6–11), less-than-half-time (0–5) |
| `financial_aid_constraints` | Pell (min 6), TAP (min 12), both (min 12) — seeded on startup |
| `academic_policies` | Extensible policy store |
| `policy_exceptions` | Per-student overrides with advisor approval |

---

## Running Tests

```bash
cd backend
pytest                          # all tests
pytest tests/unit/              # unit only
pytest tests/integration/       # integration only
pytest --cov=app tests/         # with coverage report
```

Tests use an in-memory SQLite database and mock both Claude and Gemini clients — no API keys required.

---

## Importing a Fresh Catalog

```bash
# Standard import (safe — checks for existing rows)
python -m app.scripts.import_catalog

# Force fresh import (drops and recreates all tables)
python -m app.scripts.import_catalog --fresh
```

The import script also seeds `EnrollmentStatusRule` and `FinancialAidConstraint` rows. These are also seeded on every server startup so a fresh `uvicorn` run without a catalog import still has compliance rules available.

---

## Deployment

### Render

1. Push to GitHub
2. Connect repo in Render → New Web Service
3. Set environment variables: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `DATABASE_URL`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Docker

```bash
docker build -t dja-backend .
docker run -p 8000:8000 --env-file .env dja-backend
```
