Project One-Liner (use this everywhere — slides, website, video opener)
Project DJA — Compliance-Aware AI Advising for CUNY. An AI academic advisor that doesn't just suggest courses — it protects students' visa status, financial aid, and graduation timeline before making any recommendation.
Refined Problem Statement
For a typical student, bad academic advice is an inconvenience. For a CUNY student, it can be a crisis. An international student who drops below 12 credits risks visa revocation. A TAP recipient who takes an elective not listed as "allowable" in DegreeWorks loses funding. A Pell recipient who drops to 9 credits silently loses 25% of their award. Human advisors are overloaded and optimize for institutional retention — not the student's legal, financial, or career outcomes. DegreeWorks enforces compliance with the degree, but not with the student's life circumstances. Project DJA fills that gap.
Refined Solution Description
Project DJA is an agentic AI advisor that ingests a student's school, major, completed coursework, career goal, and compliance profile (visa status, aid type, work schedule), then produces a personalized next-semester plan. Before any course is recommended, the plan passes through a Compliance Guardrail that flags visa, TAP, Pell, and scheduling risks. Every recommendation is explained, cited to a requirement, and accompanied by a human-advisor confirmation prompt.
How We Built It (tech stack answer)
Frontend: HTML/CSS/JS (single-page site). Backend: Python with Claude API (agentic tool use). Data layer: curated JSON course catalog for BMCC (Engineering Science + one additional major) with prerequisite graph. Guardrail logic: deterministic Python rules run before the LLM sees the query, so the LLM cannot override compliance constraints. Chatbot: Claude-powered follow-up Q&A scoped to the student's generated plan. Hosted on GitHub Pages / Vercel. Tools: Claude, Windsurf, Antigravity, GitHub, Google Workspace.
Public Interest Technology Alignment (all 9 guidelines)
This is where you win the track. Map every guideline explicitly:

Systems Thinking — We don't treat advising as a course-picker problem. We model the full system: degree requirements → visa rules → aid rules → work constraints → career outcomes. A "good" course fails the student if it breaks any layer.
Ethical Decision-Making — The AI never presents itself as authoritative. Every output ends with "Confirm with your advisor and DegreeWorks before registering." We never store student data beyond the session.
Equity & Inclusion — The compliance guardrail exists because the highest-stakes advising mistakes fall hardest on international, low-income, and working students. We explicitly design for the students human advising fails most often.
Engage Communities Meaningfully — Our team is three CUNY students from BMCC and Medgar Evers. We are the user. The work-schedule filter, DegreeWorks language, and TAP-allowable warning all come from lived experience.
Interdisciplinarity — The solution combines education policy (TAP/Pell rules), immigration law (F-1 credit minimums), software engineering, and UX.
Transparency & Accountability — Every recommendation shows (a) the degree requirement it satisfies, (b) the compliance checks it passed, and (c) a plain-language rationale. No black-box answers.
Continuous Learning — The JSON catalog and guardrail rules are modular; as CUNY policies or catalogs change, we update the data layer without retraining anything.
PIT Technological Intuition — We deliberately chose not to use AI for the compliance layer. Rules that determine whether someone keeps their visa or their Pell grant must be deterministic and auditable, not probabilistic. AI handles the personalization; code handles the protection.
Champion the Public Interest — CUNY serves ~225,000 students, the majority first-generation, working, or low-income. Scalable compliance-aware advising is a direct public-interest good.

User Journeys (your three — refined to show the compliance angle)

An accepted F-1 international CUNY student needs compliance-aware course recommendations that maintain a 12+ credit load and limit online sections in order to register for fall without risking their visa.
A transfer CUNY student on TAP needs to know which transferred credits count toward their degree and which electives are TAP-allowable in order to continue their education without losing funding.
A high school student entering BMCC Engineering Science needs a semester-by-semester plan aligned with their career interest (e.g., robotics) in order to register confidently for their first term.

MVP Feature List — Restructured
Function 1: Profile Intake

F1.1 — Academic profile: school, major, year, completed courses (multi-select + "ENG101" text input for edge cases)
F1.2 — Compliance profile: visa status, financial aid type, work schedule + unavailable times
F1.3 — Career goal (free text, ~1–2 sentences)

Function 2: Compliance Guardrail (deterministic, non-AI)

F2.1 — Visa rule: if international, enforce ≥12 credits and ≤1 online course; flag violations before plan is shown
F2.2 — TAP rule: if TAP recipient, flag any recommended elective not in a curated "allowable electives" list for that major
F2.3 — Pell rule: show prorated award amount based on planned credits (12=100%, 9=75%, 6=50%)
F2.4 — Schedule rule: if full-time worker, filter to async / evening / weekend sections

Function 3: Agentic Recommendation Engine (Claude + tool use)

F3.1 — Tool: get_remaining_requirements(major, completed_courses) returns what's still needed
F3.2 — Tool: get_eligible_courses(major, completed_courses) returns prerequisite-cleared courses
F3.3 — Tool: check_compliance(plan, profile) returns pass/fail + reasons
F3.4 — LLM composes ranked recommendations with career-alignment rationale, then validates through check_compliance before returning

Function 4: Output & Chat

F4.1 — Plan display: 3–5 recommended courses, each with requirement cited, compliance status, and "why this fits your goal"
F4.2 — Always-visible advisor disclaimer
F4.3 — Follow-up chatbot scoped to the generated plan ("why not MAT 301?", "what if I switch majors?")

P1 (only if ahead): DegreeWorks PDF upload parsing, multi-semester planning, second major (Medgar Evers CS)
P2 (skip): Account save, advisor sharing, additional schools
Updated Challenges Section

Video recording logistics — solved by recording separate screen-capture segments with one narrator, mixed in post
Learning + building in 24h — mitigated by splitting roles early: D owns agent/backend, A owns frontend/site, J owns PRD/slides/video
Multi-college course data breadth — scoped to BMCC Engineering Science for demo; architecture is generalizable
Making compliance logic trustworthy — solved by implementing it as deterministic Python, not as LLM behavior, so it can be audited

Updated Timeline (realistic for tonight + tomorrow)
Tonight (Fri) by 7pm: PRD signed off, website skeleton live, slide shell up, GitHub repo created, course JSON for 1 major drafted
Tonight by 11pm (optional push): Working Claude API "hello world" hitting the JSON; intake form collecting data
Saturday 8am–12pm: Guardrail logic coded + tested; agent recommendation loop working end-to-end (ugly but functional)
Saturday 12–2pm: Polish UI, add chat, finalize slides
Saturday 2–4pm: Record video (under 5 min), final submissions
Saturday 4–5pm: Upload everything to Bemyapp, buffer for issues