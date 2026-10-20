import { useState } from "react";

import { api } from "../api";
import { loadLlmConfig, saveLlmConfig } from "../llmConfig";

const SUGGESTED_MODELS = [
  "openai/gpt-oss-120b",
  "llama-3.3-70b-versatile",
  "llama-3.1-8b-instant",
];

const EMPTY = { apiKey: "", model: "", temperature: "" };

function temperatureLabel(value) {
  if (value <= 0.3) return "Precise";
  if (value <= 0.8) return "Balanced";
  if (value <= 1.4) return "Creative";
  return "Playful";
}

function normalize(form) {
  return {
    apiKey: form.apiKey.trim(),
    model: form.model.trim(),
    temperature: form.temperature === "" ? "" : String(form.temperature),
  };
}

function sourceLabel(source) {
  if (source === "browser") return "browser key";
  if (source === "server") return "server key";
  return "no key";
}

export default function SettingsModal({ onClose, onSaved }) {
  const [form, setForm] = useState(() => loadLlmConfig());
  const [showKey, setShowKey] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);

  const sliderValue = form.temperature === "" ? 0 : Number(form.temperature);

  function update(field, value) {
    setConfirmDelete(false);
    setConfirmReset(false);
    setTestResult(null);
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function applyConfig(config) {
    saveLlmConfig(config);
    setForm(config);
    setTestResult(null);
    onSaved(config);
  }

  function handleSubmit(event) {
    event.preventDefault();
    applyConfig(normalize(form));
    onClose();
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await api.status(normalize(form));
      setTestResult(
        response.llm_connected
          ? {
              ok: true,
              message: `Connected · ${response.model} · ${sourceLabel(
                response.key_source
              )}`,
            }
          : { ok: false, message: response.detail }
      );
    } catch (error) {
      setTestResult({ ok: false, message: error.message });
    } finally {
      setTesting(false);
    }
  }

  function handleDeleteKey() {
    if (!confirmDelete) {
      setConfirmDelete(true);
      setConfirmReset(false);
      return;
    }
    applyConfig({ ...form, apiKey: "" });
    setConfirmDelete(false);
  }

  function handleReset() {
    if (!confirmReset) {
      setConfirmReset(true);
      setConfirmDelete(false);
      return;
    }
    applyConfig(EMPTY);
    setConfirmReset(false);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form
        className="modal"
        onClick={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <div className="modal-header">
          <h2>LLM settings</h2>
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
          Bring your own Groq API key. It is stored only in this browser and
          sent to the agent with each message. Leave a field blank to use the
          server default.
        </p>

        <label className="field">
          <span>API key</span>
          <div className="field-row">
            <input
              type={showKey ? "text" : "password"}
              value={form.apiKey}
              placeholder="gsk_..."
              autoComplete="off"
              onChange={(event) => update("apiKey", event.target.value)}
            />
            <button
              type="button"
              className="ghost-btn"
              onClick={() => setShowKey((value) => !value)}
            >
              {showKey ? "Hide" : "Show"}
            </button>
          </div>
        </label>

        <label className="field">
          <span>Model</span>
          <input
            list="model-options"
            value={form.model}
            placeholder="openai/gpt-oss-120b"
            autoComplete="off"
            onChange={(event) => update("model", event.target.value)}
          />
          <datalist id="model-options">
            {SUGGESTED_MODELS.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </label>

        <div className="field">
          <div className="field-head">
            <span>Temperature</span>
            <span className="field-value">
              {sliderValue.toFixed(1)} · {temperatureLabel(sliderValue)}
            </span>
          </div>
          <input
            className="range"
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={sliderValue}
            onChange={(event) => update("temperature", event.target.value)}
          />
          <div className="range-labels">
            <span>Real · precise</span>
            <span>Fun · creative</span>
          </div>
        </div>

        <div className="test-row">
          <button
            type="button"
            className="ghost-btn"
            disabled={testing}
            onClick={handleTest}
          >
            {testing ? "Testing…" : "Test connection"}
          </button>
          {testResult && (
            <span
              className={`test-result ${
                testResult.ok ? "ok" : "fail"
              }`}
            >
              {testResult.ok ? "✓ " : "✕ "}
              {testResult.message}
            </span>
          )}
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="ghost-btn"
            onClick={handleReset}
          >
            {confirmReset ? "Confirm reset?" : "Reset"}
          </button>
          <button
            type="button"
            className={`danger-btn ${confirmDelete ? "confirm" : ""}`}
            disabled={!form.apiKey}
            onClick={handleDeleteKey}
          >
            {confirmDelete ? "Confirm delete?" : "Delete key"}
          </button>
          <div className="spacer" />
          <button type="button" className="ghost-btn" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary-btn">
            Save
          </button>
        </div>
      </form>
    </div>
  );
}
