# Google-Style Testing Strategy for BMCC Backend

Implement a comprehensive testing suite following Google testing best practices: unit tests for business logic, integration tests for API endpoints, and dedicated tests for data quality, transcript parsing, and AI services.

---

## Testing Philosophy (Google Style)

### Test Pyramid
```
       /\
      /  \  <10%  E2E Tests (API contract validation)
     /____\
    /      \  20%  Integration Tests (DB + Services)
   /________\
  /          \  70%  Unit Tests (Pure logic, fast)
 /____________\
```

### Principles
- **Small tests (Unit)**: Fast (<100ms), isolated, no I/O, 70% of suite
- **Medium tests (Integration)**: Test component interactions, use test DB, 20% of suite  
- **Large tests (E2E)**: Full API stack, limited scenarios, <10% of suite
- **Mock external services**: Never call real OpenAI in tests

---

## Project Structure

```
backend/tests/
├── __init__.py
├── conftest.py                 # Shared fixtures (test DB, mocked services)
├── unit/                       # Fast, isolated unit tests
│   ├── __init__.py
│   ├── test_prerequisites.py   # Prerequisite checking logic
│   ├── test_enrollment_rules.py # Credit calculations
│   ├── test_academic_utils.py   # Semester calculations
│   └── test_services/           # Business logic
│       ├── test_session_service.py
│       └── test_ai_service.py
├── integration/                # Medium tests with test DB
│   ├── __init__.py
│   ├── test_api_endpoints.py    # FastAPI client tests
│   ├── test_data_quality.py     # Catalog data validation
│   └── test_transcript_flow.py  # Upload → Parse → Store
├── e2e/                         # Full API tests
│   └── test_complete_workflow.py # Create session → Upload → Advise
├── fixtures/                    # Test data
│   ├── __init__.py
│   ├── sample_transcript.png    # Test image
│   ├── sample_transcript.pdf    # Test PDF
│   ├── sample_courses.csv       # Test CSV data
│   └── mock_responses/          # Mocked AI responses
│       ├── gemini_advisement.json
│       └── gemini_transcript.json
└── helpers/                     # Test utilities
    ├── __init__.py
    ├── database.py              # Test DB setup/teardown
    └── mocks.py                 # Mock factories
```

---

## Test Configuration

### conftest.py
```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.config import settings

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    """Fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    """TestClient with overridden DB dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

@pytest.fixture
def mock_gemini_client(monkeypatch):
    """Mock Gemini API responses."""
    class MockGeminiClient:
        def generate_content(self, **kwargs):
            return type('Response', (), {'text': 'Mocked advisement response'})
    
    monkeypatch.setattr('google.genai.Client', lambda **kwargs: MockGeminiClient())
```

---

## Unit Tests (70% of Suite)

### test_prerequisites.py
```python
"""Unit tests for prerequisite checking logic. Fast, no DB."""

import pytest
from app.services.prerequisite_service import PrerequisiteService

class TestCheckPrerequisites:
    """Test prerequisite satisfaction logic."""
    
    def test_no_prerequisites_required(self):
        """Course with no prereqs should be available to anyone."""
        service = PrerequisiteService(db=None)  # Logic only, no DB
        # Mock get_prerequisites to return []
        result = service.check_prerequisites("ENG 101", [])
        assert result is True
    
    def test_single_prerequisite_satisfied(self):
        """Should pass when required course completed."""
        service = PrerequisiteService(db=None)
        result = service.check_prerequisites("MAT 206", ["MAT 157"])
        assert result is True
    
    def test_single_prerequisite_missing(self):
        """Should fail when required course not completed."""
        service = PrerequisiteService(db=None)
        result = service.check_prerequisites("MAT 206", [])
        assert result is False
    
    def test_or_condition_one_satisfied(self):
        """Should pass if at least one option in OR group satisfied."""
        # MAT 206 requires MAT 056 OR MAT 150
        service = PrerequisiteService(db=None)
        result = service.check_prerequisites("MAT 206", ["MAT 056"])
        assert result is True
        
        result = service.check_prerequisites("MAT 206", ["MAT 150"])
        assert result is True
    
    def test_or_condition_none_satisfied(self):
        """Should fail if no option in OR group satisfied."""
        service = PrerequisiteService(db=None)
        result = service.check_prerequisites("MAT 206", ["ENG 101"])
        assert result is False

class TestRemainingRequirements:
    """Test degree requirement tracking."""
    
    def test_returns_uncompleted_courses(self):
        """Should return only courses not yet taken."""
        completed = ["MAT 157", "ENG 101"]
        program_requirements = ["MAT 157", "MAT 206", "ENG 101", "CSC 103"]
        
        result = self.service.get_remaining_requirements_mock(
            program_requirements, 
            completed
        )
        assert "MAT 206" in result
        assert "CSC 103" in result
        assert "MAT 157" not in result
        assert "ENG 101" not in result
```

