import type {
  SessionResponse,
  StudentProfile,
  AdvisementResponse,
  ComplianceViolation,
  Program,
  TranscriptParseResult,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ── helpers ───────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // Surface compliance violations as a typed error
    if (res.status === 422 && body?.detail?.type) {
      const err = new ComplianceError(body.detail as ComplianceViolation);
      throw err;
    }
    throw new Error(body?.detail ?? `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ── Typed compliance error ────────────────────────────────────────────────────

export class ComplianceError extends Error {
  violation: ComplianceViolation;
  constructor(violation: ComplianceViolation) {
    super(violation.message);
    this.name = "ComplianceError";
    this.violation = violation;
  }
}

// ── Session ───────────────────────────────────────────────────────────────────

export async function createSession(): Promise<SessionResponse> {
  return request<SessionResponse>("/api/session/", { method: "POST" });
}

export async function setProfile(
  sessionId: string,
  profile: StudentProfile
): Promise<void> {
  await request(`/api/session/${sessionId}/profile`, {
    method: "POST",
    body: JSON.stringify(profile),
  });
}

export async function saveParsedCourses(
  sessionId: string,
  courses: import("../types").ParsedCourse[]
): Promise<{ saved: number; total: number }> {
  return request(`/api/session/${sessionId}/courses/bulk`, {
    method: "POST",
    body: JSON.stringify(
      courses.map((c) => ({
        course_code: c.course_code,
        course_title: c.course_title,
        semester_taken: c.semester_taken ?? null,
        status: c.status,
        grade: c.grade ?? null,
        credits: c.credits ?? 0,
        source: "transcript",
      }))
    ),
  });
}

// ── Transcript ────────────────────────────────────────────────────────────────

export async function uploadTranscript(
  sessionId: string,
  file: File
): Promise<TranscriptParseResult> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(
    `${BASE_URL}/api/session/${sessionId}/transcript`,
    { method: "POST", body: form }
  );

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? "Transcript upload failed");
  }

  return res.json() as Promise<TranscriptParseResult>;
}

// ── Advisement ────────────────────────────────────────────────────────────────

export async function getAdvisement(
  sessionId: string,
  message: string
): Promise<AdvisementResponse> {
  return request<AdvisementResponse>(
    `/api/session/${sessionId}/advisement`,
    {
      method: "POST",
      body: JSON.stringify({ message }),
    }
  );
}

// ── Programs ──────────────────────────────────────────────────────────────────

export async function getPrograms(): Promise<Program[]> {
  const res = await request<{ programs?: Program[] } | Program[]>(
    "/api/programs"
  );
  // Handle both array and wrapped responses
  return Array.isArray(res) ? res : (res as { programs: Program[] }).programs ?? [];
}
