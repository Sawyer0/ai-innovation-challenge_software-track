import { useEffect, useState, useSyncExternalStore } from "react";
import { loadUsage } from "../api/client";
import { formatWait, getUsageSnapshot, secondsUntilReset, subscribeUsage } from "../api/usage";

let requested = false;

/** "AI requests left: 28 of 30 this hour", or when the visitor can try again. */
export default function UsageChip() {
  const usage = useSyncExternalStore(subscribeUsage, getUsageSnapshot);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    // Every chip shares one store; fetch it once per page load.
    if (!requested) {
      requested = true;
      void loadUsage();
    }
  }, []);

  const blocked = usage
    ? [usage.day, usage.hour, usage.minute].find((w) => w.remaining === 0)
    : undefined;

  useEffect(() => {
    // Count down while blocked, then fetch fresh numbers once the window resets.
    if (!blocked) return;
    const timer = window.setInterval(() => {
      setNow(Date.now());
      if (secondsUntilReset(blocked) === 0) void loadUsage();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [blocked]);

  if (!usage) return null;

  let text: string;
  let tone = "";
  if (blocked) {
    const wait = formatWait(secondsUntilReset(blocked, now));
    text =
      blocked === usage.day
        ? `Demo AI limit reached for today · try again in ${wait}`
        : `AI limit reached · try again in ${wait}`;
    tone = " usage-chip--blocked";
  } else {
    text = `AI requests left: ${usage.hour.remaining} of ${usage.hour.limit} this hour`;
    if (usage.hour.remaining <= 5) tone = " usage-chip--low";
  }

  return (
    <span
      className={`usage-chip${tone}`}
      role="status"
      aria-live="polite"
      title="Limits keep this free demo available for everyone."
    >
      {text}
    </span>
  );
}
