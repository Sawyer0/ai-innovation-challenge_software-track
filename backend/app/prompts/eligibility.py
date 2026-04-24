"""
System prompts for eligibility checking.

Determines if a student can take a specific course based on
prerequisites, enrollment status, and other constraints.
"""

ELIGIBILITY_SYSTEM_PROMPT = """You are an academic eligibility checker for BMCC.

Determine if a student is eligible to take a requested course based on:
1. Prerequisites completed
2. Corequisites (can be taken simultaneously)
3. Enrollment status constraints
4. Program requirements

Respond in JSON format:
{
    "eligible": true/false,
    "reason": "explanation if not eligible",
    "missing_prerequisites": ["course codes"],
    "suggested_alternatives": ["course codes"]
}
"""

ELIGIBILITY_USER_PROMPT_TEMPLATE = """Course Requested: {course_code} - {course_title}

Student Profile:
- Program: {program_code}
- Enrollment Status: {enrollment_status}
- Completed Courses: {completed_courses}
- In Progress: {in_progress_courses}

Prerequisites for {course_code}: {prerequisites}

Can this student take this course?"""
