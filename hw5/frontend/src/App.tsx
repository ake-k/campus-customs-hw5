import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_URL, api } from "./api";
import { money } from "./agents";
import { buildFeed, buildFloor, buildRecap, currentEpoch, runIds, ticketEvents } from "./derive";
import { useDesk, useTicketDetail } from "./hooks";
import type { ApprovalRequest, TicketDecision } from "./types";
import { AgentFloor } from "./components/AgentFloor";
import { Drafts, LiveFeed, Recap } from "./components/Panels";
import { ApprovalInbox, CashCard } from "./components/Money";
import { TicketHero } from "./components/TicketHero";
import { TicketRail } from "./components/TicketRail";

type Tab = "feed" | "recap" | "drafts";
interface Toast { id: number; tone: "ok" | "warn" | "err"; text: string }

export default function App() {
  const desk = useDesk();
  const [selected, setSelected] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("feed");
  const [approver, setApproverState] = useState(() => localStorage.getItem("desk.approver") ?? "");
  const [workingId, setWorkingId] = useState<number | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const setApprover = (s: string) => {
    setApproverState(s);
    localStorage.setItem("desk.approver", s);
  };
  const toast = useCallback((tone: Toast["tone"], text: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, tone, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  // Pick the first open ticket once the board loads.
  useEffect(() => {
    if (selected == null && desk.tickets.length) setSelected((desk.tickets.find((t) => t.is_open) ?? desk.tickets[0]).id);
  }, [desk.tickets, selected]);

  const ticket = desk.tickets.find((t) => t.id === selected) ?? null;
  const epoch = useMemo(() => currentEpoch(desk.events), [desk.events]);
  const tEvents = useMemo(() => (selected == null ? [] : ticketEvents(epoch, selected)), [epoch, selected]);
  const runId = useMemo(() => runIds(tEvents).at(-1) ?? null, [tEvents]);
  const floor = useMemo(() => buildFloor(tEvents, runId), [tEvents, runId]);
  const feed = useMemo(() => buildFeed(tEvents), [tEvents]);
  const recap = useMemo(() => buildRecap(tEvents), [tEvents]);
  const decision = useMemo<TicketDecision | null>(() => {
    const done = tEvents.filter((e) => e.event === "run_finished");
    return (done.at(-1)?.data.decision as TicketDecision) ?? null;
  }, [tEvents]);
  const detail = useTicketDetail(selected, tEvents.length + desk.approvals.length);
  const running = !!ticket?.run_status || floor.running || starting;

  // When a run we watched finishes, show the recap: the "what happened" moment.
  const watched = useRef(new Set<string>());
  const celebrated = useRef(new Set<string>());
  useEffect(() => {
    if (!runId) return;
    if (floor.running) watched.current.add(runId);
    if (floor.finished && watched.current.has(runId) && !celebrated.current.has(runId)) {
      celebrated.current.add(runId);
      setTab("recap");
      if (floor.decision) toast(floor.decision.status === "resolved" ? "ok" : "warn", `#${floor.decision.ticket_id}: ${floor.decision.decision}`);
    }
  }, [floor.running, floor.finished, floor.decision, runId, toast]);

  const startRun = async () => {
    if (!ticket) return;
    setStarting(true);
    setTab("feed");
    try {
      await api.run(ticket.id);
      desk.nudge();
    } catch (e) {
      toast("err", (e as Error).message);
    } finally {
      window.setTimeout(() => setStarting(false), 1500);
    }
  };

  const decide = async (r: ApprovalRequest, d: "approve" | "reject") => {
    setWorkingId(r.id);
    try {
      const res = await (d === "approve" ? api.approve(r.id, approver.trim()) : api.reject(r.id, approver.trim()));
      if (d === "reject") toast("warn", `Rejected request #${r.id}. No money moved.`);
      else if (res.paid) toast("ok", `Paid ${money(r.amount)} to ${r.payee}. Checking is now ${money(res.payment?.balance_after ?? 0)}.`);
      else toast("err", `Approved, but the payment was refused: ${res.payment?.error ?? "unknown reason"}`);
      setSelected(r.ticket_id);
      setTab("feed");
      desk.nudge();
    } catch (e) {
      toast("err", (e as Error).message);
    } finally {
      setWorkingId(null);
    }
  };

  const reset = async () => {
    setConfirmReset(false);
    try {
      await api.reset(approver.trim() || "dashboard");
      toast("ok", "Fresh start: the working database was restored from the original.");
      setTab("feed");
      desk.nudge();
    } catch (e) {
      toast("err", (e as Error).message);
    }
  };

  return (
    <div className="app">
      <div className="backdrop" aria-hidden="true">
        <span className="blob b1" /> <span className="blob b2" /> <span className="blob b3" />
      </div>

      <header className="topbar glass">
        <div className="brand">
          <span className="logo">CC</span>
          <div>
            <div className="brand-name">The Desk</div>
            <div className="brand-sub">Campus Customs · Multi-Agent Operations</div>
          </div>
        </div>
        <div className="top-pills">
          <span className="tpill">Shop date <b>{desk.health?.shop_date ?? "—"}</b></span>
          <span className="tpill">Model <b>{desk.health?.model ?? "—"}</b></span>
          <span className={`tpill status ${desk.connected === false ? "is-off" : desk.busy ? "is-busy" : "is-idle"}`}>
            <i />
            {desk.connected === false ? "Backend offline" : desk.busy ? "Team working" : "Team idle"}
          </span>
          {confirmReset ? (
            <span className="reset-confirm">
              Reset all tickets and cash?
              <button className="btn-danger" onClick={reset}>Reset</button>
              <button className="btn-ghost" onClick={() => setConfirmReset(false)}>Cancel</button>
            </span>
          ) : (
            <button className="btn-ghost" onClick={() => setConfirmReset(true)} disabled={desk.busy} title="Restore the working database from the original">
              Fresh start
            </button>
          )}
        </div>
      </header>

      {desk.connected === false && (
        <div className="offline glass">
          Can't reach the backend at <code>{API_URL}</code>. Start it from <code>hw5/backend</code> with <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="layout">
        <TicketRail tickets={desk.tickets} selected={selected} onSelect={(id) => { setSelected(id); setTab("feed"); }} />

        <div className="stage">
          {ticket ? (
            <>
              <TicketHero ticket={ticket} detail={detail} running={running} teamBusy={desk.busy && !running} onRun={startRun} />
              <section className="floor-card glass">
                <div className="floor-head">
                  <span className="eyebrow">Agent floor</span>
                  <span className="muted small">
                    {floor.running ? "Live — lines light up when one agent asks another" : floor.finished ? `Last run · ${floor.usage?.requests ?? 0} model calls · ${((floor.usage?.input_tokens ?? 0) + (floor.usage?.output_tokens ?? 0)).toLocaleString()} tokens` : "Any agent can ask any other"}
                  </span>
                </div>
                <AgentFloor floor={floor} idleHint="Start the team and watch the Boss hand out the work." />
              </section>
              <section className="panel glass">
                <nav className="seg" role="tablist">
                  {(["feed", "recap", "drafts"] as Tab[]).map((t) => (
                    <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
                      {t === "feed" ? "Live feed" : t === "recap" ? "Recap" : `Drafts${detail?.board.drafts.length ? ` · ${detail.board.drafts.length}` : ""}`}
                    </button>
                  ))}
                </nav>
                {tab === "feed" && <LiveFeed items={feed} live={floor.running} />}
                {tab === "recap" && <Recap recap={recap} decision={decision} updates={detail?.board.updates ?? []} />}
                {tab === "drafts" && <Drafts drafts={detail?.board.drafts ?? []} />}
              </section>
            </>
          ) : (
            <section className="hero glass"><div className="skeleton" /></section>
          )}
        </div>

        <div className="money">
          <CashCard cash={desk.cash} />
          <ApprovalInbox requests={desk.approvals} approver={approver} setApprover={setApprover} onDecide={decide} workingId={workingId} />
        </div>
      </main>

      <div className="toasts" aria-live="assertive">
        {toasts.map((t) => (
          <div key={t.id} className={`toast glass tone-${t.tone}`}>{t.text}</div>
        ))}
      </div>
    </div>
  );
}
