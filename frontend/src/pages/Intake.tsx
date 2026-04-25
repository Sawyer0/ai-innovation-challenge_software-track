import ProfileForm from "../components/ProfileForm";
import TranscriptUpload from "../components/TranscriptUpload";
import type { StudentProfile, TranscriptParseResult, TranscriptProfileHints, ParsedCourse } from "../types";

interface Props {
  sessionId: string;
  onSubmit: (profile: StudentProfile) => void;
  loading: boolean;
  prefill?: TranscriptProfileHints;
  parsedCourses?: ParsedCourse[];
  onParsed: (result: TranscriptParseResult) => void;
}

export default function Intake({ sessionId, onSubmit, loading, prefill, parsedCourses, onParsed }: Props) {
  return (
    <div className="intake-layout">
      <div className="intake-header">
        <h1 className="intake-title">Project DJA</h1>
        <p className="intake-subtitle">
          Compliance-aware AI advising for CUNY students — protecting your visa
          status, financial aid, and graduation timeline before every recommendation.
        </p>
      </div>

      <TranscriptUpload sessionId={sessionId} onParsed={onParsed} />

      <ProfileForm
        onSubmit={onSubmit}
        loading={loading}
        prefill={prefill}
        parsedCourses={parsedCourses}
      />
    </div>
  );
}
