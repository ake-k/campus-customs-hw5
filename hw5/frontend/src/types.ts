// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentId = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";
export type Actor = AgentId | "human" | "system";

export type TicketStatus = "open" | "in_progress" | "awaiting_approval" | "waiting_on_vendor" | "resolved" | "declined";

export interface Ticket {
  id: number;
  type: string;
  requester: string;
  subject: string;
  sku: string | null;
  size: string | null;
  qty: number | null;
  lease_id: number | null;
  invoice_id: number | null;
  status: TicketStatus;
  notes: string | null;
  created_at: string;
  is_open: boolean;
  state: "open" | "resolved";
  run_status: "queued" | "running" | null;
  pending_approvals: number;
  drafts_count: number;
  ticket_updates_count: number;
  approval_requests_count: number;
}

export interface ApprovalRequest {
  id: number;
  ticket_id: number;
  kind: "invoice" | "rent" | "purchase_order";
  ref_id: number | null;
  payee: string;
  vendor_id: number | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  unit_cost: number | null;
  amount: number;
  account: string;
  reason: string;
  requested_by: string;
  status: "pending" | "approved" | "rejected" | "paid";
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  payment_id: number | null;
  expected_arrival: string | null;
  created_at: string;
}

export interface Draft {
  id: number;
  ticket_id: number;
  recipient: string;
  subject: string;
  body: string;
  author: string;
  status: string;
  created_at: string;
}

export interface TicketUpdate {
  id: number;
  ticket_id: number;
  status: TicketStatus;
  note: string;
  author: string;
  created_at: string;
}

export interface TicketDetail {
  today: string;
  ticket: Ticket;
  linked: Record<string, Record<string, unknown>[]>;
  board: { updates: TicketUpdate[]; approval_requests: ApprovalRequest[]; drafts: Draft[] };
}

export interface Payment {
  id: number;
  kind: string;
  ref_id: number | null;
  amount: number;
  account: string;
  paid_at: string;
  approved_by: string;
}

export interface Cash {
  account: string;
  balance: number;
  as_of: string;
  shop_date: string;
  unpaid_requests_total: number;
  balance_after_unpaid_requests: number;
  payments: Payment[];
}

export interface AgentEvent {
  index: number;
  ts: string;
  run_id: string;
  ticket_id: number | null;
  agent: Actor;
  depth: number;
  event: string;
  summary: string;
  data: Record<string, any>;
}

export interface EventsPage {
  events: AgentEvent[];
  cursor: number;
  team_busy: boolean;
}

export interface Health {
  ok: boolean;
  model: string;
  database: string;
  shop_date: string;
  team_busy: boolean;
}

export interface TicketDecision {
  ticket_id: number;
  status: TicketStatus;
  assigned_to: AgentId[];
  decision: string;
  actions_taken: string[];
  approval_request_ids: number[];
  draft_ids: number[];
  needs_human: string | null;
}

export interface DecideResult {
  request: ApprovalRequest;
  decision: "approved" | "rejected";
  payment: (Record<string, any> & { error?: string }) | null;
  paid: boolean;
  resumed_run: { run_id: string } | null;
}
