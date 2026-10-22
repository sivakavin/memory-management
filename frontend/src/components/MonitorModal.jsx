import { useEffect, useMemo, useState } from "react";

import { api } from "../api";

function formatTimestamp(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function dayKey(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}`;
}

function formatDay(value) {
  if (value === "all") return "All days";

  const date = new Date(`${value}T00:00:00`);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  if (value === dayKey(today)) return "Today";
  if (value === dayKey(yesterday)) return "Yesterday";

  return date.toLocaleDateString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
  });
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function toolLabel(tools) {
  return tools && tools.length > 0 ? tools.join(", ") : "no tools";
}

export default function MonitorModal({ userId, threads, refreshToken, onClose }) {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDay, setSelectedDay] = useState("all");
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    api
      .listMetrics(userId)
      .then((response) => {
        if (!cancelled) {
          setMetrics(response.metrics || []);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [userId, refreshToken]);

  const days = useMemo(() => {
    const keys = new Set(
      metrics.map((entry) => dayKey(entry.created_at)).filter(Boolean)
    );
    return [...keys].sort((a, b) => b.localeCompare(a));
  }, [metrics]);

  useEffect(() => {
    if (selectedDay !== "all" && !days.includes(selectedDay)) {
      setSelectedDay("all");
    }
  }, [days, selectedDay]);

  const titleById = useMemo(
    () => new Map(threads.map((thread) => [thread.thread_id, thread.title])),
    [threads]
  );

  const filtered = useMemo(
    () =>
      selectedDay === "all"
        ? metrics
        : metrics.filter((entry) => dayKey(entry.created_at) === selectedDay),
    [metrics, selectedDay]
  );

  const totals = useMemo(
    () =>
      filtered.reduce(
        (acc, entry) => {
          acc.requests += 1;
          acc.inputTokens += entry.input_tokens;
          acc.outputTokens += entry.output_tokens;
          acc.totalTokens += entry.total_tokens;
          acc.latency += entry.latency_ms;
          if (entry.tools_used && entry.tools_used.length > 0) {
            acc.toolRequests += 1;
          }
          return acc;
        },
        {
          requests: 0,
          inputTokens: 0,
          outputTokens: 0,
          totalTokens: 0,
          latency: 0,
          toolRequests: 0,
        }
      ),
    [filtered]
  );

  const conversations = useMemo(() => {
    const grouped = new Map();

    for (const entry of filtered) {
      let group = grouped.get(entry.thread_id);
      if (!group) {
        group = {
          threadId: entry.thread_id,
          title:
            titleById.get(entry.thread_id) ||
            `Conversation ${entry.thread_id.slice(0, 8)}`,
          requests: 0,
          inputTokens: 0,
          outputTokens: 0,
          totalTokens: 0,
          toolRequests: 0,
          tools: new Set(),
        };
        grouped.set(entry.thread_id, group);
      }

      group.requests += 1;
      group.inputTokens += entry.input_tokens;
      group.outputTokens += entry.output_tokens;
      group.totalTokens += entry.total_tokens;
      if (entry.tools_used && entry.tools_used.length > 0) {
        group.toolRequests += 1;
        entry.tools_used.forEach((tool) => group.tools.add(tool));
      }
    }

    return [...grouped.values()]
      .map((group) => ({ ...group, tools: [...group.tools] }))
      .sort((a, b) => b.totalTokens - a.totalTokens);
  }, [filtered, titleById]);

  const avgLatency =
    totals.requests > 0 ? totals.latency / totals.requests : 0;

  async function handleClear() {
    if (clearing) return;
    setClearing(true);
    try {
      await api.clearMetrics(userId);
      setMetrics([]);
      setSelectedDay("all");
    } catch (err) {
      setError(err.message);
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal monitor-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2>Monitor</h2>
          <button
            type="button"
            className="modal-close"
            aria-label="Close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <p className="modal-note">
          Token usage by day and conversation, including whether tools were
          called.
        </p>

        <div className="monitor-filters">
          <label className="monitor-filter">
            <span>Day</span>
            <select
              value={selectedDay}
              onChange={(event) => setSelectedDay(event.target.value)}
            >
              <option value="all">All days</option>
              {days.map((day) => (
                <option key={day} value={day}>
                  {formatDay(day)}
                </option>
              ))}
            </select>
          </label>
          <span className="monitor-count">
            {loading ? "Loading…" : `${filtered.length} requests`}
          </span>
        </div>

        {error && <div className="chat-error">{error}</div>}

        <div className="metrics-grid">
          <div className="metric">
            <span className="metric-label">Requests</span>
            <span className="metric-value">{formatNumber(totals.requests)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Total tokens</span>
            <span className="metric-value">{formatNumber(totals.totalTokens)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">In / Out</span>
            <span className="metric-value">
              {formatNumber(totals.inputTokens)} /{" "}
              {formatNumber(totals.outputTokens)}
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">Avg latency</span>
            <span className="metric-value">{avgLatency.toFixed(0)} ms</span>
          </div>
          <div className="metric">
            <span className="metric-label">Tool requests</span>
            <span className="metric-value">
              {formatNumber(totals.toolRequests)}
            </span>
          </div>
        </div>

        <div className="monitor-section">
          <div className="monitor-section-head">
            <h3>By conversation</h3>
            <span>{conversations.length}</span>
          </div>

          {conversations.length === 0 && !loading ? (
            <p className="metrics-empty">No conversations for this day.</p>
          ) : (
            <div className="conversation-list">
              {conversations.map((group) => (
                <div className="conversation-row" key={group.threadId}>
                  <div className="conversation-info">
                    <span className="conversation-title">{group.title}</span>
                    <span className="conversation-meta">
                      {group.requests} requests ·{" "}
                      {formatNumber(group.inputTokens)} in /{" "}
                      {formatNumber(group.outputTokens)} out
                    </span>
                  </div>
                  <div className="conversation-stats">
                    <span className="conversation-tokens">
                      {formatNumber(group.totalTokens)} tok
                    </span>
                    <span
                      className={`tool-chip ${
                        group.toolRequests > 0 ? "used" : "none"
                      }`}
                      title={toolLabel(group.tools)}
                    >
                      {group.toolRequests > 0
                        ? `${group.toolRequests} tool req`
                        : "no tools"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="monitor-section">
          <div className="monitor-section-head">
            <h3>Requests</h3>
            <span>{filtered.length}</span>
          </div>

          <div className="metrics-list">
            {loading && <p className="metrics-empty">Loading requests…</p>}

            {!loading && filtered.length === 0 && (
              <p className="metrics-empty">
                No requests for this day. Send a message to see token and
                latency details.
              </p>
            )}

            {filtered.map((entry) => (
              <div className="metric-row" key={entry.id}>
                <div className="metric-row-main">
                  <span className="metric-model">{entry.model}</span>
                  <div className="metric-badges">
                    <span
                      className={`tool-chip ${
                        entry.tools_used && entry.tools_used.length > 0
                          ? "used"
                          : "none"
                      }`}
                      title={toolLabel(entry.tools_used)}
                    >
                      {toolLabel(entry.tools_used)}
                    </span>
                    <span className="metric-source">
                      {entry.key_source === "browser"
                        ? "browser key"
                        : "server key"}
                    </span>
                  </div>
                </div>
                <div className="metric-row-stats">
                  <span title="input / output / total tokens">
                    {formatNumber(entry.input_tokens)} /{" "}
                    {formatNumber(entry.output_tokens)} /{" "}
                    {formatNumber(entry.total_tokens)} tok
                  </span>
                  <span className="metric-latency">
                    {Math.round(entry.latency_ms)} ms
                  </span>
                  <span className="metric-thread">
                    {titleById.get(entry.thread_id) || "Unknown conversation"}
                  </span>
                  <span className="metric-time">
                    {formatTimestamp(entry.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-actions">
          <div className="spacer" />
          <button
            type="button"
            className="ghost-btn"
            disabled={metrics.length === 0 || clearing}
            onClick={handleClear}
          >
            {clearing ? "Clearing…" : "Clear history"}
          </button>
          <button type="button" className="primary-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
