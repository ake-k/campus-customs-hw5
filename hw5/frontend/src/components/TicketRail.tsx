import { STATUS_LABEL, TYPE_LABEL } from "../agents";
import type { Ticket } from "../types";

export function TicketRail({
  tickets,
  selected,
  onSelect,
}: {
  tickets: Ticket[];
  selected: number | null;
  onSelect: (id: number) => void;
}) {
  const open = tickets.filter((t) => t.is_open);
  const done = tickets.filter((t) => !t.is_open);
  return (
    <aside className="rail">
      <div className="rail-head">
        <span className="eyebrow">Board</span>
        <span className="count">{open.length} open · {done.length} resolved</span>
      </div>
      {open.map((t) => (
        <TicketCard key={t.id} t={t} active={t.id === selected} onSelect={onSelect} />
      ))}
      {done.length > 0 && <div className="rail-divider"><span>Resolved</span></div>}
      {done.map((t) => (
        <TicketCard key={t.id} t={t} active={t.id === selected} onSelect={onSelect} />
      ))}
    </aside>
  );
}

function TicketCard({ t, active, onSelect }: { t: Ticket; active: boolean; onSelect: (id: number) => void }) {
  const working = t.run_status != null;
  return (
    <button
      className={`ticket-card glass status-${t.status} ${active ? "is-active" : ""} ${working ? "is-working" : ""}`}
      onClick={() => onSelect(t.id)}
      aria-pressed={active}
    >
      <div className="tc-top">
        <span className="tc-num">#{t.id}</span>
        <span className="tc-type">{TYPE_LABEL[t.type] ?? t.type}</span>
      </div>
      <div className="tc-subject">{t.subject}</div>
      <div className="tc-who">{t.requester}</div>
      <div className="tc-foot">
        <span className={`pill pill-${t.status}`}>{working ? (t.run_status === "queued" ? "Queued" : "Team working") : STATUS_LABEL[t.status]}</span>
        {t.pending_approvals > 0 && <span className="tc-flag">{t.pending_approvals} to approve</span>}
      </div>
      {t.status === "resolved" && <span className="seal" aria-hidden="true">Resolved</span>}
    </button>
  );
}
