import type { AiUsage, UsageWindow } from "../types";

// A tiny store for the visitor's AI quota. AI responses carry X-AI-* headers;
// /api/usage fills it on load and after failures that carry no headers.

type Listener = () => void;

let current: AiUsage | null = null;
let receivedAt = 0;
const listeners = new Set<Listener>();

function publish(usage: AiUsage) {
  current = usage;
  receivedAt = Date.now();
  listeners.forEach((l) => l());
}

export function subscribeUsage(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getUsageSnapshot(): AiUsage | null {
  return current;
}

/** Seconds until a window resets, counted from when the numbers were received. */
export function secondsUntilReset(window: UsageWindow, now = Date.now()): number {
  return Math.max(0, window.reset_seconds - Math.floor((now - receivedAt) / 1000));
}

function readWindow(headers: Headers, name: string): UsageWindow | null {
  const limit = headers.get(`X-AI-Limit-${name}`);
  const remaining = headers.get(`X-AI-Remaining-${name}`);
  const reset = headers.get(`X-AI-Reset-${name}`);
  if (limit === null || remaining === null) return null;
  return { limit: Number(limit), remaining: Number(remaining), reset_seconds: Number(reset ?? 0) };
}

/** Update the store from an AI response's headers. Returns false when it had none. */
export function updateUsageFromHeaders(headers: Headers): boolean {
  const minute = readWindow(headers, "Minute");
  const hour = readWindow(headers, "Hour");
  const day = readWindow(headers, "Day");
  if (!minute || !hour || !day) return false;
  publish({ minute, hour, day });
  return true;
}

export async function refreshUsage(baseUrl: string): Promise<void> {
  try {
    const res = await fetch(`${baseUrl}/api/usage`, { cache: "no-store" });
    if (res.ok) publish((await res.json()) as AiUsage);
  } catch {
    // The chip is informational; keep the last known numbers.
  }
}

export function formatWait(seconds: number): string {
  if (seconds < 90) return `${Math.max(1, seconds)} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  return `${Math.round(seconds / 3600)} h`;
}
