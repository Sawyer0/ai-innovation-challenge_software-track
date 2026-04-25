// ── Session ──────────────────────────────────────────────────────────────────

export interface SessionResponse {
  session_id: string;
  created_at: string;
  last_activity: string;
}

// ── Profile ───────────────────────────────────────────────────────────────────

export type StudentType = "domestic" | "international";
export type FinancialAidType = "pell" | "tap" | "both" | null;
export type EnrollmentStatus = "full-time" | "half-time" | "less-than-half-time";

export interface StudentProfile {
  school?: string;
  program_code?: string;
  enrollment_status?: EnrollmentStatus;
  student_type?: StudentType;
  financial_aid_type?: FinancialAidType;
  graduation_year?: number;
  graduation_semester?: string;
  career_goal?: string;
}

// ── Transcript ────────────────────────────────────────────────────────────────

export interface ParsedCourse {
  course_code: string;
  course_title: string;
  semester_taken: string | null;
  credits: number;
  grade: string | null;
  status: "completed" | "in-progress" | "withdrawn";
}

export interface TranscriptProfileHints {
  school?: string | null;
  program_code?: string | null;
  program_name?: string | null;
  degree?: string | null;
  student_type?: "domestic" | "international" | null;
  cumulative_gpa?: number | null;
  total_credits_earned?: number | null;
  total_credits_needed?: number | null;
}

export interface TranscriptParseResult {
  profile: TranscriptProfileHints;
  courses: ParsedCourse[];
}

// ── Advisement ────────────────────────────────────────────────────────────────

export type ComplianceStatus = "compliant" | "warning" | "blocked";

export interface RecommendedCourse {
  course_code: string;
  course_title: string;
  credits: number;
  requirement_satisfied: string;
  compliance_status: ComplianceStatus;
  compliance_note: string | null;
  career_rationale: string;
  why_now: string;
}

export interface PellProration {
  planned_credits: number;
  percentage: number;
  percentage_display: string;
  enrollment_tier: string;
  note: string;
}

export interface AdvisementResponse {
  next_semester: string;
  total_planned_credits: number;
  compliance_cleared: boolean;
  advisor_message: string;
  recommended_courses: RecommendedCourse[];
  pell_proration: PellProration | null;
  disclaimer: string;
}

// ── Compliance violation (422) ────────────────────────────────────────────────

export type ComplianceViolationType =
  | "compliance_violation"
  | "visa_compliance_violation";

export interface ComplianceViolation {
  type: ComplianceViolationType;
  aid_type?: string;
  student_type?: string;
  planned_credits: number;
  message: string;
}

// ── Programs ──────────────────────────────────────────────────────────────────

export interface Program {
  id?: number;
  program_code: string;
  name: string;
  degree?: string | null;
  department?: string | null;
}
