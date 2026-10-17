import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { AgentEvent, ApprovalRequest, Cash, Health, Ticket, TicketDetail } from "./types";

const FAST_MS = 1200; // while the team is working
const SLOW_MS = 4000; // idle

/** Polls the backend: new audit events by cursor, and the board/cash/approvals whenever something changes. */
export function useDesk() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [cash, setCash] = useState<Cash | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState(false);
  const [connected, setConnected] = useState<boolean | null>(null);
  const cursor = useRef(-1);
  const timer = useRef<number | undefined>(undefined);

  const refreshBoard = useCallback(async () => {
    const [t, c, a, h] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.health()]);
    setTickets(t.tickets);
    setCash(c);
    setApprovals(a.requests);
    setHealth(h);
  }, []);

  const tick = useCallback(async () => {
    let isBusy = false;
    try {
      const page = await api.events(cursor.current);
      isBusy = page.team_busy;
      if (page.cursor < cursor.current) {
        // the audit file shrank (shouldn't happen: it's append-only) — start over
        cursor.current = -1;
        setEvents([]);
      } else {
        cursor.current = page.cursor;
      }
      if (page.events.length) setEvents((prev) => [...prev, ...page.events]);
      setBusy(page.team_busy);
      await refreshBoard();
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(tick, isBusy ? FAST_MS : SLOW_MS);
    }
  }, [refreshBoard]);

  /** Poll right away (after a click), instead of waiting for the next tick. */
  const nudge = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(tick, 150);
  }, [tick]);

  useEffect(() => {
    tick();
    return () => window.clearTimeout(timer.current);
  }, [tick]);

  return { events, tickets, cash, approvals, health, busy, connected, nudge };
}

/** Ticket detail (linked rows, drafts, updates); refetched when that ticket's events change. */
export function useTicketDetail(ticketId: number | null, version: number) {
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  useEffect(() => {
    if (ticketId == null) return;
    let live = true;
    api.ticket(ticketId).then((d) => live && setDetail(d)).catch(() => {});
    return () => {
      live = false;
    };
  }, [ticketId, version]);
  return detail?.ticket.id === ticketId ? detail : null;
}

/** Eases a number toward its new value, so the balance visibly counts down after a payment. */
export function useTweened(target: number | undefined, ms = 1100) {
  const [shown, setShown] = useState(target ?? 0);
  const from = useRef(target ?? 0);
  useEffect(() => {
    if (target === undefined) return;
    const start = performance.now();
    const origin = from.current;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = origin + (target - origin) * eased;
      setShown(v);
      from.current = v;
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return shown;
}
