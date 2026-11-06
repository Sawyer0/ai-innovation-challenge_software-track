import ProfileForm from "../components/ProfileForm";
import TranscriptUpload from "../components/TranscriptUpload";
import type { SessionRunner } from "../api/client";
import type { StudentProfile, TranscriptParseResult, TranscriptProfileHints, ParsedCourse } from "../types";

interface Props {
  withSession: SessionRunner;
  onSubmit: (profile: StudentProfile) => void;
  loading: boolean;
  prefill?: TranscriptProfileHints;
  parsedCourses?: ParsedCourse[];
  onParsed: (result: TranscriptParseResult) => void;
}

export default function Intake({ withSession, onSubmit, loading, prefill, parsedCourses, onParsed }: Props) {
  return (
    <div className="intake-layout">
      <div className="intake-header">
        <h1 className="intake-title">Project DJA</h1>
        <p className="intake-subtitle">
          Compliance-aware AI advising for CUNY students — protecting your visa
          status, financial aid, and graduation timeline before every recommendation.
        </p>
      </div>

      <TranscriptUpload withSession={withSession} onParsed={onParsed} />

      <ProfileForm
        onSubmit={onSubmit}
        loading={loading}
        prefill={prefill}
        parsedCourses={parsedCourses}
      />
    </div>
  );
}
