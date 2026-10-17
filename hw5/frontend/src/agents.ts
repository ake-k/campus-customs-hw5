import type { Actor, AgentId, TicketStatus } from "./types";

export interface AgentMeta {
  id: AgentId;
  name: string;
  initials: string;
  role: string;
  color: string; // the agent's ink: ring, edges, feed accents
  // Seat on the Agent Floor (percent of the floor box). Boss at the head, specialists around.
  x: number;
  y: number;
}

export const AGENTS: Record<AgentId, AgentMeta> = {
  boss: { id: "boss", name: "Boss", initials: "B", role: "Routes & decides", color: "#7c5cff", x: 50, y: 17 },
  inventory: { id: "inventory", name: "Inventory", initials: "In", role: "Stock & vendors", color: "#0a84ff", x: 15, y: 45 },
  accounting: { id: "accounting", name: "Accounting", initials: "Ac", role: "Cash & approvals", color: "#22a06b", x: 85, y: 45 },
  facilities: { id: "facilities", name: "Facilities", initials: "Fa", role: "Leases & rent", color: "#f08c00", x: 28, y: 84 },
  customer_service: { id: "customer_service", name: "Customer Service", initials: "CS", role: "Customer drafts", color: "#e8467c", x: 72, y: 84 },
};

export const AGENT_ORDER: AgentId[] = ["boss", "inventory", "accounting", "facilities", "customer_service"];

export function actorName(a: Actor | string): string {
  if (a in AGENTS) return AGENTS[a as AgentId].name;
  if (a === "human") return "You";
  return "Desk";
}

export function actorColor(a: Actor | string): string {
  if (a in AGENTS) return AGENTS[a as AgentId].color;
  return a === "human" ? "#5b6577" : "#8a94a6";
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  awaiting_approval: "Needs your approval",
  waiting_on_vendor: "Waiting on vendor",
  resolved: "Resolved",
  declined: "Declined",
};

export const TYPE_LABEL: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Discount request",
};

export const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });

export const prettyTool = (t: string) => t.replace(/_/g, " ");
