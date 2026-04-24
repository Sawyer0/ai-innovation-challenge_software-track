# BMCC AI-Powered Backend Implementation Plan

Build a Python + FastAPI backend for BMCC academic advisement with student progress tracking, transcript parsing, prerequisite checking, and AI-powered course recommendations using SQLite for rapid development.

---

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   FastAPI App   │────▶│   SQLite DB  │     │   bmcc-catalog  │
│                 │     │  (dev) /     │     │      .json      │
│  /api/courses   │     │ PostgreSQL   │     │  (seed source)  │
│  /api/programs  │     │  (prod)      │     └─────────────────┘
│  /api/search    │     └──────────────┘
│  /api/recommend │◄────┐
│  /api/chat      │◄────┘
└─────────────────┘     ┌──────────────┐
                        │  OpenAI API  │
                        │  (GPT-4o,   │
                        │ embeddings)  │
                        └──────────────┘
```

---

## Tech Stack

| Component      | Choice                           | Reason                                         |
| -------------- | -------------------------------- | ---------------------------------------------- |
| **Framework**  | FastAPI                          | Auto-generated docs, async support, type hints |
| **ORM**        | SQLAlchemy 2.0                   | Works with both SQLite and PostgreSQL          |
| **Database**   | SQLite (dev) → PostgreSQL (prod) | Easy migration path                            |
| **AI**         | OpenAI SDK + LangChain           | Course recommendations, chat                   |
| **Validation** | Pydantic                         | Native FastAPI integration                     |
| **Testing**    | pytest                           | Standard Python testing                        |

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings (DB URL, OpenAI key)
│   ├── database.py          # SQLAlchemy engine/session
│   ├── models.py            # Database models (complete relational)
│   ├── schemas.py           # Pydantic request/response models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── courses.py       # GET /courses, /courses/{id}
│   │   ├── programs.py      # GET /programs, /programs/{id}
│   │   ├── search.py        # GET /search?q=...
│   │   ├── ai.py            # POST /advisement (main feature)
│   │   └── transcript.py    # POST /parse-transcript
│   ├── services/
│   │   ├── __init__.py
│   │   ├── catalog_loader.py    # Import bmcc-catalog.json
│   │   ├── recommendation.py    # AI recommendation logic
│   │   └── prerequisites.py     # Prerequisite checking engine
│   ├── utils/
│   │   └── embeddings.py        # Course embedding helpers
│   └── parsers/
│       ├── __init__.py
│       ├── image_parser.py      # OCR for transcript images
│       └── csv_parser.py        # CSV transcript parsing
├── data/
│   └── bmcc-catalog.json    # Copy of catalog data
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Database Schema (Complete Relational)

Full schema to support student progress tracking and prerequisite checking:

```sql
-- courses: 3,467 rows
CREATE TABLE courses (
    id INTEGER PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,        -- "ACC 122"
    title VARCHAR(255) NOT NULL,
    long_name VARCHAR(255),
    description TEXT,
    credits DECIMAL(4,2),
    subject VARCHAR(50),
    department VARCHAR(100),
    hegis_code VARCHAR(20),
    typically_offered VARCHAR(100),            -- "Fall, Spring"
    raw_data JSON                            -- Full catalog data
);

-- course_prerequisites: Normalized prerequisite relationships
CREATE TABLE course_prerequisites (
    id INTEGER PRIMARY KEY,
    course_id INTEGER REFERENCES courses(id),
    prerequisite_course_code VARCHAR(20),      -- "MAT 056"
    is_corequisite BOOLEAN DEFAULT FALSE,    -- Can be taken together
    logic_group INTEGER DEFAULT 1,           -- For OR conditions (1 of 3)
    notes TEXT                               -- "or equivalent"
);

-- programs: 111 rows
CREATE TABLE programs (
    id INTEGER PRIMARY KEY,
    program_code VARCHAR(50) UNIQUE NOT NULL,  -- "CSC-AS"
    name VARCHAR(255) NOT NULL,                -- "Computer Science"
    long_name VARCHAR(255),                    -- "Computer Science AS"
    description TEXT,
    degree VARCHAR(50),                        -- "A.S.", "A.A.S."
    department VARCHAR(100),
    hegis_code VARCHAR(20),
    raw_data JSON
);

