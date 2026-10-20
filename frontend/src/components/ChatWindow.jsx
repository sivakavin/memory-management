import { useEffect, useRef, useState } from "react";

export default function ChatWindow({
  userId,
  thread,
  messages,
  sending,
  loading,
  ready,
  isNewUser,
  error,
  onSend,
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages, sending, loading]);

  function handleSubmit(event) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    onSend(text);
    setDraft("");
  }

  if (!thread) {
    return (
      <div className="welcome">
        <div className="welcome-inner">
          {!ready ? (
            <div className="welcome-emoji">…</div>
          ) : (
            <>
              <div className="welcome-emoji">{isNewUser ? "👋" : "💬"}</div>
              <h2>
                {isNewUser
                  ? `Welcome, ${userId}!`
                  : `Welcome back, ${userId}!`}
              </h2>
              <p>
                {isNewUser
                  ? "I'm your Memory Agent. I remember what you tell me across conversations, so ask me anything to get started."
                  : "Pick a conversation from the left, or start a new one."}
              </p>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="chat">
      <div className="messages" ref={scrollRef}>
        {loading && <p className="messages-hint">Loading conversation…</p>}

        {!loading && messages.length === 0 && (
          <p className="messages-hint">Say hello to start this conversation.</p>
        )}

        {messages.map((message, index) => (
          <div key={index} className={`bubble-row ${message.role}`}>
            <div className={`bubble ${message.role}`}>{message.content}</div>
          </div>
        ))}

        {sending && (
          <div className="bubble-row assistant">
            <div className="bubble assistant typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>

      {error && <div className="chat-error">{error}</div>}

      <form className="composer" onSubmit={handleSubmit}>
        <input
          className="composer-input"
          placeholder="Type a message…"
          value={draft}
          maxLength={10000}
          autoFocus
          autoComplete="off"
          disabled={sending}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button
          className="composer-send"
          type="submit"
          disabled={sending || !draft.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
