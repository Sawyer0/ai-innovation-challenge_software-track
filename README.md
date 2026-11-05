# Project DJA: Compliance-Aware AI Advising for CUNY

[![CI](https://github.com/Sawyer0/ai-innovation-challenge_software-track/actions/workflows/ci.yml/badge.svg)](https://github.com/Sawyer0/ai-innovation-challenge_software-track/actions/workflows/ci.yml)

An AI academic advisor for BMCC/CUNY students that checks a course plan against
visa and financial-aid rules **before** it asks an LLM for recommendations.

**Live demo: [project-dja.vercel.app](https://project-dja.vercel.app)**

Project DJA was built in two days by a three-person student team for the
**AI Innovation Challenge (AI Software / Agentic AI track)**, a CUNY hackathon hosted
by the BMCC Technology Learning Community and BMCC Tech Innovation Hub. It is a
hackathon prototype, not a production service, and it is not affiliated with or
endorsed by CUNY.

## Why

For many CUNY students, a bad schedule isn't only an inconvenience:

- An F-1 student who drops below 12 credits, or counts more than one online course,
  puts their visa status at risk.
- A TAP recipient below 12 credits loses that semester's TAP award.
- A Pell recipient's award is prorated by credit load (12+ = 100%, 9 = 75%, 6 = 50%).

DegreeWorks tracks degree progress, but not those personal constraints. DJA's core
design choice: **the rules that protect a student's visa and aid are plain,
tested Python, and the LLM only personalizes within them.** The model can't override
a block.

## How it works

```
React intake form ──► FastAPI
                       │
  transcript upload ──►│ LLM reads a PDF or screenshot → courses + profile hints
                       │ (student reviews them, then they are saved to the session)
                       │
  "What should I take?"│
                       ▼
        ┌──────────────────────────────┐
        │ Eligibility (deterministic)  │  remaining program requirements whose
        │                              │  prerequisites are completed or in progress
        └──────────────┬───────────────┘
        ┌──────────────▼───────────────┐
        │ Guardrails (deterministic)   │  TAP/Pell credit minimums, F-1 ≥12 credits
        │                              │  and ≤1 online/hybrid course → HTTP 422
        └──────────────┬───────────────┘
        ┌──────────────▼───────────────┐
        │ LLM advisement               │  structured JSON plan: course, requirement
        │ Claude → Gemini → Groq       │  satisfied, career rationale, why now
        └──────────────┬───────────────┘
        ┌──────────────▼───────────────┐
        │ Post-AI annotation           │  TAP elective warnings, Pell proration
        └──────────────────────────────┘
```

| Layer | What's there |
|---|---|
| Frontend | React 19 + TypeScript + Vite (`frontend/`): intake form, transcript upload and review, results |
| API | FastAPI + SQLAlchemy 2.0 on SQLite (`backend/app/`) |
| Domain rules | `app/academics/`: semesters, grades, and the compliance guardrails |
| AI | `app/infrastructure/ai/providers.py`: one `LLMProvider` interface; Claude, Gemini and Groq are tried in order for whichever keys are set |
| Data | `backend/data/bmcc-catalog.json`: 3,467 courses and 111 programs scraped from the public BMCC catalog (`backend/scripts/scrape_bmcc.py`); loaded into SQLite on first start |

Backend layout: `routers/` (HTTP) → `services/` (use cases) → `repositories/` (DB
access), with `academics/` for pure rules and `prompts/` for every LLM prompt.
See [`backend/README.md`](backend/README.md) for the API reference.

## Quick start

Requires Python 3.11+ and Node 20.19+ (or 22.12+).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then set at least one AI key (see below)
uvicorn app.main:app --reload # first start loads the catalog (~15 s)
```

```bash
# Frontend (second terminal)
cd frontend
npm ci
npm run dev                   # http://localhost:5173
```

Or run both at once from the repo root with `npm install && npm run dev`.

**AI keys.** Advisement and transcript reading need one LLM key in `backend/.env`
(gitignored; never commit it). The cheapest path is a free
[Groq API key](https://console.groq.com/keys) as `GROQ_API_KEY`; `ANTHROPIC_API_KEY`
and `GEMINI_API_KEY` also work and are tried first when set. Without any key,
everything else (catalog, sessions, eligibility, guardrails) still works and the AI
endpoints answer `503` with setup instructions.

## Demo

Real output from a local run with no AI key configured. An international student on
TAP has 7 planned credits, so the guardrail blocks the plan before any LLM call:

```console
$ curl -s -X POST localhost:8000/api/session/$S/advisement \
    -H 'content-type: application/json' -d '{"message":"What should I take next semester?"}'
{"detail":{"type":"compliance_violation","aid_type":"tap","planned_credits":7.0,
 "message":"TAP (Tuition Assistance Program) requires full-time enrollment of at least
 12 credits. Dropping below 12 credits will result in loss of TAP funding for this
 semester. Please add more courses or speak with a financial aid advisor before registering."}}
HTTP 422

$ curl -s localhost:8000/api/session/$S/advisement/eligible   # CSC-AS, after MAT 206 + ENG 101
{"eligible_courses":["MAT 301","CIS 317","CSC 203","FRN 280E","FRN 280EH","SPN 450H"]}
```

With a key set, the same endpoint returns a plan shaped like this (from the test
suite's fixtures, not a live model):

```json
{
  "next_semester": "Spring 2027",
  "total_planned_credits": 12.0,
  "compliance_cleared": true,
  "advisor_message": "With MAT 157 done, Precalculus keeps you on the engineering track.",
  "recommended_courses": [
    {
      "course_code": "MAT 206",
      "course_title": "Precalculus",
      "credits": 4.0,
      "requirement_satisfied": "Required",
      "compliance_status": "compliant",
      "compliance_note": null,
      "career_rationale": "Builds toward robotics.",
      "why_now": "Prerequisites are complete."
    }
  ],
  "pell_proration": { "percentage_display": "100%", "enrollment_tier": "full-time", "...": "..." },
  "disclaimer": "Always confirm your final schedule with your advisor and DegreeWorks before registering."
}
```

## Testing

```bash
cd backend
ruff check . && ruff format --check .   # lint + format
mypy                                    # type check
pytest                                  # unit, integration, e2e and catalog data-quality tests
```

Tests use an in-memory database and fake LLM providers, so they need no keys and make
no network calls. CI (`.github/workflows/ci.yml`) runs the same checks plus the
frontend's `npm run lint` and `npm run build` on every pull request.

## Deployment

The repo deploys to Vercel as one project (`vercel.json`): the Vite build is served
as static files, and `api/index.py` runs the FastAPI app as a Python function that
receives every `/api/*` request. The frontend calls the API on the same origin.

- **Env vars:** `GROQ_API_KEY` (or another provider key) in the Vercel project
  settings. Nothing secret lives in the repo.
- **Database:** the function's filesystem is read-only except `/tmp`, so each
  instance copies the pre-built catalog database `backend/data/catalog.sqlite` to
  `/tmp` on cold start. Rebuild it with `python backend/scripts/build_catalog_db.py`
  after changing the catalog, `rules.json` or the models (a test checks it is in sync).
- **Sessions are ephemeral** in the deployed demo: they live in that instance's `/tmp`
  and disappear when it is recycled, and two instances don't share them.
- **Abuse limits:** advisement and transcript upload are limited per IP (5/minute,
  30/hour by default) on top of the per-session limit; CORS allows only the
  deployment's own origins.

## Known limitations

- Rules cover BMCC programs and the specific F-1, TAP and Pell thresholds above;
  they are simplified and not legal or financial-aid advice.
- Online/hybrid status comes from the catalog's course-level instruction mode, not
  from actual section schedules.
- Sessions are anonymous and stored in SQLite; there is no authentication.

## Team

Built for the AI Innovation Challenge by CUNY students from BMCC and Medgar Evers:

- **D**: backend and AI integration
- **A**: frontend and site
- **J**: PRD, slides and video

Background docs: [Product description](Product_description.md) ·
[Competition brief](Competition_description.md)
