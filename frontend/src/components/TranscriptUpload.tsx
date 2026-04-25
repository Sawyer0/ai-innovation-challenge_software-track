import { useRef, useState } from "react";
import { uploadTranscript, saveParsedCourses } from "../api/client";
import type { TranscriptParseResult, TranscriptProfileHints, ParsedCourse } from "../types";

interface Props {
  sessionId: string;
  onParsed: (result: TranscriptParseResult) => void;
}

type Status = "idle" | "selected" | "uploading" | "done" | "error";

const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"];
const ALLOWED_EXT = "JPEG, PNG, WebP, GIF, PDF";

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function TranscriptUpload({ sessionId, onParsed }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [dragging, setDragging] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });

  function validateAndStage(files: FileList | File[]) {
    const list = Array.from(files);
    const invalid = list.filter((f) => !ALLOWED.includes(f.type));
    if (invalid.length > 0) {
      setErrorMsg(`Unsupported file type: ${invalid.map((f) => f.name).join(", ")}. Use ${ALLOWED_EXT}.`);
      setStatus("error");
      return;
    }
    setErrorMsg("");
    setSelectedFiles((prev) => {
      // Deduplicate by name+size
      const existing = new Set(prev.map((f) => `${f.name}-${f.size}`));
      const added = list.filter((f) => !existing.has(`${f.name}-${f.size}`));
      return [...prev, ...added];
    });
    setStatus("selected");
  }

  function removeFile(index: number) {
    setSelectedFiles((prev) => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) setStatus("idle");
      return next;
    });
  }

  function reset() {
    setSelectedFiles([]);
    setStatus("idle");
    setErrorMsg("");
    setProgress({ done: 0, total: 0 });
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleUpload() {
    if (selectedFiles.length === 0) return;
    setStatus("uploading");
    setProgress({ done: 0, total: selectedFiles.length });

    const allCourses: ParsedCourse[] = [];
    let mergedProfile: TranscriptProfileHints = {};

    for (let i = 0; i < selectedFiles.length; i++) {
      try {
        const result = await uploadTranscript(sessionId, selectedFiles[i]);
        allCourses.push(...(Array.isArray(result.courses) ? result.courses : []));
        // First file's profile hints win; subsequent files fill in gaps
        mergedProfile = {
          school: mergedProfile.school ?? result.profile.school,
          program_code: mergedProfile.program_code ?? result.profile.program_code,
          program_name: mergedProfile.program_name ?? result.profile.program_name,
          student_type: mergedProfile.student_type ?? result.profile.student_type,
          cumulative_gpa: mergedProfile.cumulative_gpa ?? result.profile.cumulative_gpa,
          total_credits_earned: result.profile.total_credits_earned != null
            ? (mergedProfile.total_credits_earned ?? 0) + result.profile.total_credits_earned
            : mergedProfile.total_credits_earned,
        };
      } catch (e) {
        setErrorMsg(`Failed to parse "${selectedFiles[i].name}": ${e instanceof Error ? e.message : "Unknown error"}`);
        setStatus("error");
        return;
      }
      setProgress({ done: i + 1, total: selectedFiles.length });
    }

    // Deduplicate courses by code+semester
    const seen = new Set<string>();
    const dedupedCourses = allCourses.filter((c) => {
      const key = `${c.course_code}-${c.semester_taken ?? ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Persist courses to the session so the backend knows the student's history
    try {
      await saveParsedCourses(sessionId, dedupedCourses);
    } catch {
      // Non-fatal: the form prefill still works, advisor will just have less context
    }

    setStatus("done");
    onParsed({ profile: mergedProfile, courses: dedupedCourses });
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (status === "uploading") return;
    validateAndStage(e.dataTransfer.files);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length > 0) {
      validateAndStage(e.target.files);
      e.target.value = ""; // allow re-selecting same file
    }
  }

  return (
    <div className="transcript-section">
      <h3>
        Upload Transcript{" "}
        <span className="badge badge-optional">Optional</span>
      </h3>
      <p className="subtitle">
        Upload screenshots or PDFs from CUNYfirst — we'll extract your courses and
        pre-fill your profile. You'll review everything before submitting.
      </p>

      {/* Drop zone — only shown when not in uploading/done states */}
      {status !== "uploading" && status !== "done" && (
        <div
          className={`drop-zone ${dragging ? "dragging" : ""} ${status === "error" ? "error" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
            style={{ display: "none" }}
            onChange={onInputChange}
          />

          {status === "error" ? (
            <>
              <div className="drop-icon">⚠️</div>
              <p className="error-text">{errorMsg}</p>
              <p className="drop-sub">Click to try again</p>
            </>
          ) : (
            <>
              <div className="drop-icon">📄</div>
              <p>{status === "selected" ? "Drop more files, or click to add" : "Drag & drop your transcript here"}</p>
              <p className="drop-sub">
                {status === "selected"
                  ? `${ALLOWED_EXT} accepted · multiple pages supported`
                  : `Click to browse — ${ALLOWED_EXT} accepted`}
              </p>
            </>
          )}
        </div>
      )}

      {/* Uploading state */}
      {status === "uploading" && (
        <div className="drop-zone drop-zone--uploading">
          <div className="spinner" />
          <p>
            Parsing file {progress.done + 1} of {progress.total} with AI…
          </p>
          <p className="drop-sub">This may take a few seconds per file</p>
          {progress.total > 1 && (
            <div className="upload-progress-bar">
              <div
                className="upload-progress-bar__fill"
                style={{ width: `${(progress.done / progress.total) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Done state */}
      {status === "done" && (
        <div className="drop-zone done">
          <div className="drop-icon">✅</div>
          <p>Transcript parsed — review your profile below</p>
          <button
            type="button"
            className="btn-secondary"
            style={{ marginTop: ".5rem", fontSize: ".8rem" }}
            onClick={reset}
          >
            Upload different files
          </button>
        </div>
      )}

      {/* Staged file list */}
      {status === "selected" && selectedFiles.length > 0 && (
        <div className="staged-files">
          <div className="staged-files__header">
            <span>{selectedFiles.length} file{selectedFiles.length > 1 ? "s" : ""} ready to send</span>
          </div>
          <ul className="staged-files__list">
            {selectedFiles.map((f, i) => (
              <li key={`${f.name}-${i}`} className="staged-file">
                <span className="staged-file__icon">
                  {f.type === "application/pdf" ? "📋" : "🖼️"}
                </span>
                <span className="staged-file__name">{f.name}</span>
                <span className="staged-file__size">{formatSize(f.size)}</span>
                <button
                  type="button"
                  className="staged-file__remove"
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${f.name}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <div className="staged-files__actions">
            <button type="button" className="btn-secondary" onClick={reset}>
              Cancel
            </button>
            <button type="button" className="btn-primary" onClick={handleUpload}>
              Parse {selectedFiles.length > 1 ? `${selectedFiles.length} files` : "transcript"} →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