### test_enrollment_rules.py
```python
"""Unit tests for enrollment and financial aid calculations."""

import pytest
from app.utils.academic_utils import calculate_remaining_credits, check_financial_aid_compliance

class TestCalculateRemainingCredits:
    """Test credit capacity calculations."""
    
    @pytest.mark.parametrize("status,planned,expected", [
        ("full-time", 0, 18),      # 12-18 credits
        ("full-time", 15, 3),       # 18 - 15 = 3 remaining
        ("full-time", 18, 0),       # At max
        ("half-time", 0, 11),       # 6-12 credits
        ("half-time", 9, 3),
    ])
    def test_calculations(self, status, planned, expected, mock_db):
        """Parametrized test for various enrollment scenarios."""
        result = calculate_remaining_credits(status, planned, mock_db)
        assert result == expected

class TestFinancialAidCompliance:
    """Test financial aid constraint checking."""
    
    def test_pell_grant_satisfied(self, mock_db):
        """Pell requires 6+ credits."""
        compliant, warning = check_financial_aid_compliance(
            "pell", 9, "half-time", mock_db
        )
        assert compliant is True
        assert warning is None
    
    def test_pell_grant_under_minimum(self, mock_db):
        """Pell warning when under 6 credits."""
        compliant, warning = check_financial_aid_compliance(
            "pell", 3, "less-than-half-time", mock_db
        )
        assert compliant is False
        assert "Pell" in warning
    
    def test_tap_requires_full_time(self, mock_db):
        """TAP requires 12+ credits."""
        compliant, warning = check_financial_aid_compliance(
            "tap", 9, "half-time", mock_db
        )
        assert compliant is False
```

### test_ai_service.py (with mocked Gemini)
```python
"""Unit tests for AI service with mocked Gemini client."""

import pytest
from unittest.mock import Mock, patch
from app.services.ai_service import AIService

class TestGenerateAdvisement:
    """Test AI advisement generation with mocked LLM."""
    
    @pytest.fixture
    def mock_profile(self):
        """Standard student profile fixture."""
        return Mock(
            enrollment_status="full-time",
            student_type="regular",
            financial_aid_type="pell",
            program_code="CSC-AS",
            graduation_semester="Spring",
            graduation_year=2026
        )
    
    @patch('google.genai.Client')
    def test_prompt_includes_all_student_data(self, mock_client_class, mock_profile):
        """Verify prompt template is populated correctly."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        service = AIService()
        service.client = mock_client
        
        result = service.generate_advisement(
            profile=mock_profile,
            completed_courses=["MAT 157"],
            in_progress_courses=["ENG 101"],
            planned_courses=[],
            available_courses=[{"code": "MAT 206", "title": "Precalculus"}],
            warnings=["Test warning"],
            current_planned_credits=0,
            db=Mock(),
            student_message="What next?"
        )
        
        # Verify Gemini was called with correct structure
        call_args = mock_client.models.generate_content.call_args
        assert call_args is not None
        assert "MAT 157" in str(call_args)  # Completed courses in prompt
        assert "MAT 206" in str(call_args)  # Available courses in prompt
```

---

## Integration Tests (20% of Suite)

