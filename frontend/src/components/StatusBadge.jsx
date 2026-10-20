import { useEffect, useState } from "react";

import { api } from "../api";

const POLL_INTERVAL_MS = 15000;

export default function StatusBadge({ reloadToken = 0 }) {
  const [status, setStatus] = useState({
    state: "checking",
    detail: "",
    source: "",
  });

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const response = await api.status();
        if (cancelled) return;
        setStatus({
          state: response.llm_connected ? "online" : "offline",
          detail: response.detail,
          source:
            response.key_source === "browser"
              ? "browser key"
              : response.key_source === "server"
                ? "server key"
                : "",
        });
      } catch (error) {
        if (!cancelled) {
          setStatus({ state: "offline", detail: error.message, source: "" });
        }
      }
    }

    check();
    const timer = setInterval(check, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [reloadToken]);

  const label =
    status.state === "online"
      ? "LLM connected"
      : status.state === "offline"
        ? "LLM unavailable"
        : "Checking…";

  const tooltip = [status.detail, status.source && `via ${status.source}`]
    .filter(Boolean)
    .join(" · ");

  return (
    <span
      className={`status-badge status-${status.state}`}
      title={tooltip || label}
    >
      <span className="status-dot" />
      <span className="status-label">{label}</span>
      {status.source === "browser key" && status.state === "online" && (
        <span className="status-tag">BYOK</span>
      )}
    </span>
  );
}
