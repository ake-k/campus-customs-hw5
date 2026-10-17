import { STATUS_LABEL, TYPE_LABEL, money } from "../agents";
import type { Ticket, TicketDetail } from "../types";

export function TicketHero({
  ticket,
  detail,
  running,
  teamBusy,
  onRun,
}: {
  ticket: Ticket;
  detail: TicketDetail | null;
  running: boolean;
  teamBusy: boolean;
  onRun: () => void;
}) {
  const facts: { k: string; v: string; warn?: boolean }[] = [];
  const inv = detail?.linked.inventory?.find((r) => r.size === ticket.size);
  const price = detail?.linked.pricing?.[0];
  const lease = detail?.linked.lease?.[0];
  const invoice = detail?.linked.invoice?.[0];
  if (ticket.sku) facts.push({ k: "Item", v: `${ticket.sku} · ${ticket.size} × ${ticket.qty}` });
  if (inv) {
    const short = (ticket.qty ?? 0) - Number(inv.qty);
    facts.push({ k: "On hand", v: short > 0 ? `${inv.qty} (short ${short})` : `${inv.qty}`, warn: short > 0 });
  }
  if (price) facts.push({ k: "List / cost", v: `${money(Number(price.list_price))} / ${money(Number(price.unit_cost))}` });
  if (lease) facts.push({ k: "Rent", v: `${money(Number(lease.monthly_rent))} due ${lease.next_due}` });
  if (invoice)
    facts.push({ k: `Invoice #${invoice.id}`, v: `${money(Number(invoice.amount))} · ${invoice.status} · due ${invoice.due_date}`, warn: invoice.status === "open" });

  const label = running ? "Team is working…" : teamBusy ? "Team busy on another ticket" : ticket.status === "open" ? "Start the team" : "Run the team again";

  return (
    <section className="hero glass">
      <div className="hero-main">
        <div className="eyebrow">
          {TYPE_LABEL[ticket.type] ?? ticket.type} · {ticket.requester} · opened {ticket.created_at.slice(0, 10)}
        </div>
        <h1>
          <span className="hero-num">#{ticket.id}</span> {ticket.subject}
        </h1>
        {ticket.notes && <p className="hero-quote">“{ticket.notes}”</p>}
        <div className="facts">
          {facts.map((f) => (
            <div key={f.k} className={`fact ${f.warn ? "warn" : ""}`}>
              <span className="k">{f.k}</span>
              <span className="v">{f.v}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="hero-side">
        <span className={`pill big pill-${ticket.status}`}>{STATUS_LABEL[ticket.status]}</span>
        <button className={`run-btn ${running ? "is-running" : ""}`} onClick={onRun} disabled={running || teamBusy}>
          <span className="run-dot" />
          {label}
        </button>
      </div>
    </section>
  );
}
