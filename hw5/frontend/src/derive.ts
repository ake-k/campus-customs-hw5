// Turns the raw audit-event stream from /api/events into what the desk draws:
// the live Agent Floor, the feed, and the per-agent recap.
import { AGENT_ORDER, prettyTool } from "./agents";
import type { AgentEvent, AgentId, TicketDecision } from "./types";

/** Everything since the last database reset: older events belong to a previous "world". */
export function currentEpoch(events: AgentEvent[]): AgentEvent[] {
  let start = 0;
  events.forEach((e, i) => {
    if (e.event === "database_reset") start = i + 1;
  });
  return events.slice(start);
}

export function ticketEvents(epoch: AgentEvent[], ticketId: number): AgentEvent[] {
  return epoch.filter((e) => e.ticket_id === ticketId);
}

export function runIds(events: AgentEvent[]): string[] {
  const ids: string[] = [];
  for (const e of events) if (e.event === "run_started" && !ids.includes(e.run_id)) ids.push(e.run_id);
  return ids;
}

// ------------------------------------------------------------ floor ---

export type AgentMood = "idle" | "thinking" | "tool" | "asking" | "waiting" | "done" | "error";

export interface AgentLive {
  mood: AgentMood;
  doing: string; // short status line under the name
  said: string | null; // latest words, for the speech bubble
  touched: boolean; // took part in this run
}

export interface Edge {
  from: AgentId;
  to: AgentId;
  status: "active" | "done" | "blocked";
  question: string;
}

export interface Floor {
  runId: string | null;
  running: boolean;
  finished: boolean;
  failed: string | null;
  agents: Record<AgentId, AgentLive>;
  edges: Edge[];
  decision: TicketDecision | null;
  usage: { requests: number; input_tokens: number; output_tokens: number; tool_calls: number } | null;
}

const fresh = (): AgentLive => ({ mood: "idle", doing: "Ready", said: null, touched: false });

function words(v: unknown): string | null {
  if (v == null) return null;
  if (typeof v === "string") return v.trim() || null;
  if (typeof v === "object" && v && "decision" in v) return String((v as { decision: string }).decision);
  return JSON.stringify(v);
}

export function buildFloor(events: AgentEvent[], runId: string | null): Floor {
  const agents = Object.fromEntries(AGENT_ORDER.map((a) => [a, fresh()])) as Record<AgentId, AgentLive>;
  const floor: Floor = { runId, running: false, finished: false, failed: null, agents, edges: [], decision: null, usage: null };
  if (!runId) return floor;

  for (const e of events) {
    if (e.run_id !== runId) continue;
    const d = e.data;
    if (e.event === "run_started") floor.running = true;
    if (e.event === "run_finished") {
      floor.running = false;
      floor.finished = true;
      floor.decision = d.decision ?? null;
      floor.usage = d.usage ?? null;
    }
    if (e.event === "run_failed") {
      floor.running = false;
      floor.failed = d.error ?? "Run failed";
    }
    if (!(e.agent in agents)) continue;
    const a = agents[e.agent as AgentId];
    a.touched = true;
    switch (e.event) {
      case "agent_started":
        a.mood = "thinking";
        a.doing = "Reading the request";
        break;
      case "model_request":
        if (a.mood !== "asking") {
          a.mood = "thinking";
          a.doing = "Thinking…";
        }
        break;
      case "model_response": {
        const calls: { tool: string }[] = d.tool_calls ?? [];
        if (d.text) a.said = d.text;
        if (calls.length) {
          const asks = calls.filter((c) => c.tool === "ask_agent").length;
          const tools = calls.filter((c) => c.tool !== "ask_agent").map((c) => prettyTool(c.tool));
          a.mood = tools.length ? "tool" : "asking";
          a.doing = tools.length ? `Using ${tools.join(", ")}` : `Asking ${asks} teammate${asks > 1 ? "s" : ""}`;
        }
        break;
      }
      case "delegation_started":
        a.mood = "asking";
        a.doing = "Waiting on a teammate";
        floor.edges.push({ from: e.agent as AgentId, to: d.to_agent, status: "active", question: d.question ?? "" });
        break;
      case "delegation_finished":
      case "delegation_blocked": {
        const edge = [...floor.edges].reverse().find((x) => x.from === e.agent && x.to === d.to_agent && x.status === "active");
        if (edge) edge.status = e.event === "delegation_blocked" ? "blocked" : "done";
        else if (e.event === "delegation_blocked")
          floor.edges.push({ from: e.agent as AgentId, to: d.to_agent, status: "blocked", question: d.question ?? "" });
        if (!floor.edges.some((x) => x.from === e.agent && x.status === "active")) {
          a.mood = "thinking";
          a.doing = "Thinking…";
        }
        break;
      }
      case "agent_finished":
        a.mood = "done";
        a.doing = "Done";
        a.said = words(d.output) ?? a.said;
        break;
      case "agent_failed":
        a.mood = "error";
        a.doing = "Hit a problem";
        a.said = d.error ?? a.said;
        break;
    }
  }
  // An agent with an outstanding ask is "asking"; the one being asked is working for them.
  for (const edge of floor.edges) if (edge.status === "active" && agents[edge.to].mood === "idle") agents[edge.to].mood = "waiting";
  return floor;
}

// ------------------------------------------------------------ recap ---

