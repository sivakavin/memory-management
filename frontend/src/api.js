import { loadLlmConfig } from "./llmConfig";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

function llmHeaders(config) {
  const source = config || loadLlmConfig();
  const headers = {};

  if (source.apiKey && source.apiKey.trim()) {
    headers["X-LLM-Api-Key"] = source.apiKey.trim();
  }
  if (source.model && source.model.trim()) {
    headers["X-LLM-Model"] = source.model.trim();
  }
  if (source.temperature !== "" && source.temperature != null) {
    headers["X-LLM-Temperature"] = String(source.temperature);
  }

  return headers;
}

async function request(path, { withLlm = false, llmConfig = null, ...options } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (withLlm) {
    Object.assign(headers, llmHeaders(llmConfig));
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });

  const text = await response.text();
  let body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const detail =
      body && typeof body === "object" && body.detail
        ? body.detail
        : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return body;
}

export const api = {
  status: (llmConfig = null) =>
    request("/status", { withLlm: true, llmConfig }),

  listThreads: (userId) =>
    request(`/users/${encodeURIComponent(userId)}/threads`),

  createThread: (userId) =>
    request(`/users/${encodeURIComponent(userId)}/threads`, {
      method: "POST",
    }),

  getMessages: (userId, threadId) =>
    request(
      `/users/${encodeURIComponent(userId)}/threads/${encodeURIComponent(
        threadId
      )}/messages`
    ),

  deleteThread: (userId, threadId) =>
    request(
      `/users/${encodeURIComponent(userId)}/threads/${encodeURIComponent(
        threadId
      )}`,
      { method: "DELETE" }
    ),

  chat: (userId, threadId, message) =>
    request("/chat", {
      method: "POST",
      withLlm: true,
      body: JSON.stringify({
        user_id: userId,
        thread_id: threadId,
        message,
      }),
    }),
};

export { API_BASE };