-- program_course_requirements: Full degree requirements
CREATE TABLE program_requirements (
    id INTEGER PRIMARY KEY,
    program_id INTEGER REFERENCES programs(id),
    course_code VARCHAR(20),                   -- NULL = elective slot
    semester_year VARCHAR(20),                 -- "Year 1"
    semester_term VARCHAR(20),                 -- "Fall", "Spring"
    is_required BOOLEAN DEFAULT TRUE,
    elective_group VARCHAR(50),                -- "Health Ed Elective"
    min_credits DECIMAL(4,2)                 -- For elective slots
);

-- student_sessions: Session-based student data (no auth)
CREATE TABLE student_sessions (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL,    -- UUID for session
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- student_profiles: Academic standing per session
CREATE TABLE student_profiles (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES student_sessions(session_id),
    school VARCHAR(100),                       -- "BMCC"
    program_code VARCHAR(50),                  -- "CSC-AS"
    enrollment_status VARCHAR(50),           -- "full-time", "part-time"
    student_type VARCHAR(50),                  -- "international", "regular"
    financial_aid_type VARCHAR(50),          -- "pell", "tap", NULL
    graduation_year INTEGER,
    graduation_semester VARCHAR(20)            -- "Fall", "Spring"
);

-- student_courses: Courses student has taken or planned
CREATE TABLE student_courses (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES student_sessions(session_id),
    course_code VARCHAR(20),
    semester_taken VARCHAR(20),              -- "Fall 2023"
    status VARCHAR(20),                      -- "completed", "planned", "in-progress"
    grade VARCHAR(5),                          -- "A", "B+", NULL if planned
    credits DECIMAL(4,2),
    source VARCHAR(50)                        -- "manual", "transcript", "plan"
);

-- enrollment_status_rules: Definitions for full-time, half-time, etc.
CREATE TABLE enrollment_status_rules (
    id INTEGER PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL,        -- "full-time", "half-time", "less-than-half-time"
    min_credits DECIMAL(4,2) NOT NULL,         -- 12.0 for full-time
    max_credits DECIMAL(4,2),                  -- NULL = no max, or 18.0 for overload limit
    description TEXT,
    is_default BOOLEAN DEFAULT FALSE           -- Default status for new students
);

-- financial_aid_constraints: Rules for aid recipients
CREATE TABLE financial_aid_constraints (
    id INTEGER PRIMARY KEY,
    aid_type VARCHAR(50) NOT NULL,           -- "pell", "tap", "federal-loan"
    min_credits_required DECIMAL(4,2),       -- 6.0 for Pell half-time, 12.0 for full
    min_status_required VARCHAR(50),         -- "half-time", "full-time"
    warning_message TEXT,                    -- "Dropping below half-time may affect aid"
    block_underload BOOLEAN DEFAULT FALSE,   -- True = prevent scheduling < min
    allow_exception_process BOOLEAN DEFAULT FALSE
);

-- academic_policies: General rules (hardcoded + editable)
CREATE TABLE academic_policies (
    id INTEGER PRIMARY KEY,
    policy_type VARCHAR(50) NOT NULL,        -- "international", "degree-requirement", "prereq-exception"
    policy_code VARCHAR(50),                   -- "INTL-001", "DEG-AS-001"
    description TEXT NOT NULL,
    rule_logic JSON,                           -- {"min_credits": 12, "max_courses": 5}
    applies_to_student_types JSON,           -- ["international", "full-time"]
    applies_to_programs JSON,                -- ["CSC-AS", "all"]
    priority INTEGER DEFAULT 100,              -- Lower = checked first
    is_active BOOLEAN DEFAULT TRUE,
    is_hardcoded BOOLEAN DEFAULT FALSE       -- True = system rule, False = editable
);

-- policy_exceptions: Student-specific overrides (rare cases)
CREATE TABLE policy_exceptions (
    id INTEGER PRIMARY KEY,
    session_id VARCHAR(64) REFERENCES student_sessions(session_id),
    policy_id INTEGER REFERENCES academic_policies(id),
    reason TEXT,
    approved_by VARCHAR(100),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

---

## API Endpoints

### Core Catalog

| Method | Endpoint                | Description                                      |
| ------ | ----------------------- | ------------------------------------------------ |
| GET    | `/api/courses`          | List courses (paginated, filter by subject/dept) |
| GET    | `/api/courses/{code}`   | Get course by code (e.g., `ACC 122`)             |
| GET    | `/api/programs`         | List all programs                                |
| GET    | `/api/programs/{code}`  | Get program with all courses                     |
| GET    | `/api/search?q={query}` | Search courses and programs                      |

### Student & Transcript (Session-Based)

| Method | Endpoint                         | Request Body                                        | Description                                     |
| ------ | -------------------------------- | --------------------------------------------------- | ----------------------------------------------- |
| POST   | `/api/session`                   | `{}`                                                | Create new student session (returns session_id) |
| GET    | `/api/session/:id`               | -                                                   | Get session with courses and profile            |
| POST   | `/api/session/:id/profile`       | `{"school": "BMCC", "program_code": "CSC-AS"}`      | Set student academic standing                   |
| POST   | `/api/session/:id/courses`       | `{"course_code": "ACC 122", "status": "completed"}` | Add course manually                             |
| POST   | `/api/session/:id/transcript`    | `file` (image/PDF/CSV)                              | Upload transcript, auto-extract courses         |
| DELETE | `/api/session/:id/courses/:code` | -                                                   | Remove a course                                 |

### AI Advisement (Main Feature)

| Method | Endpoint                   | Request Body                                                   | Response                          |
| ------ | -------------------------- | -------------------------------------------------------------- | --------------------------------- |
| POST   | `/api/advisement`          | `{"session_id": "...", "message": "What should I take next?"}` | Personalized advisement message   |
| POST   | `/api/advisement/plan`     | `{"session_id": "..."}`                                        | Full semester plan                |
| GET    | `/api/advisement/eligible` | `?session_id=...`                                              | List courses student can take now |
| POST   | `/api/search/semantic`     | `{"query": "programming courses"}`                             | Meaning-based course search       |

### Prerequisite Engine

| Method | Endpoint                            | Description                                   |
| ------ | ----------------------------------- | --------------------------------------------- | ----------------------------- |
| GET    | `/api/courses/:code/prerequisites`  | Get prerequisite chain                        |
| GET    | `/api/courses/:code/eligible-after` | What courses does this unlock?                |
| POST   | `/api/check-eligibility`            | `{"session_id": "...", "course_code": "..."}` | Can student take this course? |

---

## AI Advisement Logic

### Core Feature: Personalized Advisement Messages

Example output: _"Since you've already completed MAT157 in the Summer, you are now able to register MAT206 which is available in the Fall. Does that sound like a plan?"_

```python
async def generate_advisement(session_id: str, student_message: str = None) -> str:
    # 1. Load student data
    profile = get_student_profile(session_id)
    completed_courses = get_completed_courses(session_id)
    planned_courses = get_planned_courses(session_id)
    total_planned_credits = sum(c.credits for c in planned_courses)

    # 2. Check enrollment & financial aid constraints
    constraints = get_applicable_constraints(profile)
    warnings = []
    if profile.financial_aid_type:
        aid_rules = get_financial_aid_rules(profile.financial_aid_type)
        if total_planned_credits < aid_rules.min_credits_required:
            warnings.append(aid_rules.warning_message)

    # 3. Check program requirements
    program = get_program(profile.program_code)
    required_courses = get_remaining_requirements(program, completed_courses)

    # 4. Find immediately eligible courses
    eligible = [
        course for course in required_courses
        if check_prerequisites(course, completed_courses)
    ]

    # 5. Filter by enrollment status capacity
    max_credits = get_max_credits_for_status(profile.enrollment_status)
    remaining_capacity = max_credits - total_planned_credits
    available = [c for c in eligible if c.credits <= remaining_capacity]

    # 6. Check availability by semester
    next_semester = get_next_semester()
    available = [c for c in available if c.available_in(next_semester)]

    # 7. Build prompt for LLM with constraints
    prompt = f"""
    Student: {profile.enrollment_status}, {profile.student_type}, aid: {profile.financial_aid_type}
    Completed: {', '.join(completed_courses)}
    Can take now: {', '.join(available)}
    Max credits this term: {remaining_capacity}
    Warnings: {'; '.join(warnings)}
    Goal: Complete {profile.program_code} by {profile.graduation_semester} {profile.graduation_year}

    Generate a friendly, personalized advisement message suggesting 2-3 courses.
    IMPORTANT: Respect enrollment constraints and warn about aid implications if applicable.
    """

    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful BMCC academic advisor."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
```

### Prerequisite Checking Engine

```python
def check_prerequisites(course_code: str, completed_courses: list[str]) -> bool:
    """
    Check if student can take a course.
    Handles complex logic: AND conditions, OR conditions, minimum grades.
    """
    prereqs = get_prerequisites(course_code)

    for group in prereqs:
        # At least one course in each logic group must be satisfied
        if not any(p in completed_courses for p in group.courses):
            return False
    return True

def get_prerequisite_chain(course_code: str) -> list[list[str]]:
    """
    Return full prerequisite tree (for visualization).
    Example: MAT206 requires [MAT157] requires [MAT056 or MAT150]
    """
    # BFS/DFS to build chain
```

### Transcript Parsing

```python
async def parse_transcript(file: UploadFile) -> list[ParsedCourse]:
    """
    Handle image (OCR), PDF (text extraction), or CSV.
    Return extracted course codes and semester info.
    """
    if file.content_type.startswith('image'):
        return await parse_image_transcript(file)
    elif file.content_type == 'application/pdf':
        return await parse_pdf_transcript(file)
    elif file.content_type in ['text/csv', 'application/vnd.ms-excel']:
        return await parse_csv_transcript(file)
```

---

## Implementation Steps

### Phase 1: Core Setup (45 min)

1. Create `backend/` directory structure
2. Set up FastAPI with SQLAlchemy
3. Create complete relational models (courses, programs, prerequisites, student tables)
4. Add data import script (bmcc-catalog.json → SQLite)
5. Seed prerequisite relationships

### Phase 2: Student & Transcript API (45 min)

1. Implement session creation (`POST /api/session`)
2. Implement transcript upload (`POST /api/session/:id/transcript`)
3. Add OCR/parser for images and PDFs (use OpenAI Vision API or pytesseract)
4. Implement manual course entry endpoints
5. Test with sample transcript data

### Phase 3: AI Advisement & Prerequisites (60 min)

1. Implement prerequisite checking engine
2. Build eligibility checker (`GET /api/advisement/eligible`)
3. Implement main advisement endpoint (`POST /api/advisement`)
4. Add plan generation (`POST /api/advisement/plan`)
5. Test with sample student profiles
6. Verify AI output quality

### Phase 4: Team Handoff (30 min)

1. Generate API documentation (FastAPI auto-docs at `/docs`)
2. Create `API.md` with example requests/responses for frontend team
3. Add CORS for frontend
4. Create `.env.example`

---

## Environment Variables

```env
# Database
DATABASE_URL=sqlite:///./bmcc_catalog.db
# For PostgreSQL later: postgresql://user:pass@localhost/bmcc_catalog

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# App
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## Migration to PostgreSQL

When ready for production:

```bash
# 1. Update DATABASE_URL in .env
DATABASE_URL=postgresql://user:pass@localhost/bmcc_catalog

# 2. Install pgvector extension for embeddings
# 3. Run same data import script
# 4. Enable vector similarity search
```

SQLAlchemy handles 95% of the migration automatically.

---

## Key Dependencies

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
openai>=1.12.0
python-multipart>=0.0.6      # File uploads
python-dotenv>=1.0.0
httpx>=0.26.0

# Transcript parsing (choose based on complexity)
pymupdf>=1.23.0              # PDF text extraction
pytesseract>=0.3.10          # OCR for images
pillow>=10.0.0               # Image processing
pandas>=2.0.0                # CSV parsing
```

---

## Success Metrics

- [ ] API serves all 3,467 courses in <100ms
- [ ] Program detail includes full course roadmap
- [ ] Student session created with unique ID
- [ ] Transcript upload extracts courses (image/PDF/CSV)
- [ ] Prerequisite checking works for sample courses
- [ ] AI advisement generates contextual messages
- [ ] `/api/advisement/eligible` returns available courses
- [ ] Frontend team has API documentation
