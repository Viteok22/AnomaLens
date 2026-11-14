const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

export { API_BASE };

async function jsonFetch(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

export function fetchSensors() {
  return jsonFetch("/api/sensors");
}

export function fetchScenarios() {
  return jsonFetch("/api/scenarios");
}

export function fetchMetrics() {
  return jsonFetch("/api/metrics");
}

export function fetchHealth() {
  return jsonFetch("/api/health");
}

export function fetchAlerts(limit = 50) {
  return jsonFetch(`/api/alerts?limit=${limit}`);
}

export function ackAlert(id) {
  return jsonFetch(`/api/alerts/${id}/ack`, { method: "POST" });
}

export function closeAlert(id) {
  return jsonFetch(`/api/alerts/${id}/close`, { method: "POST" });
}

export async function uploadCsv(file) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/upload`, {
    method: "POST",
    body: form,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `HTTP ${response.status}`);
  }
  return data;
}

export function testTelegram() {
  return jsonFetch("/api/telegram/test", { method: "POST" });
}

export function streamUrl() {
  return `${WS_BASE}/ws/stream`;
}