export interface AgentRecap {
  id: AgentId;
  runs: number;
  tools: Record<string, number>;
  asked: AgentId[]; // whom this agent asked
  askedBy: AgentId[];
  lastWords: string | null;
  tokens: number;
  wrote: string[]; // board changes it made (requests filed, drafts saved, status set)
}

export function buildRecap(events: AgentEvent[]): AgentRecap[] {
  const map = new Map<AgentId, AgentRecap & { runSet: Set<string> }>();
  const get = (id: AgentId) => {
    if (!map.has(id))
      map.set(id, { id, runs: 0, runSet: new Set(), tools: {}, asked: [], askedBy: [], lastWords: null, tokens: 0, wrote: [] });
    return map.get(id)!;
  };
  for (const e of events) {
    if (!AGENT_ORDER.includes(e.agent as AgentId)) continue;
    const r = get(e.agent as AgentId);
    const d = e.data;
    r.runSet.add(e.run_id);
    if (e.event === "tool_call") r.tools[d.tool] = (r.tools[d.tool] ?? 0) + 1;
    if (e.event === "model_response") r.tokens += (d.usage?.input_tokens ?? 0) + (d.usage?.output_tokens ?? 0);
    if (e.event === "delegation_started") {
      r.asked.push(d.to_agent);
      get(d.to_agent).askedBy.push(e.agent as AgentId);
    }
    if (e.event === "agent_finished") r.lastWords = words(d.output);
    if (e.event === "tool_result" && d.ok && d.result) {
      const res = d.result;
      if (d.tool === "request_payment_approval") r.wrote.push(`Filed request #${res.request_id} · ${res.payee} $${res.amount}`);
      if (d.tool === "save_customer_draft") r.wrote.push(`Saved draft #${res.draft_id}`);
      if (d.tool === "update_ticket") r.wrote.push(`Set status → ${String(res.status).replace(/_/g, " ")}`);
    }
  }
  return AGENT_ORDER.filter((id) => map.has(id)).map((id) => {
    const { runSet, ...rest } = map.get(id)!;
    return { ...rest, runs: runSet.size };
  });
}

// ------------------------------------------------------------- feed ---

export interface FeedItem {
  key: string;
  ts: string;
  actor: string;
  kind: "said" | "tool" | "ask" | "reply" | "start" | "finish" | "human" | "money" | "run" | "error";
  title: string;
  body?: string;
  ok?: boolean | null;
  to?: AgentId;
}

/** A readable feed: tool calls paired with their result, model chatter folded away. */
export function buildFeed(events: AgentEvent[]): FeedItem[] {
  const items: FeedItem[] = [];
  const openCalls: FeedItem[] = [];
  for (const e of events) {
    const d = e.data;
    const base = { key: `${e.index}`, ts: e.ts, actor: e.agent };
    switch (e.event) {
      case "run_started":
        items.push({ ...base, kind: "run", title: d.instruction ? "Team resumed" : "Team started", body: d.instruction ?? undefined });
        break;
      case "run_finished":
        items.push({ ...base, kind: "finish", title: `Run finished · ${String(d.decision?.status ?? "").replace(/_/g, " ")}`, body: d.decision?.decision });
        break;
      case "run_failed":
      case "agent_failed":
        items.push({ ...base, kind: "error", title: "Something went wrong", body: d.error });
        break;
      case "model_response":
        if (d.text) items.push({ ...base, kind: "said", title: "said", body: d.text });
        break;
      case "tool_call": {
        const args = Object.entries(d.args ?? {})
          .filter(([k, v]) => k !== "acting_agent" && v !== "" && v !== 0)
          .map(([k, v]) => `${k}=${typeof v === "string" && v.length > 40 ? v.slice(0, 40) + "…" : v}`)
          .join(", ");
        const item: FeedItem = { ...base, kind: "tool", title: d.tool, body: args, ok: null };
        items.push(item);
        openCalls.push(item);
        break;
      }
      case "tool_result": {
        const i = openCalls.findIndex((c) => c.actor === e.agent && c.title === d.tool);
        if (i >= 0) {
          openCalls[i].ok = !!d.ok;
          openCalls.splice(i, 1);
        }
        break;
      }
      case "tool_denied":
        items.push({ ...base, kind: "error", title: `Refused ${d.tool}`, body: d.reason });
        break;
      case "delegation_started":
        items.push({ ...base, kind: "ask", title: "asked", to: d.to_agent, body: d.question });
        break;
      case "delegation_finished":
        items.push({ ...base, actor: d.to_agent, kind: "reply", title: "replied to", to: e.agent as AgentId, body: d.reply });
        break;
      case "delegation_blocked":
        items.push({ ...base, kind: "error", title: `Couldn't ask ${d.to_agent}`, body: d.reason });
        break;
      case "human_decision":
        items.push({ ...base, kind: "human", title: `${d.approver} ${d.decision} request #${d.request_id}`, body: d.note || undefined });
        break;
      case "payment_made":
        items.push({ ...base, kind: "money", title: `Paid $${Number(d.result?.amount ?? 0).toLocaleString()} to ${d.result?.payee}`, body: `Checking is now $${Number(d.result?.balance_after ?? 0).toLocaleString()}` });
        break;
      case "payment_refused":
        items.push({ ...base, kind: "error", title: `Payment for request #${d.request_id} refused`, body: d.result?.error });
        break;
    }
  }
  return items;
}
