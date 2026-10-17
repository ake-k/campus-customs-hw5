// Thin client for the Problem 7 routes. The backend runs on port 8000.
import type { ApprovalRequest, Cash, DecideResult, EventsPage, Health, Ticket, TicketDetail } from "./types";

export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `${res.status} ${res.statusText}`);
  return body as T;
}

const post = <T>(path: string, body: unknown) => call<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => call<Health>("/api/health"),
  tickets: () => call<{ today: string; tickets: Ticket[] }>("/api/tickets"),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) => post<{ run_id: string; status: string }>(`/api/tickets/${id}/run`, {}),
  events: (after: number) => call<EventsPage>(`/api/events?after=${after}&limit=1000&detail=true`),
  approvals: () => call<{ requests: ApprovalRequest[] }>("/api/approvals"),
  approve: (id: number, approver: string, note = "") =>
    post<DecideResult>(`/api/approvals/${id}/approve`, { approver, note, resume: true }),
  reject: (id: number, approver: string, note = "") =>
    post<DecideResult>(`/api/approvals/${id}/reject`, { approver, note, resume: true }),
  cash: () => call<Cash>("/api/cash"),
  reset: (requested_by: string) => post<{ reset: boolean }>("/api/reset", { requested_by }),
};
