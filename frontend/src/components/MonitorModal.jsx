function formatTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
}

function average(values) {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export default function MonitorModal({ metrics, onClose, onClear }) {
  const totalTokens = metrics.reduce(
    (sum, entry) => sum + entry.totalTokens,
    0
  );
  const inputTokens = metrics.reduce(
    (sum, entry) => sum + entry.inputTokens,
    0
  );
  const outputTokens = metrics.reduce(
    (sum, entry) => sum + entry.outputTokens,
    0
  );
  const avgLatency = average(metrics.map((entry) => entry.latencyMs));

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
          Token usage and latency for requests in this session.
        </p>

        <div className="metrics-grid">
          <div className="metric">
            <span className="metric-label">Requests</span>
            <span className="metric-value">{metrics.length}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Avg latency</span>
            <span className="metric-value">{avgLatency.toFixed(0)} ms</span>
          </div>
          <div className="metric">
            <span className="metric-label">Total tokens</span>
            <span className="metric-value">{totalTokens}</span>
          </div>
          <div className="metric">
            <span className="metric-label">In / Out</span>
            <span className="metric-value">
              {inputTokens} / {outputTokens}
            </span>
          </div>
        </div>

        <div className="metrics-list">
          {metrics.length === 0 && (
            <p className="metrics-empty">
              No requests yet. Send a message to see token and latency details.
            </p>
          )}

          {metrics.map((entry) => (
            <div className="metric-row" key={entry.id}>
              <div className="metric-row-main">
                <span className="metric-model">{entry.model}</span>
                <span className="metric-source">
                  {entry.keySource === "browser" ? "browser key" : "server key"}
                </span>
              </div>
              <div className="metric-row-stats">
                <span title="input / output / total tokens">
                  {entry.inputTokens} / {entry.outputTokens} /{" "}
                  {entry.totalTokens} tok
                </span>
                <span className="metric-latency">
                  {entry.latencyMs.toFixed(0)} ms
                </span>
                <span className="metric-time">{formatTime(entry.at)}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="modal-actions">
          <div className="spacer" />
          <button
            type="button"
            className="ghost-btn"
            disabled={metrics.length === 0}
            onClick={onClear}
          >
            Clear
          </button>
          <button type="button" className="primary-btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
