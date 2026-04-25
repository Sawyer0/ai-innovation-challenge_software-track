import CourseCard from "../components/CourseCard";
import PellProration from "../components/PellProration";
import type { AdvisementResponse } from "../types";

interface Props {
  result: AdvisementResponse;
  onStartOver: () => void;
}

export default function Results({ result, onStartOver }: Props) {
  const warnings = result.recommended_courses.filter(
    (c) => c.compliance_status !== "compliant"
  );

  return (
    <div className="results-layout">
      {/* Header */}
      <div className="results-header">
        <div>
          <h1>Your Plan for {result.next_semester}</h1>
          <p className="results-meta">
            {result.total_planned_credits} planned credits ·{" "}
            <span className="compliance-cleared">✓ Compliance cleared</span>
          </p>
        </div>
        <button className="btn-secondary" onClick={onStartOver}>
          ← Start Over
        </button>
      </div>

      {/* Advisor message */}
      <div className="advisor-message card">
        <span className="advisor-avatar">🎓</span>
        <p>{result.advisor_message}</p>
      </div>

      {/* Pell proration banner */}
      {result.pell_proration && <PellProration data={result.pell_proration} />}

      {/* TAP summary warning */}
      {warnings.length > 0 && (
        <div className="tap-summary-warning">
          <strong>⚠ {warnings.length} course{warnings.length > 1 ? "s" : ""} flagged for TAP review</strong>
          <p>
            The courses marked below may not count toward your TAP-eligible credits.
            Confirm with your financial aid advisor before registering.
          </p>
        </div>
      )}

      {/* Course cards */}
      <div className="course-list">
        {result.recommended_courses.map((course, i) => (
          <CourseCard key={course.course_code} course={course} index={i} />
        ))}
      </div>

      {/* Disclaimer */}
      <div className="disclaimer">
        <span>ℹ</span>
        <p>{result.disclaimer}</p>
      </div>
    </div>
  );
}
