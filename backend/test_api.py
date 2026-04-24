import httpx
import asyncio

async def test_endpoints():
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
        print("Testing /api/courses...")
        resp = await client.get("/api/courses?limit=1")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response:", resp.json())
        
        print("\nTesting /api/programs...")
        resp = await client.get("/api/programs?limit=1")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response:", resp.json())
            
        print("\nTesting session creation...")
        resp = await client.post("/api/session/")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            session_data = resp.json()
            session_id = session_data["session_id"]
            print(f"Created session: {session_id}")
            
            print("\nTesting get session...")
            resp = await client.get(f"/api/session/{session_id}")
            print(f"Status: {resp.status_code}")
            
            print("\nTesting set profile...")
            profile_data = {
                "program_code": "043", # Example
                "enrollment_status": "full-time",
                "student_type": "freshman",
                "financial_aid_type": "pell",
                "graduation_semester": "Spring",
                "graduation_year": 2026
            }
            resp = await client.post(f"/api/session/{session_id}/profile", json=profile_data)
            print(f"Status: {resp.status_code}")
            
            print("\nTesting add course...")
            course_data = {
                "course_code": "ENG 101",
                "semester_taken": "Fall 2024",
                "status": "completed",
                "grade": "A",
                "credits": 3.0,
                "source": "manual"
            }
            resp = await client.post(f"/api/session/{session_id}/courses", json=course_data)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Added course.")

            print("\nTesting get eligible courses...")
            resp = await client.get(f"/api/advisement/eligible", params={"session_id": session_id})
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Eligible:", resp.json())
            else:
                print("Error details:", resp.text)

            print("\nTesting LLM Advisement Generation...")
            chat_payload = {
                "session_id": session_id,
                "message": "I've just finished ENG 101. What should I take next spring?"
            }
            # Set a slightly longer timeout for LLM generation
            resp = await client.post(f"/api/advisement/", json=chat_payload, timeout=30.0)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Advisement LLM Response:\n", resp.json().get("response"))
            else:
                print("Error details:", resp.text)

            print("\nTesting LLM Transcript Parsing...")
            # Create a fake transcript file
            fake_transcript_content = b"Student Name: John Doe\nSchool: BMCC\nTerm: Fall 2024\nCourse: MAT 150 - Intro to Calculus\nGrade: B\nCredits: 4.0\nStatus: completed\n"
            files = {'file': ('transcript.txt', fake_transcript_content, 'text/plain')}
            resp = await client.post(f"/api/session/{session_id}/transcript", files=files, timeout=30.0)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print("Parsed Courses from Transcript:\n", resp.json())
            else:
                print("Error details:", resp.text)

if __name__ == "__main__":
    asyncio.run(test_endpoints())
