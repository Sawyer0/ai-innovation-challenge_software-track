import { useRef, useState } from "react";
import { uploadTranscript } from "../api/client";
import type { ParsedCourse } from "../types";

interface Props {
  sessionId: string;
  onParsed: (courses: ParsedCourse[]) => void;
}

export default function TranscriptUpload({ sessionId, onParsed }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [dragging, setDragging] = useState(false);
  const [parsedCount, setParsedCount] = useState(0);

  async function handleFile(file: File) {
    const allowed = ["image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"];
    if (!allowed.includes(file.type)) {
      setErrorMsg("Please upload a JPEG, PNG, WebP, GIF, or PDF file.");
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setErrorMsg("");

    try {
      const courses = await uploadTranscript(sessionId, file);
      setParsedCount(courses.length);
      setStatus("done");
      onParsed(courses);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Upload failed. Try again.");
      setStatus("error");
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  return (
    <div className="transcript-section">
      <h3>Upload Transcript <span className="badge badge-optional">Optional</span></h3>
      <p className="subtitle">
        Upload a screenshot or PDF from CUNYfirst — we'll extract your completed
        courses automatically using AI. You can also add courses manually below.
      </p>

      <div
        className={`drop-zone ${dragging ? "dragging" : ""} ${status === "done" ? "done" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
          style={{ display: "none" }}
          onChange={onInputChange}
        />

        {status === "idle" && (
          <>
            <div className="drop-icon">📄</div>
            <p>Drag & drop your transcript here</p>
            <p className="drop-sub">or click to browse — JPEG, PNG, PDF accepted</p>
          </>
        )}

        {status === "uploading" && (
          <>
            <div className="spinner" />
            <p>Parsing transcript with AI…</p>
          </>
        )}

        {status === "done" && (
          <>
            <div className="drop-icon">✅</div>
            <p><strong>{parsedCount} courses</strong> extracted from your transcript</p>
            <p className="drop-sub">Click to upload a different file</p>
          </>
        )}

        {status === "error" && (
          <>
            <div className="drop-icon">⚠️</div>
            <p className="error-text">{errorMsg}</p>
            <p className="drop-sub">Click to try again</p>
          </>
        )}
      </div>
    </div>
  );
}
