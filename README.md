# Project X

AI-powered academic advisement for community college students. Upload your transcript, set your goals, and get personalized course recommendations with financial aid compliance built in.

## The Problem

Community college students face complex decisions every semester:

- Which courses satisfy degree requirements?
- What are the prerequisites for my target courses?
- Will dropping a course affect my financial aid?
- Am I on track to graduate on time?

Most students rely on overworked advisors or navigate confusing degree audit systems like DegreeWorks on their own.

## Our Solution

Project X is an AI academic advisor that:

1. **Reads your transcript** — Upload a screenshot, PDF, or CSV from CUNYfirst
2. **Checks your standing** — Full-time? International? Financial aid recipient? We factor it all in
3. **Suggests courses** — "Since you completed MAT157, you can take MAT206 this Fall"
4. **Warns about aid** — "Dropping below 6 credits will affect your Pell Grant"
5. **Builds your plan** — Full roadmap to graduation based on your pace

## How It Works

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Upload     │───▶│  AI Parser  │───▶│  Check      │
│  Transcript │    │  (OCR/LLM)  │    │  Prerequisites
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐
│  Get        │◄───│  Generate   │◄───│  Apply      │
│  Advice     │    │  Response   │    │  Constraints│
└─────────────┘    └─────────────┘    └─────────────┘
```

## Features

### For Students

- **No login required** — Start immediately with a session ID
- **Transcript upload** — Drag & drop screenshots, PDFs, or CSVs
- **Smart eligibility** — See exactly which courses you can take next
- **Contextual advice** — Natural language responses, not just lists
- **Compliance aware** — Financial aid and enrollment status rules built in

### For Advisors

- **Prerequisite chains** — Visualize full course dependency trees
- **Policy enforcement** — Automatic warnings for enrollment violations
- **Student insights** — See where students struggle with requirements

## Tech Stack

| Layer           | Technology                                           |
| --------------- | ---------------------------------------------------- |
| **Frontend**    | React / Next.js                                      |
| **Backend**     | FastAPI + SQLAlchemy                                 |
| **Database**    | SQLite (dev) / PostgreSQL (prod)                     |
| **AI**          | Google Gemini 2.5 Flash + Vision API                 |
| **Data Source** | BMCC Coursedog Catalog (3,467 courses, 111 programs) |

## Data

We use the official BMCC course catalog:

- **3,467 courses** with prerequisites, descriptions, credit hours
- **111 programs** with degree maps and requirements
- **Real-time catalog** scraped from Coursedog API

## API

The backend exposes REST endpoints for:

- `POST /api/session` — Create student session
- `POST /api/session/{id}/transcript` — Upload and parse transcript
- `POST /api/advisement` — Get AI recommendation
- `GET /api/advisement/eligible` — List available courses

See [backend/README.md](backend/README.md) for full documentation.

## Project Structure

```
ai-innovation-challenge/
├── README.md              # This file — product overview
├── BACKEND_PLAN.md        # Technical architecture & schema
├── backend/               # FastAPI backend
│   ├── README.md          # Backend setup & API docs
│   ├── app/               # Source code
│   └── requirements.txt
├── data/                  # Catalog data
│   ├── bmcc-catalog.json  # Full course catalog (3,467 courses)
│   └── bmcc-programs.json # Program listings (111 programs)
└── scrape_bmcc.py         # Catalog scraping script
```

## Getting Started

### Prerequisites

- Python 3.11+
- Google Gemini API key

### Quick Start

```bash
# 1. Clone and enter backend
cd backend

# 2. Set up Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and add: GEMINI_API_KEY=your-key-here

# 4. Import catalog data
python -m app.scripts.import_catalog

# 5. Start server
uvicorn app.main:app --reload

# 6. Test API
open http://localhost:8000/docs
```

## Example Usage

### Create a Student Session

```bash
curl -X POST http://localhost:8000/api/session
```

Response:

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "created_at": "2024-04-24T20:00:00Z"
}
```

### Set Student Profile

```bash
curl -X POST http://localhost:8000/api/session/a1b2c3d4/profile \
  -H "Content-Type: application/json" \
  -d '{
    "school": "BMCC",
    "program_code": "CSC-AS",
    "enrollment_status": "full-time",
    "financial_aid_type": "pell",
    "graduation_year": 2026
  }'
```

### Get AI Advisement

```bash
curl -X POST http://localhost:8000/api/advisement \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4",
    "message": "What should I take next semester?"
  }'
```

Response:

```json
{
  "message": "Since you've already completed MAT157 in the Summer, you are now able to register MAT206 which is available in the Fall. Does that sound like a plan?",
  "suggested_courses": ["MAT206", "CSC103", "ENG201"],
  "warnings": ["Remember: To keep your Pell Grant, stay at 6+ credits."],
  "total_credits": 12
}
```

## Roadmap

### Phase 1 — Core (In Progress)

- [x] Scrape BMCC catalog (3,467 courses)
- [x] Design backend architecture
- [ ] Build FastAPI backend
- [ ] Implement transcript parsing
- [ ] Add AI advisement endpoint

### Phase 2 — AI Features

- [ ] Prerequisite checking engine
- [ ] Financial aid compliance warnings
- [ ] Semantic course search
- [ ] Full degree planning

### Phase 3 — Scale

- [ ] Support multiple CUNY colleges
- [ ] Integration with CUNYfirst (if permitted)
- [ ] Advisor dashboard
- [ ] Analytics on student pathways

## Team

This project was built for the **AI Innovation Challenge - Software Track** by:

- [Team Member] — Backend & AI
- [Team Member] — Frontend
- [Team Member] — Data & Research

## License

MIT


