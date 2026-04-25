import { useState, useEffect } from "react";
import type { StudentProfile, Program, EnrollmentStatus, FinancialAidType, StudentType } from "../types";
import { getPrograms } from "../api/client";

interface Props {
  onSubmit: (profile: StudentProfile) => void;
  loading: boolean;
}

const STEPS = ["Academic", "Compliance", "Career Goal"];

export default function ProfileForm({ onSubmit, loading }: Props) {
  const [step, setStep] = useState(0);
  const [programs, setPrograms] = useState<Program[]>([]);
  const [profile, setProfile] = useState<StudentProfile>({
    school: "BMCC",
    enrollment_status: "full-time",
    student_type: "domestic",
    financial_aid_type: null,
  });

  useEffect(() => {
    getPrograms().then(setPrograms).catch(() => {});
  }, []);

  function set<K extends keyof StudentProfile>(key: K, value: StudentProfile[K]) {
    setProfile((p) => ({ ...p, [key]: value }));
  }

  function next() { setStep((s) => s + 1); }
  function back() { setStep((s) => s - 1); }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(profile);
  }

  return (
    <div className="card">
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
            <p className="subtitle">Tell us about your current academic standing.</p>

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
              <select
                value={profile.program_code ?? ""}
                onChange={(e) => set("program_code", e.target.value)}
              >
                <option value="">— Select your program —</option>
                {programs.map((p) => (
                  <option key={p.program_code} value={p.program_code}>
                    {p.name} ({p.degree ?? p.program_code})
                  </option>
                ))}
              </select>
            </label>

            <div className="row">
              <label>
                Target Graduation Semester
                <select
                  value={profile.graduation_semester ?? ""}
                  onChange={(e) => set("graduation_semester", e.target.value)}
                >
                  <option value="">— Semester —</option>
                  <option>Spring</option>
                  <option>Summer</option>
                  <option>Fall</option>
                </select>
              </label>
              <label>
                Graduation Year
                <input
                  type="number"
                  min={2025}
                  max={2035}
                  value={profile.graduation_year ?? ""}
                  onChange={(e) => set("graduation_year", Number(e.target.value))}
                  placeholder="2027"
                />
              </label>
            </div>

            <div className="form-actions">
              <button type="button" className="btn-primary" onClick={next} disabled={!profile.program_code}>
                Next →
              </button>
            </div>
          </div>
        )}

        {/* ── Step 1: Compliance ── */}
        {step === 1 && (
          <div className="form-section">
            <h2>Compliance Profile</h2>
            <p className="subtitle">
              This information powers the compliance guardrail — it protects your visa
              status and financial aid before any course is recommended.
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
              Your goal shapes every course recommendation — the advisor will explain
              exactly how each course moves you toward it.
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
