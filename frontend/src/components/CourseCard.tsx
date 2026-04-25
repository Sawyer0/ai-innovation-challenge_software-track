import type { RecommendedCourse } from "../types";

interface Props {
  course: RecommendedCourse;
  index: number;
}

const STATUS_CONFIG = {
  compliant: { label: "Compliant", className: "badge-compliant", icon: "✓" },
  warning:   { label: "Review Required", className: "badge-warning", icon: "⚠" },
  blocked:   { label: "Blocked", className: "badge-blocked", icon: "✗" },
};

export default function CourseCard({ course, index }: Props) {
  const status = STATUS_CONFIG[course.compliance_status] ?? STATUS_CONFIG.compliant;

  return (
    <div className={`course-card course-card--${course.compliance_status}`}>
      <div className="course-card__header">
        <div className="course-card__title-group">
          <span className="course-card__index">{index + 1}</span>
          <div>
            <h3 className="course-card__code">{course.course_code}</h3>
            <p className="course-card__title">{course.course_title}</p>
          </div>
        </div>
        <div className="course-card__meta">
          <span className="course-card__credits">{course.credits} cr</span>
          <span className={`badge ${status.className}`}>
            {status.icon} {status.label}
          </span>
        </div>
      </div>

      {course.compliance_note && (
        <div className="course-card__compliance-note">
          <strong>⚠ TAP Note:</strong> {course.compliance_note}
        </div>
      )}

      <div className="course-card__body">
        <div className="course-card__row">
          <span className="course-card__row-label">Satisfies</span>
          <span>{course.requirement_satisfied}</span>
        </div>
        <div className="course-card__row">
          <span className="course-card__row-label">Career fit</span>
          <span>{course.career_rationale}</span>
        </div>
        <div className="course-card__row">
          <span className="course-card__row-label">Why now</span>
          <span>{course.why_now}</span>
        </div>
      </div>
    </div>
  );
}
