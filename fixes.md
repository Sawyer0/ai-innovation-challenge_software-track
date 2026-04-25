Priority Fixes (in order for the hackathon)
Here's what I'd tackle, roughly sorted by impact vs. effort:

#	Fix	Impact	Effort
1	Switch AI from Gemini to Claude API with tool use	Critical (matches PRD)	Medium
2	Wire check_financial_aid_compliance() into the router — hard block, not just a warning string	High	Low
3	Add visa/F-1 guardrail: if student_type == "international", block plans < 12 credits	High	Low
4	Add career_goal to StudentProfile schema and prompt	High	Low
5	Return structured JSON plan (list of courses with rationale + compliance status) instead of freeform string	High	Medium
6	Add Pell proration display	Medium	Low
7	Build the HTML/CSS/JS frontend	Critical for demo	High
8	TAP allowable electives list	Medium	Medium
My recommendation: Items 1–5 are the core integrity gap between what's coded and what's described. Items 1 and 5 together transform this from "chatbot that mentions compliance" into "agentic advisor with compliance guardrails."

Want me to start implementing? I'd suggest beginning with switching to the Claude API with proper tool use (item 1) since it's the centerpiece of the PRD and will pull items 3–5 along with it naturally. Then we wire the hard guardrails. Then the frontend.