import { useState, useEffect } from "react";
import type {
  StudentProfile,
  Program,
  EnrollmentStatus,
  FinancialAidType,
  StudentType,
  TranscriptProfileHints,
  ParsedCourse,
} from "../types";
import { getPrograms } from "../api/client";
import { BMCC_PROGRAMS } from "../data/bmccPrograms";
import ProgramSearch from "./ProgramSearch";

interface Props {
  onSubmit: (profile: StudentProfile) => void;
  loading: boolean;
  prefill?: TranscriptProfileHints;
  parsedCourses?: ParsedCourse[];
}

const STEPS = ["Academic", "Compliance", "Career Goal"];
const CURRENT_YEAR = new Date().getFullYear();
const MIN_GRAD_YEAR = CURRENT_YEAR;
const MAX_GRAD_YEAR = CURRENT_YEAR + 10;

export default function ProfileForm({ onSubmit, loading, prefill, parsedCourses }: Props) {
  const [step, setStep] = useState(0);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [showAllCourses, setShowAllCourses] = useState(false);
  const [gradYearError, setGradYearError] = useState("");
  const [profile, setProfile] = useState<StudentProfile>({
    school: prefill?.school ?? "BMCC",
    program_code: prefill?.program_code ?? undefined,
    enrollment_status: "full-time",
    student_type: (prefill?.student_type as StudentType) ?? "domestic",
    financial_aid_type: null,
  });

  // Re-apply prefill if a new transcript is uploaded after mount
  useEffect(() => {
    if (!prefill) return;
    setProfile((p) => ({
      ...p,
      school: prefill.school ?? p.school,
      program_code: prefill.program_code ?? p.program_code,
      student_type: (prefill.student_type as StudentType) ?? p.student_type,
    }));
  }, [prefill]);

  useEffect(() => {
    getPrograms()
      .then((data) => setPrograms(data.length > 0 ? data : BMCC_PROGRAMS))
      .catch(() => setPrograms(BMCC_PROGRAMS));
  }, []);

  function set<K extends keyof StudentProfile>(key: K, value: StudentProfile[K]) {
    setProfile((p) => ({ ...p, [key]: value }));
  }

  function handleGradYear(raw: string) {
    if (raw === "") {
      set("graduation_year", undefined);
      setGradYearError("");
      return;
    }
    const yr = parseInt(raw, 10);
    if (isNaN(yr)) return;
    if (yr < MIN_GRAD_YEAR) {
      setGradYearError(`Graduation year cannot be in the past (min ${MIN_GRAD_YEAR}).`);
    } else if (yr > MAX_GRAD_YEAR) {
      setGradYearError(`Graduation year seems too far out (max ${MAX_GRAD_YEAR}).`);
    } else {
      setGradYearError("");
    }
    set("graduation_year", yr);
  }

  const step0Valid =
    !!profile.program_code &&
    !!profile.graduation_semester &&
    !!profile.graduation_year &&
    !gradYearError;

  function next() { setStep((s) => s + 1); }
  function back() { setStep((s) => s - 1); }

  function handleSubmit(e: React.SyntheticEvent) {
    e.preventDefault();
    onSubmit(profile);
  }

  const hasPrefill = prefill && (prefill.school || prefill.program_code || prefill.student_type);
  const selectedProgram = programs.find((p) => p.program_code === profile.program_code);

  return (
    <div className="card">
      {/* Prefill notice */}
      {hasPrefill && (
        <div className="prefill-notice">
          <span className="prefill-notice__icon">✦</span>
          <div>
            <strong>Pre-filled from your transcript</strong>
            <p>
              We've filled in what we could read. Review each field below — you can
              change anything before submitting.
            </p>
          </div>
        </div>
      )}

      {/* Step indicator */}
      <div className="steps">
        {STEPS.map((label, i) => (
          <div key={label} className={`step ${i === step ? "active" : i < step ? "done" : ""}`}>
            <span className="step-num">{i < step ? "✓" : i + 1}</span>
            <span className="step-label">{label}</span>
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        {/* ── Step 0: Academic ── */}
        {step === 0 && (
          <div className="form-section">
            <h2>Academic Profile</h2>
            <p className="subtitle">Confirm your academic information — edit anything that looks wrong.</p>

            <label>
              School
              <input
                type="text"
                value={profile.school ?? ""}
                onChange={(e) => set("school", e.target.value)}
                placeholder="e.g. BMCC, City College, Hunter"
              />
            </label>

            <label>
              Program / Major
              <ProgramSearch
                programs={programs}
                value={profile.program_code ?? ""}
                onChange={(code) => set("program_code", code)}
              />
              {prefill?.program_name && !profile.program_code && (
                <span className="field-hint">
                  Transcript shows: <em>{prefill.program_name}{prefill.degree ? ` (${prefill.degree})` : ""}</em> — select the matching program above
                </span>
              )}
            </label>

            {/* Parsed courses summary */}
            {parsedCourses && parsedCourses.length > 0 && (
              <div className="parsed-courses-inline">
                <div className="parsed-courses-inline__header">
                  <span className="parsed-courses-inline__count">
                    {parsedCourses.filter(c => c.status === "completed").length} completed
                    · {parsedCourses.filter(c => c.status === "in-progress").length} in progress
                  </span>
                  {prefill?.total_credits_earned != null && (
                    <span className="parsed-courses-inline__credits">
                      {prefill.total_credits_earned} cr earned
                      {prefill.total_credits_needed != null && ` / ${prefill.total_credits_needed} needed`}
                    </span>
                  )}
                  {prefill?.cumulative_gpa != null && (
                    <span className="parsed-courses-inline__gpa">
                      GPA {prefill.cumulative_gpa.toFixed(2)}
                    </span>
                  )}
                </div>
                {/* column headers */}
                <div className="parsed-item parsed-item--header">
                  <span className="parsed-code">Code</span>
                  <span className="parsed-name">Title</span>
                  <span className="parsed-cr">Cr</span>
                  <span className="parsed-grade">Grade</span>
                </div>
                <div className="parsed-list parsed-list--compact">
                  {(showAllCourses ? parsedCourses : parsedCourses.slice(0, 6)).map((c) => (
                    <div
                      key={`${c.course_code}-${c.semester_taken}`}
                      className={`parsed-item ${c.status === "withdrawn" ? "parsed-item--withdrawn" : ""}`}
                    >
                      <span className="parsed-code">{c.course_code}</span>
                      <span className="parsed-name">
                        {c.course_title}
                        {c.semester_taken && <span className="parsed-term">{c.semester_taken}</span>}
                      </span>
                      <span className="parsed-cr">{c.credits > 0 ? c.credits : "—"}</span>
                      <span className={`parsed-grade parsed-grade--${c.status}`}>
                        {c.status === "withdrawn" ? "W"
                          : c.status === "in-progress" ? "IP"
                          : c.grade ?? "—"}
                      </span>
                    </div>
                  ))}
                  {parsedCourses.length > 6 && (
                    <button
                      type="button"
                      className="parsed-toggle"
                      onClick={() => setShowAllCourses((v) => !v)}
                    >
                      {showAllCourses
                        ? "Show less ▲"
                        : `+ ${parsedCourses.length - 6} more courses ▼`}
                    </button>
                  )}
                </div>
              </div>
            )}

            <div className="row">
              <label>
                Target Graduation Semester <span className="field-required">*</span>
                <select
                  value={profile.graduation_semester ?? ""}
                  onChange={(e) => set("graduation_semester", e.target.value)}
                  className={!profile.graduation_semester ? "input-empty" : ""}
                >
                  <option value="">— Select semester —</option>
                  <option>Spring</option>
                  <option>Summer</option>
                  <option>Fall</option>
                </select>
                {!profile.graduation_semester && (
                  <span className="field-hint field-hint--required">Required</span>
                )}
              </label>
              <label>
                Graduation Year <span className="field-required">*</span>
                <input
                  type="number"
                  min={MIN_GRAD_YEAR}
                  max={MAX_GRAD_YEAR}
                  value={profile.graduation_year ?? ""}
                  onChange={(e) => handleGradYear(e.target.value)}
                  placeholder={String(CURRENT_YEAR + 2)}
                  className={gradYearError ? "input-error" : ""}
                />
                {gradYearError
                  ? <span className="field-hint field-hint--error">{gradYearError}</span>
                  : !profile.graduation_year
                    ? <span className="field-hint field-hint--required">Required</span>
                    : null}
              </label>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="btn-primary"
                onClick={next}
                disabled={!step0Valid}
              >
                {!profile.program_code
                  ? "Select a program to continue"
                  : !profile.graduation_semester || !profile.graduation_year
                    ? "Set graduation target to continue"
                    : `Next → ${selectedProgram ? `(${selectedProgram.name})` : ""}`}
              </button>
            </div>
          </div>
        )}

        {/* ── Step 1: Compliance ── */}
        {step === 1 && (
          <div className="form-section">
            <h2>Compliance Profile</h2>
            <p className="subtitle">
              This powers the compliance guardrail — protecting your visa status
              and financial aid before any course is recommended.
            </p>

            <label>
              Student Type
              <div className="radio-group">
                {(["domestic", "international"] as StudentType[]).map((t) => (
                  <label key={t} className="radio-label">
                    <input
                      type="radio"
                      name="student_type"
                      value={t}
                      checked={profile.student_type === t}
                      onChange={() => set("student_type", t)}
                    />
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                    {t === "international" && (
                      <span className="badge badge-info">F-1 rules apply</span>
                    )}
                    {prefill?.student_type === t && (
                      <span className="badge badge-prefilled">from transcript</span>
                    )}
                  </label>
                ))}
              </div>
            </label>

            <label>
              Enrollment Status
              <select
                value={profile.enrollment_status ?? ""}
                onChange={(e) => set("enrollment_status", e.target.value as EnrollmentStatus)}
              >
                <option value="full-time">Full-time (12–18 credits)</option>
                <option value="half-time">Half-time (6–11 credits)</option>
                <option value="less-than-half-time">Less than half-time (0–5 credits)</option>
              </select>
            </label>

            <label>
              Financial Aid
              <select
                value={profile.financial_aid_type ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  set("financial_aid_type", (v === "" ? null : v) as FinancialAidType);
                }}
              >
                <option value="">None / Not applicable</option>
                <option value="pell">Pell Grant</option>
                <option value="tap">TAP (Tuition Assistance Program)</option>
                <option value="both">Both Pell and TAP</option>
              </select>
            </label>

            {profile.financial_aid_type && (
              <div className="info-box">
                {(profile.financial_aid_type === "pell" || profile.financial_aid_type === "both") && (
                  <p>Pell Grant requires at least <strong>6 credits</strong> (half-time).</p>
                )}
                {(profile.financial_aid_type === "tap" || profile.financial_aid_type === "both") && (
                  <p>TAP requires <strong>full-time enrollment (12+ credits)</strong>.</p>
                )}
              </div>
            )}

            {profile.student_type === "international" && (
              <div className="info-box info-box--warning">
                <p>F-1 visa requires <strong>≥12 credits</strong> and <strong>no more than 1 online/hybrid course</strong> per semester.</p>
              </div>
            )}

            <div className="form-actions">
              <button type="button" className="btn-secondary" onClick={back}>← Back</button>
              <button type="button" className="btn-primary" onClick={next}>Next →</button>
            </div>
          </div>
        )}

        {/* ── Step 2: Career Goal ── */}
        {step === 2 && (
          <div className="form-section">
            <h2>Career Goal</h2>
            <p className="subtitle">
              Your goal shapes every recommendation — the advisor explains exactly
              how each course moves you toward it.
            </p>

            <label>
              What do you want to do after graduating?
              <textarea
                rows={4}
                value={profile.career_goal ?? ""}
                onChange={(e) => set("career_goal", e.target.value)}
                placeholder="e.g. I want to work as a software engineer at a tech company, focusing on machine learning and data pipelines."
              />
            </label>

            <div className="form-actions">
              <button type="button" className="btn-secondary" onClick={back}>← Back</button>
              <button
                type="submit"
                className="btn-primary"
                disabled={loading || !profile.career_goal?.trim()}
              >
                {loading ? "Getting your plan…" : "Get My Plan →"}
              </button>
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
