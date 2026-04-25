import { useEffect, useState } from "react";
import Intake from "./pages/Intake";
import Results from "./pages/Results";
import ComplianceAlert from "./components/ComplianceAlert";
import { createSession, setProfile, getAdvisement, ComplianceError } from "./api/client";
import type { AdvisementResponse, ComplianceViolation, StudentProfile, TranscriptProfileHints, ParsedCourse } from "./types";

type AppState = "intake" | "loading" | "results";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [appState, setAppState] = useState<AppState>("intake");
  const [result, setResult] = useState<AdvisementResponse | null>(null);
  const [violation, setViolation] = useState<ComplianceViolation | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Lifted here so transcript data survives compliance errors
  const [prefill, setPrefill] = useState<TranscriptProfileHints | undefined>();
  const [parsedCourses, setParsedCourses] = useState<ParsedCourse[]>([]);

  useEffect(() => {
    createSession()
      .then((s) => setSessionId(s.session_id))
      .catch(() =>
        setError("Could not connect to the server. Make sure the backend is running.")
      );
  }, []);

  async function handleProfileSubmit(profile: StudentProfile) {
    if (!sessionId) return;
    setAppState("loading");
    setError(null);
    setViolation(null);

    try {
      await setProfile(sessionId, profile);
      const advisement = await getAdvisement(
        sessionId,
        "What should I take next semester?"
      );
      setResult(advisement);
      setAppState("results");
    } catch (e) {
      if (e instanceof ComplianceError) {
        setViolation(e.violation);
        setAppState("intake"); // stay on intake so the form is still there
      } else {
        setError(e instanceof Error ? e.message : "Something went wrong.");
        setAppState("intake");
      }
    }
  }

  function handleStartOver() {
    setResult(null);
    setViolation(null);
    setError(null);
    setPrefill(undefined);
    setParsedCourses([]);
    setAppState("intake");
    createSession()
      .then((s) => setSessionId(s.session_id))
      .catch(() => {});
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-header__brand">
            <span className="app-header__logo">DJA</span>
            <div>
              <div className="app-header__name">Project DJA</div>
              <div className="app-header__tagline">
                Compliance-Aware AI Advising for CUNY
              </div>
            </div>
          </div>
          <nav className="app-header__nav">
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
            >
              API Docs
            </a>
          </nav>
        </div>
      </header>

      <main className="app-main">
        {error && (
          <div className="global-error">
            <strong>Error:</strong> {error}
          </div>
        )}

        {(appState === "intake" || appState === "loading") && sessionId && (
          <>
            {violation && (
              <ComplianceAlert
                violation={violation}
                onDismiss={() => setViolation(null)}
              />
            )}
            <Intake
              sessionId={sessionId}
              onSubmit={handleProfileSubmit}
              loading={appState === "loading"}
              prefill={prefill}
              parsedCourses={parsedCourses}
              onParsed={(result) => {
                setPrefill(result.profile);
                setParsedCourses(result.courses);
              }}
            />
          </>
        )}

        {appState === "results" && result && (
          <Results result={result} onStartOver={handleStartOver} />
        )}
      </main>

      <footer className="app-footer">
        <p>
          Project DJA · Built for the CUNY AI Innovation Challenge ·{" "}
          <em>Not a substitute for official academic advising.</em>
        </p>
      </footer>
    </div>
  );
}