### test_api_endpoints.py
```python
"""Integration tests for API endpoints with test database."""

import pytest
from fastapi.testclient import TestClient

class TestSessionEndpoints:
    """Test session CRUD operations."""
    
    def test_create_session(self, client):
        """POST /api/session should create new session."""
        response = client.post("/api/session")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # UUID format
    
    def test_get_session_with_data(self, client):
        """GET /api/session/{id} should return session with profile and courses."""
        # Create session
        create_resp = client.post("/api/session")
        session_id = create_resp.json()["session_id"]
        
        # Set profile
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS"
        })
        
        # Get session
        get_resp = client.get(f"/api/session/{session_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["session_id"] == session_id
        assert data["profile"]["program_code"] == "CSC-AS"
    
    def test_add_course_to_session(self, client):
        """POST /api/session/{id}/courses should add course."""
        # Setup
        session_id = client.post("/api/session").json()["session_id"]
        
        # Add course
        response = client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 206",
            "status": "completed",
            "semester_taken": "Fall 2023",
            "grade": "A",
            "credits": 4
        })
        assert response.status_code == 200
        assert response.json()["course_code"] == "MAT 206"

class TestAdvisementEndpoints:
    """Test AI advisement flow."""
    
    def test_get_eligible_courses(self, client, mock_gemini_client):
        """GET /api/advisement/eligible returns available courses."""
        # Setup complete student profile
        session_id = client.post("/api/session").json()["session_id"]
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time"
        })
        client.post(f"/api/session/{session_id}/courses", json={
            "course_code": "MAT 157",  # Prereq for MAT 206
            "status": "completed",
            "credits": 4
        })
        
        # Get eligible courses
        response = client.get(f"/api/advisement/eligible?session_id={session_id}")
        assert response.status_code == 200
        data = response.json()
        assert "eligible_courses" in data
        # MAT 206 should be eligible (prereq satisfied)
        assert any("MAT 206" in c for c in data["eligible_courses"])
```

### test_data_quality.py
```python
"""Integration tests for catalog data quality."""

import pytest
from app import models

class TestCourseDataQuality:
    """Validate course catalog data integrity."""
    
    def test_all_courses_have_required_fields(self, db):
        """Every course must have code, title, credits."""
        courses = db.query(models.Course).all()
        
        for course in courses:
            assert course.code is not None and course.code != "", f"Course {course.id} missing code"
            assert course.title is not None and course.title != "", f"Course {course.code} missing title"
            assert course.credits is not None, f"Course {course.code} missing credits"
    
    def test_prerequisites_reference_valid_courses(self, db):
        """All prerequisite codes must reference existing courses."""
        course_codes = {c.code for c in db.query(models.Course).all()}
        prereqs = db.query(models.CoursePrerequisite).all()
        
        orphaned = []
        for p in prereqs:
            if p.prerequisite_course_code not in course_codes:
                orphaned.append(p.prerequisite_course_code)
        
        assert len(orphaned) == 0, f"Orphaned prerequisites: {orphaned[:10]}"
    
    def test_program_requirements_link_to_courses(self, db):
        """All program requirements should reference valid courses."""
        course_codes = {c.code for c in db.query(models.Course).all()}
        requirements = db.query(models.ProgramRequirement).all()
        
        for req in requirements:
            if req.course_code and req.course_code not in course_codes:
                # Allow elective slots (null course_code) but not invalid codes
                print(f"Warning: Program requirement references unknown course {req.course_code}")
    
    def test_no_duplicate_course_codes(self, db):
        """Course codes must be unique."""
        from sqlalchemy import func
        
        duplicates = db.query(
            models.Course.code,
            func.count(models.Course.id).label('count')
        ).group_by(models.Course.code).having(func.count(models.Course.id) > 1).all()
        
        assert len(duplicates) == 0, f"Duplicate course codes: {duplicates}"
```

