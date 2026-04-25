import { useEffect, useState, useCallback } from "react";
import Intake from "./pages/Intake";
import Results from "./pages/Results";
import ComplianceAlert from "./components/ComplianceAlert";
import { createSession, setProfile, getAdvisement, ComplianceError } from "./api/client";
import type { AdvisementResponse, ComplianceViolation, StudentProfile, TranscriptProfileHints, ParsedCourse } from "./types";

type AppState = "intake" | "loading" | "results";

// Persists a value in sessionStorage so refreshes don't wipe it.
// sessionStorage is tab-scoped and clears when the tab is closed.
function useSessionStorage<T>(key: string, initial: T): [T, (val: T) => void] {
  const [value, setInner] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  const setValue = useCallback((val: T) => {
    setInner(val);
    try {
      if (val === undefined || val === null) {
        sessionStorage.removeItem(key);
      } else {
        sessionStorage.setItem(key, JSON.stringify(val));
      }
    } catch { /* quota exceeded — degrade gracefully */ }
  }, [key]);

  return [value, setValue];
}

export default function App() {
  const [sessionId, setSessionId] = useSessionStorage<string | null>("dja_session_id", null);
  const [prefill, setPrefill] = useSessionStorage<TranscriptProfileHints | undefined>("dja_prefill", undefined);
  const [parsedCourses, setParsedCourses] = useSessionStorage<ParsedCourse[]>("dja_courses", []);

  const [appState, setAppState] = useState<AppState>("intake");
  const [result, setResult] = useState<AdvisementResponse | null>(null);
  const [violation, setViolation] = useState<ComplianceViolation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only create a new session if we don't have a cached one
    if (sessionId) return;
    createSession()
      .then((s) => setSessionId(s.session_id))
      .catch(() =>
        setError("Could not connect to the server. Make sure the backend is running.")
      );
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        setAppState("intake");
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        // Session expired (server restarted) — create a fresh one
        if (msg.includes("404") || msg.includes("Session not found") || msg.includes("ERR_FAILED")) {
          try {
            const fresh = await createSession();
            setSessionId(fresh.session_id);
            setError("Your session expired — please submit again.");
          } catch {
            setError("Could not connect to the server. Make sure the backend is running.");
          }
        } else {
          setError(msg);
        }
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
