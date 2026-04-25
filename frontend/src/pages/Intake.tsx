import { useState } from "react";
import ProfileForm from "../components/ProfileForm";
import TranscriptUpload from "../components/TranscriptUpload";
import type { StudentProfile, ParsedCourse } from "../types";

interface Props {
  sessionId: string;
  onSubmit: (profile: StudentProfile) => void;
  loading: boolean;
}

export default function Intake({ sessionId, onSubmit, loading }: Props) {
  const [parsedCourses, setParsedCourses] = useState<ParsedCourse[]>([]);

  function handleParsed(courses: ParsedCourse[]) {
    setParsedCourses(courses);
  }

  return (
    <div className="intake-layout">
      <div className="intake-header">
        <h1 className="intake-title">Project DJA</h1>
        <p className="intake-subtitle">
          Compliance-aware AI advising for CUNY students — protecting your visa
          status, financial aid, and graduation timeline before every recommendation.
        </p>
      </div>

      <TranscriptUpload sessionId={sessionId} onParsed={handleParsed} />

      {parsedCourses.length > 0 && (
        <div className="parsed-courses-preview card">
          <h4>Courses extracted from transcript ({parsedCourses.length})</h4>
          <div className="parsed-list">
            {parsedCourses.map((c) => (
              <div key={c.course_code} className="parsed-item">
                <span className="parsed-code">{c.course_code}</span>
                <span className="parsed-name">{c.course_title}</span>
                <span className="parsed-grade">{c.grade ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <ProfileForm onSubmit={onSubmit} loading={loading} />
    </div>
  );
}