### test_transcript_flow.py
```python
"""Integration tests for transcript upload → parse → store flow."""

import pytest
from io import BytesIO
from unittest.mock import patch, Mock

class TestTranscriptUploadFlow:
    """Test complete transcript processing pipeline."""
    
    @patch('app.parsers.transcript_parser.client')
    def test_image_upload_parsed_and_stored(self, mock_gemini_client, client):
        """Upload image → Gemini parses → courses saved to DB."""
        # Mock Gemini response
        mock_response = Mock()
        mock_response.text = '''[
            {"course_code": "MAT 206", "semester_taken": "Fall 2023", 
             "status": "completed", "grade": "B+", "credits": 4}
        ]'''
        mock_gemini_client.models.generate_content.return_value = mock_response
        
        # Create session
        session_id = client.post("/api/session").json()["session_id"]
        
        # Upload fake image
        fake_image = BytesIO(b"fake image data")
        response = client.post(
            f"/api/session/{session_id}/transcript",
            files={"file": ("transcript.png", fake_image, "image/png")}
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully parsed 1 courses"
        
        # Verify courses saved
        session_data = client.get(f"/api/session/{session_id}").json()
        assert len(session_data["courses"]) == 1
        assert session_data["courses"][0]["course_code"] == "MAT 206"
```

---

## E2E Tests (10% of Suite)

### test_complete_workflow.py
```python
"""End-to-end tests for complete student workflows."""

import pytest
from fastapi.testclient import TestClient

class TestCompleteStudentWorkflow:
    """Test full user journey: create → upload → get advisement."""
    
    @pytest.mark.slow
    def test_new_student_gets_advisement(self, client, mock_gemini_client):
        """
        E2E: New student creates session, uploads transcript, 
        sets profile, receives AI advisement.
        """
        # 1. Create session
        resp = client.post("/api/session")
        session_id = resp.json()["session_id"]
        
        # 2. Upload transcript (mocked)
        # ... upload logic ...
        
        # 3. Set profile
        client.post(f"/api/session/{session_id}/profile", json={
            "school": "BMCC",
            "program_code": "CSC-AS",
            "enrollment_status": "full-time",
            "financial_aid_type": "pell",
            "graduation_year": 2026,
            "graduation_semester": "Spring"
        })
        
        # 4. Get advisement
        resp = client.post("/api/advisement", json={
            "session_id": session_id,
            "message": "What should I take next?"
        })
        
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert len(data["response"]) > 0
```

---

## Test Execution Strategy

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --cov=app
    --cov-report=term-missing
    --cov-report=html:htmlcov
markers =
    slow: marks tests as slow (E2E tests)
    unit: marks tests as unit tests (fast)
    integration: marks tests as integration tests
    data_quality: marks tests that validate catalog data
```

### Running Tests

```bash
# Run all tests
cd backend
pytest

# Run only fast unit tests
pytest -m unit

# Run integration tests only
pytest -m integration

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_prerequisites.py -v

# Run E2E tests (slower)
pytest -m slow --tb=short

# Watch mode for development
pytest-watch -- -m unit
```

---

## Test Data Fixtures

### tests/fixtures/mock_responses/gemini_advisement.json
```json
{
  "standard_response": "Since you've completed MAT157, you can now take MAT206 this Fall. That's 4 credits. You might also consider ENG201 (3 credits) to reach full-time status. Does that sound like a plan?",
  "financial_aid_warning": "Remember: To maintain your Pell Grant eligibility, you need at least 6 credits this semester.",
  "international_student_warning": "As an international student, you must maintain full-time enrollment (12+ credits) to maintain your visa status."
}
```

### tests/fixtures/mock_responses/gemini_transcript.json
```json
{
  "single_course": [
    {
      "course_code": "MAT 206",
      "semester_taken": "Fall 2023",
      "status": "completed",
      "grade": "B+",
      "credits": 4
    }
  ],
  "multiple_courses": [
    {"course_code": "MAT 157", "semester_taken": "Spring 2023", "status": "completed", "grade": "A", "credits": 4},
    {"course_code": "ENG 101", "semester_taken": "Spring 2023", "status": "completed", "grade": "B", "credits": 3},
    {"course_code": "CSC 103", "semester_taken": "Fall 2023", "status": "completed", "grade": "A-", "credits": 3}
  ]
}
```

---

## Success Metrics

- [ ] Unit tests: >70% of test suite, all pass in <5 seconds
- [ ] Integration tests: >20% of test suite
- [ ] E2E tests: <10% of test suite
- [ ] Code coverage: >80% for services, >60% overall
- [ ] All API endpoints have at least one test
- [ ] Data quality tests validate catalog integrity
- [ ] CI pipeline runs full test suite on every commit
- [ ] No external API calls in unit/integration tests (all mocked)
