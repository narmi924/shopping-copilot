import type { MetricsResponse, TurnResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      // Keep the status-based fallback for non-JSON server errors.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function createSession(): Promise<string> {
  const payload = await request<{ session_id: string }>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({
      user_profile: {
        purchase_frequency: "not disclosed",
        average_prior_rating: null,
        rating_style: "balanced",
        preference_tags: ["quality", "practical"],
        summary: "Prefers practical, quality options.",
      },
    }),
  });
  return payload.session_id;
}

export function sendTurn(sessionId: string, message: string): Promise<TurnResponse> {
  return request<TurnResponse>(`/api/sessions/${sessionId}/turns`, {
    method: "POST",
    body: JSON.stringify({ message, top_k: 10 }),
  });
}

export function getMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/api/metrics");
}
