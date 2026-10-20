const STORAGE_KEY = "memory-agent:llm-config";

const DEFAULTS = { apiKey: "", model: "", temperature: "" };

export function loadLlmConfig() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return { ...DEFAULTS, ...(stored || {}) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveLlmConfig(config) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function isLlmConfigured(config) {
  return Boolean(config && config.apiKey && config.apiKey.trim());
}
