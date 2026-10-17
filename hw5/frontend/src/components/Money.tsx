import { useEffect, useRef, useState } from "react";
import { actorName, money } from "../agents";
import { useTweened } from "../hooks";
import type { ApprovalRequest, Cash } from "../types";

// ------------------------------------------------------------- cash ---

export function CashCard({ cash }: { cash: Cash | null }) {
  const shown = useTweened(cash?.balance);
  const prev = useRef<number | undefined>(undefined);
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null);

  useEffect(() => {
    if (cash == null) return;
    if (prev.current !== undefined && cash.balance < prev.current) setDrop({ amount: prev.current - cash.balance, key: Date.now() });
    prev.current = cash.balance;
  }, [cash?.balance]);

  if (!cash) return <section className="cash glass"><div className="skeleton" /></section>;
  const start = cash.balance + cash.payments.reduce((s, p) => s + p.amount, 0);
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / start) * 100))}%`;
  const pending = Math.min(cash.unpaid_requests_total, cash.balance);

  return (
    <section className="cash glass">
      <div className="cash-head">
        <span className="eyebrow">Checking</span>
        <span className="muted small">as of {cash.as_of}</span>
      </div>
      <div className="balance" aria-live="polite">
        {money(shown)}
        {drop && (
          <span key={drop.key} className="drop">−{money(drop.amount)}</span>
        )}
      </div>
      <div className="meter" title="Spent · waiting on approval · free">
        <span className="m-spent" style={{ width: pct(start - cash.balance) }} />
        <span className="m-pending" style={{ width: pct(pending) }} />
      </div>
      <div className="meter-legend">
        <span><i className="lg-spent" />Paid {money(start - cash.balance)}</span>
        <span><i className="lg-pending" />Awaiting you {money(cash.unpaid_requests_total)}</span>
        <span><i className="lg-free" />Free {money(Math.max(cash.balance_after_unpaid_requests, 0))}</span>
      </div>
      {cash.balance_after_unpaid_requests < 0 && (
        <p className="cash-warn">Approving everything waiting would need {money(-cash.balance_after_unpaid_requests)} more than the shop has. Payments that would overdraw are refused.</p>
      )}
      <div className="ledger">
        <span className="eyebrow">Payments</span>
        {cash.payments.length === 0 && <div className="muted small">No money has left the shop yet.</div>}
        {cash.payments.map((p) => (
          <div key={p.id} className="ledger-row">
            <span className="lr-kind">{p.kind.replace("_", " ")}</span>
            <span className="lr-by">approved by {p.approved_by}</span>
            <span className="lr-amt">−{money(p.amount)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// -------------------------------------------------------- approvals ---

const KIND: Record<ApprovalRequest["kind"], string> = { invoice: "Vendor invoice", rent: "Rent", purchase_order: "Purchase order" };

export function ApprovalInbox({
  requests,
  approver,
  setApprover,
  onDecide,
  workingId,
}: {
  requests: ApprovalRequest[];
  approver: string;
  setApprover: (s: string) => void;
  onDecide: (r: ApprovalRequest, decision: "approve" | "reject") => void;
  workingId: number | null;
}) {
  const pending = requests.filter((r) => r.status === "pending");
  const stuck = requests.filter((r) => r.status === "approved"); // approved but payment refused
  const decided = requests.filter((r) => r.status === "paid" || r.status === "rejected").slice(-4).reverse();
  const signed = approver.trim().length >= 2;

  return (
    <section className="inbox glass">
      <div className="inbox-head">
        <span className="eyebrow">Needs your approval</span>
        {pending.length > 0 && <span className="count-badge">{pending.length}</span>}
      </div>
      <label className="signer">
        <span>Signing as</span>
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your full name" aria-label="Approver name" />
      </label>
      {pending.length === 0 && stuck.length === 0 && (
        <div className="muted small inbox-empty">Nothing waiting. Agents can only <em>prepare</em> payments — they land here for you.</div>
      )}
      {[...pending, ...stuck].map((r) => (
        <ApprovalCard key={r.id} r={r} signed={signed} working={workingId === r.id} onDecide={onDecide} />
      ))}
      {decided.length > 0 && (
        <div className="decided">
          {decided.map((r) => (
            <div key={r.id} className={`decided-row is-${r.status}`}>
              <span>#{r.id} {r.payee}</span>
              <span>{r.status === "paid" ? `paid ${money(r.amount)}` : "rejected"} · {r.decided_by}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ApprovalCard({
  r,
  signed,
  working,
  onDecide,
}: {
  r: ApprovalRequest;
  signed: boolean;
  working: boolean;
  onDecide: (r: ApprovalRequest, d: "approve" | "reject") => void;
}) {
  // Two-step approve: money is real, so the first click arms, the second pays.
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = window.setTimeout(() => setArmed(false), 5000);
    return () => window.clearTimeout(t);
  }, [armed]);
  const retry = r.status === "approved";

  return (
    <article className={`req ${armed ? "is-armed" : ""}`}>
      <div className="req-top">
        <span className="req-kind">{KIND[r.kind]} · ticket #{r.ticket_id}</span>
        <span className="req-amt">{money(r.amount)}</span>
      </div>
      <div className="req-payee">{r.payee}</div>
      {r.kind === "purchase_order" && (
        <div className="req-po">{r.qty} × {r.sku} {r.size} at {money(r.unit_cost ?? 0)}</div>
      )}
      <p className="req-reason">{r.reason}</p>
      <div className="req-by">Prepared by {actorName(r.requested_by)}{retry && <> · <b>approved by {r.decided_by}, payment refused</b></>}</div>
      <div className="req-actions">
        <button className="btn-ghost" disabled={!signed || working || retry} onClick={() => onDecide(r, "reject")}>
          Reject
        </button>
        <button
          className={`btn-pay ${armed ? "is-armed" : ""}`}
          disabled={!signed || working}
          onClick={() => (armed ? (setArmed(false), onDecide(r, "approve")) : setArmed(true))}
        >
          {working ? "Paying…" : armed ? `Confirm · pay ${money(r.amount)}` : retry ? "Try payment again" : `Approve & pay`}
        </button>
      </div>
      {!signed && <div className="req-hint">Type your name above to sign.</div>}
    </article>
  );
}
