import { useEffect, useState } from "react";

export default function Sidebar({
  userId,
  threads,
  activeThreadId,
  isOpen,
  onSelect,
  onNew,
  onDelete,
  onLogout,
}) {
  const [pendingDelete, setPendingDelete] = useState(null);

  useEffect(() => {
    if (!pendingDelete) return undefined;
    const timer = setTimeout(() => setPendingDelete(null), 4000);
    return () => clearTimeout(timer);
  }, [pendingDelete]);

  function handleDeleteClick(event, threadId) {
    event.stopPropagation();
    if (pendingDelete === threadId) {
      setPendingDelete(null);
      onDelete(threadId);
      return;
    }
    setPendingDelete(threadId);
  }

  return (
    <aside className={`sidebar ${isOpen ? "sidebar-open" : ""}`}>
      <div className="sidebar-header">
        <div className="avatar">{userId.slice(0, 1).toUpperCase()}</div>
        <div className="user-meta">
          <span className="user-name">{userId}</span>
          <span className="user-role">Signed in</span>
        </div>
      </div>

      <button className="new-chat" type="button" onClick={onNew}>
        <span aria-hidden="true">＋</span> New conversation
      </button>

      <div className="thread-list">
        <p className="thread-list-title">Conversations</p>

        {threads.length === 0 && (
          <p className="thread-empty">No conversations yet.</p>
        )}

        {threads.map((thread) => (
          <div
            key={thread.thread_id}
            className={`thread-item ${
              thread.thread_id === activeThreadId ? "active" : ""
            }`}
          >
            <button
              type="button"
              className="thread-main"
              onClick={() => onSelect(thread.thread_id)}
            >
              <span className="thread-title">
                {thread.title || "New conversation"}
              </span>
              <span className="thread-sub">
                {thread.message_count} message
                {thread.message_count === 1 ? "" : "s"}
              </span>
            </button>
            <button
              type="button"
              className={`thread-delete ${
                pendingDelete === thread.thread_id ? "confirm" : ""
              }`}
              title="Delete conversation"
              aria-label="Delete conversation"
              onClick={(event) => handleDeleteClick(event, thread.thread_id)}
            >
              {pendingDelete === thread.thread_id ? "Delete?" : "🗑"}
            </button>
          </div>
        ))}
      </div>

      <button className="logout" type="button" onClick={onLogout}>
        Sign out
      </button>
    </aside>
  );
}
