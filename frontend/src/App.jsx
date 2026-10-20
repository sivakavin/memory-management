import { useCallback, useEffect, useState } from "react";

import { api } from "./api";
import ChatWindow from "./components/ChatWindow";
import MonitorModal from "./components/MonitorModal";
import SettingsModal from "./components/SettingsModal";
import Sidebar from "./components/Sidebar";
import StatusBadge from "./components/StatusBadge";
import UserGate from "./components/UserGate";

const STORAGE_KEY = "memory-agent:user-id";

function toThreadSummary(thread) {
  return {
    thread_id: thread.thread_id,
    title: thread.title,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
    message_count: thread.message_count,
  };
}

export default function App() {
  const [userId, setUserId] = useState(
    () => localStorage.getItem(STORAGE_KEY) || ""
  );
  const [threads, setThreads] = useState([]);
  const [activeThreadId, setActiveThreadId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [llmConfigVersion, setLlmConfigVersion] = useState(0);
  const [monitorOpen, setMonitorOpen] = useState(false);
  const [metrics, setMetrics] = useState([]);

  const refreshThreads = useCallback(async (id) => {
    try {
      const response = await api.listThreads(id);
      setThreads(response.threads);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    if (!userId) return;
    setBootstrapped(false);
    refreshThreads(userId).finally(() => setBootstrapped(true));
  }, [userId, refreshThreads]);

  function resetView() {
    setThreads([]);
    setActiveThreadId(null);
    setMessages([]);
    setError("");
    setMetrics([]);
  }

  function handleLogin(name) {
    localStorage.setItem(STORAGE_KEY, name);
    resetView();
    setUserId(name);
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    resetView();
    setUserId("");
  }

  async function handleNewThread() {
    setError("");
    setSidebarOpen(false);
    try {
      const created = await api.createThread(userId);
      setThreads((prev) => [toThreadSummary(created), ...prev]);
      setActiveThreadId(created.thread_id);
      setMessages([]);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSelectThread(threadId) {
    setActiveThreadId(threadId);
    setMessages([]);
    setError("");
    setLoading(true);
    setSidebarOpen(false);
    try {
      const response = await api.getMessages(userId, threadId);
      setMessages(response.messages);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDeleteThread(threadId) {
    setError("");
    try {
      await api.deleteThread(userId, threadId);
      setThreads((prev) =>
        prev.filter((thread) => thread.thread_id !== threadId)
      );
      if (activeThreadId === threadId) {
        setActiveThreadId(null);
        setMessages([]);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSend(text) {
    if (sending) return;
    setError("");

    let threadId = activeThreadId;
    if (!threadId) {
      try {
        const created = await api.createThread(userId);
        threadId = created.thread_id;
        setThreads((prev) => [toThreadSummary(created), ...prev]);
        setActiveThreadId(threadId);
        setMessages([]);
      } catch (err) {
        setError(err.message);
        return;
      }
    }

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setSending(true);
    try {
      const response = await api.chat(userId, threadId, text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.answer },
      ]);
      setMetrics((prev) =>
        [
          {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            at: new Date().toISOString(),
            model: response.model,
            keySource: response.key_source,
            latencyMs: response.latency_ms ?? 0,
            inputTokens: response.input_tokens ?? 0,
            outputTokens: response.output_tokens ?? 0,
            totalTokens: response.total_tokens ?? 0,
          },
          ...prev,
        ].slice(0, 100)
      );
      refreshThreads(userId);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "error", content: `Could not reach the agent: ${err.message}` },
      ]);
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (!userId) {
    return <UserGate onSubmit={handleLogin} />;
  }

  const activeThread =
    threads.find((thread) => thread.thread_id === activeThreadId) || null;

  return (
    <div className="app">
      <Sidebar
        userId={userId}
        threads={threads}
        activeThreadId={activeThreadId}
        isOpen={sidebarOpen}
        onSelect={handleSelectThread}
        onNew={handleNewThread}
        onDelete={handleDeleteThread}
        onLogout={handleLogout}
      />

      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <main className="main">
        <header className="topbar">
          <button
            className="menu-toggle"
            type="button"
            aria-label="Toggle conversations"
            onClick={() => setSidebarOpen((open) => !open)}
          >
            ☰
          </button>
          <div className="topbar-title">
            {activeThread ? activeThread.title : "Memory Agent"}
          </div>
          <button
            className="icon-btn"
            type="button"
            title="Monitor"
            aria-label="Monitor"
            onClick={() => setMonitorOpen(true)}
          >
            📈
          </button>
          <button
            className="icon-btn"
            type="button"
            title="LLM settings"
            aria-label="LLM settings"
            onClick={() => setSettingsOpen(true)}
          >
            ⚙
          </button>
          <StatusBadge reloadToken={llmConfigVersion} />
        </header>

        <ChatWindow
          userId={userId}
          thread={activeThread}
          messages={messages}
          sending={sending}
          loading={loading}
          ready={bootstrapped}
          isNewUser={threads.length === 0}
          error={error}
          onSend={handleSend}
        />
      </main>

      {settingsOpen && (
        <SettingsModal
          onClose={() => setSettingsOpen(false)}
          onSaved={() => setLlmConfigVersion((version) => version + 1)}
        />
      )}

      {monitorOpen && (
        <MonitorModal
          metrics={metrics}
          onClear={() => setMetrics([])}
          onClose={() => setMonitorOpen(false)}
        />
      )}
    </div>
  );
}
