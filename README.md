# Project DJA — Compliance-Aware AI Advising for CUNY

An AI academic advisor that doesn't just suggest courses — it protects students' visa status, financial aid, and graduation timeline before making any recommendation.

Built for the **AI Innovation Challenge – AI Software (Agentic AI) Track** by BMCC students, for CUNY students.

---

## The Problem

For a typical student, bad academic advice is an inconvenience. For a CUNY student, it can be a crisis.

- An international student who drops below 12 credits **risks visa revocation**
- A TAP recipient who takes a non-allowable elective **loses funding**
- A Pell recipient who drops to 9 credits **silently loses 25% of their award**

Human advisors are overloaded. DegreeWorks enforces degree compliance — not the student's legal, financial, or life circumstances. Project DJA fills that gap.

---

## How It Works

```
Student Profile
(major, courses, visa status, aid type, career goal)
        │
        ▼
┌─────────────────────────────────┐
│   Compliance Guardrail          │  ← Deterministic Python, NOT AI
│   • F-1 visa: ≥12 credits,     │
│     ≤1 online course            │
│   • TAP: ≥12 credits required   │
│   • Pell: ≥6 credits required   │
└──────────────┬──────────────────┘
               │ passes? ─── NO ──▶ 422 + plain-English explanation
               │ YES
               ▼
┌─────────────────────────────────┐
│   Claude AI (Agentic)           │  ← Primary: Claude Sonnet
│   • get_remaining_requirements  │    Fallback: Gemini 2.5 Flash
│   • get_eligible_courses        │
│   • Career-aligned rationale    │
│   • Structured JSON output      │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│   Post-AI Annotation            │
│   • TAP elective allowability   │
│   • Pell proration display      │
└──────────────┬──────────────────┘
               ▼
     Structured Plan Response
     (per-course: requirement cited,
      compliance status, career rationale)
```

---

## Key Design Decision

**Compliance logic is deterministic Python — not AI.** Rules that determine whether a student keeps their F-1 visa or their Pell Grant must be auditable and guaranteed. Claude handles personalization; code handles protection. The AI cannot override a compliance block.

---

## Features

### Function 1 — Profile Intake
- Academic profile: school, major, completed courses
- Compliance profile: visa status, financial aid type, enrollment status
- Career goal (free text) — used to personalize every course rationale

### Function 2 — Compliance Guardrail (deterministic, pre-AI)
- **Visa rule:** F-1 students must have ≥12 credits and ≤1 online/hybrid course — hard block with 422 before AI runs
- **Financial aid block:** TAP requires ≥12 credits, Pell requires ≥6 — hard block before AI runs
- **TAP elective check:** Flags any recommended elective not in the program's TAP-allowable list — post-AI annotation per course
- **Pell proration:** Shows exact award percentage based on planned credits (12=100%, 9=75%, 6=50%)

### Function 3 — AI Recommendation Engine
- **Primary AI:** Claude Sonnet (Anthropic) with structured JSON output
- **Fallback AI:** Google Gemini 2.5 Flash (automatic, transparent to user)
- **Transcript parsing:** Claude Vision reads uploaded PDFs and screenshots → Gemini fallback
- Recommends 3–5 prerequisite-cleared courses per semester
- Every recommendation includes: degree requirement satisfied, compliance status, career rationale, and why this semester

### Function 4 — Output
- Structured per-course plan — not freeform prose
- Always-visible advisor disclaimer
- Pell proration widget for eligible students
- TAP elective warnings annotated per flagged course

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML / CSS / JS (single-page) |
| **Backend** | Python, FastAPI, SQLAlchemy |
| **Primary AI** | Claude Sonnet (Anthropic) — vision + advisement |
| **Fallback AI** | Google Gemini 2.5 Flash |
| **Database** | SQLite (dev) / PostgreSQL (prod) |
| **Course Data** | BMCC Catalog — 3,467 courses, 111 programs |

---

## API Response Shape

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
      "career_rationale": "Algorithm design is foundational to robotics path planning and sensor processing.",
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

---

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key (`ANTHROPIC_API_KEY`)
- Google Gemini API key (`GEMINI_API_KEY`) — fallback only

### Setup

```bash
# 1. Enter backend
cd backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Add to .env:
#   ANTHROPIC_API_KEY=sk-ant-...
#   GEMINI_API_KEY=...

# 5. Import catalog (seeds courses, programs, and compliance rules)
python -m app.scripts.import_catalog

# 6. Start server
uvicorn app.main:app --reload

# 7. Explore API
open http://localhost:8000/docs
```

---

## User Journeys

**Journey 1 — F-1 International Student**
Sarah is an accepted international student registering for Fall. She enters her profile with `student_type: "international"`. DJA enforces ≥12 credits and flags if she selects more than 1 online course — before the AI runs.

**Journey 2 — TAP Recipient Transfer Student**
Marcus transferred in with 18 credits and receives TAP. DJA flags any recommended elective outside his program's TAP-allowable list, with a plain-English note to confirm with financial aid before registering.

**Journey 3 — Incoming BMCC Engineering Science Student**
Priya is entering BMCC with an interest in robotics. She sets her career goal. Every recommended course includes a sentence explaining how it moves her toward robotics — not generic degree boilerplate.

---

## Public Interest Technology Alignment

| PIT Principle | How DJA Implements It |
|---|---|
| Systems Thinking | Models degree → visa → aid → work constraints → career as one system |
| Ethical Decision-Making | AI never presents as authoritative; every output ends with advisor disclaimer; no data stored beyond session |
| Equity & Inclusion | Guardrails exist because the highest-stakes mistakes fall on international, low-income, and working students |
| Engage Communities | Team is CUNY students from BMCC and Medgar Evers — we are the user |
| Interdisciplinarity | Combines education policy, immigration law, software engineering, and UX |
| Transparency & Accountability | Every course shows requirement satisfied, compliance status, and plain-language rationale |
| Continuous Learning | JSON catalog and guardrail rules are modular — policy changes update the data layer, not the model |
| PIT Technological Intuition | Compliance is deterministic Python; AI handles only personalization |
| Champion the Public Interest | CUNY serves ~225,000 students, majority first-generation, working, or low-income |

---

## Project Structure

```
ai-innovation-challenge_software-track/
├── README.md                  # This file
├── README.original.md         # Original README (reference)
├── Product_description.md     # Full PRD
├── Competition_description.md # Competition brief
├── bmcc-catalog.json          # 3,467 courses, 111 programs
└── backend/
    ├── README.md              # Backend setup & full API reference
    └── app/
        ├── routers/           # API endpoints
        ├── services/          # Business logic + AI integration
        ├── parsers/           # Transcript parsing (Claude + Gemini fallback)
        ├── prompts/           # Centralized AI system prompts
        ├── utils/             # Compliance guardrail functions
        └── models.py          # Database schema
```

---

## Team

Built for the **AI Innovation Challenge – Software Track** hosted by BMCC Technology Learning Community and BMCC Tech Innovation Hub.

- **D** — Backend & AI integration
- **A** — Frontend & site
- **J** — PRD, slides & video
