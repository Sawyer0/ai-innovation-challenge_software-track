# Project DJA: Backend

FastAPI + SQLAlchemy API behind the Project DJA advisor. Setup, demo and project
background are in the [root README](../README.md); this file is the API and code reference.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # set GROQ_API_KEY (free), ANTHROPIC_API_KEY or GEMINI_API_KEY
uvicorn app.main:app --reload      # interactive docs at http://localhost:8000/docs
```

On first start the app creates the SQLite database and loads `data/bmcc-catalog.json`
and `data/rules.json` (about 15 seconds). To re-import later:

```bash
python -m app.scripts.import_catalog      # catalog + rules (keeps sessions)
python -m app.scripts.reload_rules        # rules only
python -m app.scripts.check_uniqueness    # report duplicate codes
```

## Configuration

All settings come from environment variables or `backend/.env` (gitignored). See
[`.env.example`](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | unset | Groq, free tier ([get a key](https://console.groq.com/keys)) |
| `ANTHROPIC_API_KEY` | unset | Claude |
| `GEMINI_API_KEY` | unset | Google Gemini |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq text model |
| `GROQ_VISION_MODEL` | `qwen/qwen3.8-27b` | Groq model for image transcripts (a Groq preview model) |
| `CLAUDE_MODEL` / `GEMINI_MODEL` | `claude-sonnet-4-6` / `gemini-2.5-flash` | |
| `DATABASE_URL` | `sqlite:///./bmcc_catalog.db` | |
| `CORS_ORIGINS` | `["http://localhost:3000","http://localhost:5173"]` | |
| `APP_ENV` | `development` | `production` moves the API docs to `/api/docs` |
| `AI_RATE_LIMIT_PER_MINUTE` / `AI_RATE_LIMIT_PER_HOUR` | `5` / `30` | Per-IP limits on advisement and transcript |
| `AI_DAILY_LIMIT` | `500` | Cap on AI requests across all visitors per 24 hours (bounds provider spend) |
| `TRUST_PROXY_HEADERS` | `false` | Read the client IP from `X-Real-IP` / `X-Forwarded-For` (only behind a proxy that sets them) |

Providers with a key are tried in order Claude → Gemini → Groq; if one fails or returns
malformed JSON the next is used. No provider receives a PDF file: each gets the PDF's
text layer, with personal identifiers redacted, when that looks like a transcript, and
otherwise (scans, photos saved as PDF, odd encodings) the first 4 pages rendered as
images (`GROQ_VISION_MODEL` on Groq, 3 per request), with identifiers found in the text
layer blacked out. See Privacy in the top-level README for what is and isn't redacted. Password-protected PDFs are rejected with a message; CUNYfirst's
empty-password encryption opens normally.

Failures map to messages a visitor can act on: provider rate limits and outages return
`503` with `Retry-After`, timeouts `504`, unreadable files `400`/`422`, and the real
provider error is only logged.

The AI limits (per-IP minute/hour and the global daily cap) are kept in memory, so on
serverless each warm instance counts separately: they are best-effort, not exact. AI
responses carry `X-AI-Limit-*`, `X-AI-Remaining-*` and `X-AI-Reset-*` headers
(`Minute`, `Hour`, `Day`), and `GET /api/usage` reports the same without counting. With no key set, `/health` reports `degraded` and the AI
endpoints return `503` with setup instructions.

## API

All routes are under `/api`. Sessions are anonymous UUIDs. Sessions are stored per
server instance, so the write, transcript and advisement routes accept any well-formed
UUID, creating the session when this instance doesn't have it; a malformed id gets
`404 Session not found`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | DB status and which AI providers have keys |
| `GET` | `/api/usage` | Caller's remaining AI quota (minute/hour per IP, day global); free |
| `POST` | `/api/session/` | Create a session |
| `GET` | `/api/session/{id}` | Session with profile and courses |
| `GET` | `/api/session/{id}/status` | Expiry status |
| `POST` | `/api/session/{id}/profile` | Set or update the student profile |
| `POST` | `/api/session/{id}/courses` | Add one course |
| `POST` | `/api/session/{id}/courses/bulk` | Save reviewed transcript courses (skips duplicates) |
| `DELETE` | `/api/session/{id}/courses/{code}` | Remove a course |
| `POST` | `/api/session/{id}/transcript` | Parse a transcript PDF/image into `{profile, courses}` (does not save) |
| `GET` | `/api/session/{id}/advisement/eligible` | Remaining requirements with prerequisites met |
| `POST` | `/api/session/{id}/advisement` | Guardrails, then an AI course plan. Body `{message, profile?, courses?}`; `profile` and `courses` replace what the session stored, so one request carries everything |
| `GET` | `/api/courses/?search=&skip=&limit=` | Search the catalog |
| `GET` | `/api/courses/{code}` | Course detail |
| `GET` | `/api/programs/` | Programs |
| `GET` | `/api/programs/{code}` | Program detail |

Profile body (all fields optional):

```json
{
  "school": "BMCC",
  "program_code": "CSC-AS",
  "enrollment_status": "full-time",
  "student_type": "international",
  "financial_aid_type": "tap",
  "graduation_year": 2027,
  "graduation_semester": "Spring",
  "career_goal": "robotics engineer"
}
```

Course `status` is one of `completed`, `in-progress`, `planned` or `withdrawn`.
Transcript uploads accept PDF, PNG, JPEG, GIF and WebP.

### Advisement errors

| Status | When |
|---|---|
| `400` | No profile set |
| `422` | A guardrail blocked the plan; `detail.type` is `compliance_violation` or `visa_compliance_violation` |
| `502` | Every configured AI provider failed |
| `503` | No AI provider key configured |

## Compliance rules

Hard blocks run before the AI and only once the student has planned courses
(0 planned credits means "recommend a schedule"):

| Rule | Blocks when | Applies to |
|---|---|---|
| F-1 credit minimum | planned credits < 12 | `student_type = "international"` |
| F-1 online limit | more than 1 online/hybrid course | `student_type = "international"` |
| TAP minimum | planned credits < 12 | `financial_aid_type` `tap` or `both` |
| Pell minimum | planned credits < 6 | `financial_aid_type` `pell` |

After the AI responds, courses outside a TAP student's program requirements get
`compliance_status: "warning"`, and Pell students get a `pell_proration` block for
the recommended credit total.

## Code layout

```
app/
├── main.py              app, lifespan (DB + catalog bootstrap), /health
├── config.py            settings from env / .env
├── database.py          engine, session, Base
├── models.py            SQLAlchemy models
├── schemas.py           Pydantic request/response models
├── routers/             HTTP endpoints
├── services/            use cases: sessions, advisement, prerequisites, catalog import
├── repositories/        database access
├── academics/           pure rules: semesters, grades, compliance guardrails
├── parsers/             transcript (CUNYfirst or DegreeWorks PDF) and prerequisite-text parsing
├── prompts/             every LLM prompt
├── infrastructure/ai/   LLMProvider interface (Claude, Gemini, Groq) and JSON helpers
└── scripts/             catalog import and maintenance commands
scripts/
├── scrape_bmcc.py       catalog scraper (needs `playwright`)
└── smoke_api.py         manual smoke test against a running server
```

## Tests

```bash
ruff check . && ruff format --check . && mypy && pytest
```

`tests/unit` covers rules, prerequisites, providers and the advisement service;
`tests/integration` exercises the API against an in-memory database;
`tests/e2e` walks the full transcript-to-plan journey; `test_data_quality.py`
checks the bundled catalog. LLMs are faked in `tests/conftest.py`, so no keys or
network are needed.
