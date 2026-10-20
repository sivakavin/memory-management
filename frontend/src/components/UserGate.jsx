import { useState } from "react";

export default function UserGate({ onSubmit }) {
  const [value, setValue] = useState("");
  const [touched, setTouched] = useState(false);

  function handleSubmit(event) {
    event.preventDefault();
    const name = value.trim();
    if (!name) {
      setTouched(true);
      return;
    }
    onSubmit(name);
  }

  return (
    <div className="gate">
      <form className="gate-card" onSubmit={handleSubmit}>
        <div className="gate-logo">◈</div>
        <h1>Memory Agent</h1>
        <p className="gate-subtitle">
          Enter a username to start chatting. Your conversations and memories
          are stored per user.
        </p>

        <label className="gate-label" htmlFor="user-id">
          Username
        </label>
        <input
          id="user-id"
          className="gate-input"
          placeholder="e.g. ravi"
          value={value}
          maxLength={100}
          autoFocus
          autoComplete="off"
          onChange={(event) => setValue(event.target.value)}
        />
        {touched && !value.trim() && (
          <p className="gate-error">Please enter a username to continue.</p>
        )}

        <button className="gate-button" type="submit">
          Continue
        </button>
      </form>
    </div>
  );
}
