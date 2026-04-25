import { useRef, useState } from "react";
import { uploadTranscript } from "../api/client";
import type { TranscriptParseResult } from "../types";

interface Props {
  sessionId: string;
  onParsed: (result: TranscriptParseResult) => void;
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
      const result = await uploadTranscript(sessionId, file);
      setParsedCount(result.courses.length);
      setStatus("done");
      onParsed(result);
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
      <h3>
        Upload Transcript{" "}
        <span className="badge badge-optional">Optional</span>
      </h3>
      <p className="subtitle">
        Upload a screenshot or PDF from CUNYfirst — we'll extract your courses
        and pre-fill your profile automatically. You'll review everything before
        submitting.
      </p>

      <div
        className={`drop-zone ${dragging ? "dragging" : ""} ${status === "done" ? "done" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => { if (status !== "uploading") inputRef.current?.click(); }}
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
            <p className="drop-sub">This may take a few seconds</p>
          </>
        )}

        {status === "done" && (
          <>
            <div className="drop-icon">✅</div>
            <p><strong>{parsedCount} courses</strong> extracted — review your profile below</p>
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
