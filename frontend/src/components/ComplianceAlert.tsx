import type { ComplianceViolation } from "../types";

interface Props {
  violation: ComplianceViolation;
  onDismiss: () => void;
}

const TITLES: Record<string, string> = {
  visa_compliance_violation: "F-1 Visa Compliance Issue",
  compliance_violation: "Financial Aid Compliance Issue",
};

export default function ComplianceAlert({ violation, onDismiss }: Props) {
  return (
    <div className="compliance-alert">
      <div className="compliance-alert__header">
        <span className="compliance-alert__icon">🚫</span>
        <h3>{TITLES[violation.type] ?? "Compliance Issue"}</h3>
      </div>
      <p className="compliance-alert__message">{violation.message}</p>
      <div className="compliance-alert__meta">
        <span>Planned credits: <strong>{violation.planned_credits}</strong></span>
        {violation.aid_type && (
          <span>Aid type: <strong>{violation.aid_type.toUpperCase()}</strong></span>
        )}
        {violation.student_type && (
          <span>Student type: <strong>{violation.student_type}</strong></span>
        )}
      </div>
      <p className="compliance-alert__note">
        Please adjust your planned courses to meet the requirements, then try again.
        Speak with your advisor or the International Student Office if you need an exception.
      </p>
      <button className="btn-secondary" onClick={onDismiss}>← Adjust My Profile</button>
    </div>
  );
}
