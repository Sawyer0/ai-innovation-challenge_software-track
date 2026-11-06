import type {
  SessionResponse,
  StudentProfile,
  AdvisementResponse,
  ComplianceViolation,
  Program,
  TranscriptParseResult,
} from "../types";
import { refreshUsage, updateUsageFromHeaders } from "./usage";

// Production builds call the API on the same origin (Vercel routes /api/* to the
// backend function). In dev the backend runs on :8000 unless VITE_API_URL says otherwise.
const BASE_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : "");

// FastAPI serves its docs at /docs locally and under /api/docs in production.
export const API_DOCS_URL = import.meta.env.DEV
  ? `${BASE_URL}/docs`
  : `${BASE_URL}/api/docs`;

// Vercel rejects request bodies over 4.5 MB before they reach the API.
export const MAX_UPLOAD_BYTES = 4.5 * 1024 * 1024;

// ── helpers ───────────────────────────────────────────────────────────────────

/** An HTTP error whose message is safe to show; retryAfter is in seconds when known. */
export class ApiError extends Error {
  status: number;
  retryAfter: number | null;
  constructor(message: string, status: number, retryAfter: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

// Used when the response has no JSON detail (e.g. a platform error page).
function fallbackMessage(status: number): string {
  if (status === 413) return "This file is too large to upload (4.5 MB max). Try a smaller PDF or a screenshot.";
  if (status === 429) return "Too many requests right now. Please wait a moment and try again.";
  if (status === 502 || status === 503) return "The demo is busy right now. Please try again in a moment.";
  if (status === 504) return "The server took too long to respond. Please try again in a moment.";
  return `Request failed (${status}).`;
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Couldn't reach the server. Check your connection and try again.", 0, null);
  }
}

async function toError(res: Response): Promise<Error> {
  const body = await res.json().catch(() => ({}));
  // Surface compliance violations as a typed error
  if (res.status === 422 && body?.detail?.type) {
    return new ComplianceError(body.detail as ComplianceViolation);
  }
  const retry = Number(res.headers.get("Retry-After"));
  const message =
    typeof body?.detail === "string" ? body.detail : fallbackMessage(res.status);
  return new ApiError(message, res.status, Number.isFinite(retry) && retry > 0 ? retry : null);
}

/** After an AI call, update the quota chip from its headers (or ask the API). */
function trackUsage(res: Response) {
  if (!updateUsageFromHeaders(res.headers)) void refreshUsage(BASE_URL);
}

async function request<T>(path: string, init?: RequestInit, ai = false): Promise<T> {
  const res = await send(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (ai) trackUsage(res);
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

export function loadUsage(): Promise<void> {
  return refreshUsage(BASE_URL);
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

  const res = await send(`/api/session/${sessionId}/transcript`, {
    method: "POST",
    body: form,
  });
  trackUsage(res);
  if (!res.ok) throw await toError(res);
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
    },
    true
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
