import { useEffect, useRef } from "react";
import { AGENTS, STATUS_LABEL, actorColor, actorName, prettyTool } from "../agents";
import type { AgentRecap, FeedItem } from "../derive";
import { Rich } from "./Rich";
import type { Draft, TicketDecision, TicketUpdate } from "../types";

// ------------------------------------------------------------- feed ---

export function LiveFeed({ items, live }: { items: FeedItem[]; live: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // follow the conversation only if the reader is already near the bottom
    const el = box.current;
    if (el && el.scrollHeight - el.scrollTop - el.clientHeight < 160) end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [items.length]);

  if (!items.length) return <Empty title="Nothing yet" body="When the team works this ticket, every message, ask and tool call appears here as it happens." />;
  return (
    <div className="feed" ref={box} aria-live="polite">
      {items.map((it) => (
        <FeedRow key={it.key} it={it} />
      ))}
      {live && (
        <div className="feed-typing">
          <span /> <span /> <span />
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

function FeedRow({ it }: { it: FeedItem }) {
  const color = actorColor(it.actor);
  const time = new Date(it.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const who = <b style={{ color }}>{actorName(it.actor)}</b>;
  const to = it.to ? <b style={{ color: actorColor(it.to) }}>{actorName(it.to)}</b> : null;
  return (
    <div className={`frow kind-${it.kind}`} style={{ ["--ink" as string]: color }}>
      <span className="frow-dot" />
      <div className="frow-main">
        <div className="frow-head">
          {it.kind === "tool" && (
            <>
              {who} <span className="muted">used</span> <code className="tool">{prettyTool(it.title)}</code>
              {it.ok === true && <span className="ok">✓</span>}
              {it.ok === false && <span className="bad">error</span>}
            </>
          )}
          {it.kind === "said" && <>{who} <span className="muted">said</span></>}
          {it.kind === "ask" && <>{who} <span className="arrow">→</span> {to} <span className="muted">asked</span></>}
          {it.kind === "reply" && <>{who} <span className="arrow">↩</span> {to} <span className="muted">replied</span></>}
          {["run", "finish", "human", "money", "error"].includes(it.kind) && <span className="frow-title">{it.title}</span>}
          <time>{time}</time>
        </div>
        {it.body && (it.kind === "tool" ? <div className="frow-args">{it.body}</div> : <div className="frow-body"><Rich text={it.body} /></div>)}
      </div>
    </div>
  );
}

// ------------------------------------------------------------ recap ---

export function Recap({ recap, decision, updates }: { recap: AgentRecap[]; decision: TicketDecision | null; updates: TicketUpdate[] }) {
  if (!recap.length && !decision) return <Empty title="No recap yet" body="After the team runs, each agent's part — who asked whom, tools used, what they wrote — is summarized here." />;
  return (
    <div className="recap">
      {decision && (
        <div className="decision glass-inner">
          <div className="decision-head">
            <span className="eyebrow">Boss's call</span>
            <span className={`pill pill-${decision.status}`}>{STATUS_LABEL[decision.status]}</span>
          </div>
          <p className="decision-text"><Rich text={decision.decision} /></p>
          {decision.needs_human && <p className="needs-human"><b>Your move:</b> {decision.needs_human}</p>}
        </div>
      )}
      <div className="recap-grid">
        {recap.map((r) => {
          const meta = AGENTS[r.id];
          const tools = Object.entries(r.tools);
          return (
            <article key={r.id} className="rcard" style={{ ["--ink" as string]: meta.color }}>
              <header>
                <span className="mini-avatar">{meta.initials}</span>
                <div>
                  <div className="rcard-name">{meta.name}</div>
                  <div className="rcard-sub">
                    {r.askedBy.length ? `Asked by ${[...new Set(r.askedBy)].map((a) => AGENTS[a].name).join(", ")}` : "Led the ticket"}
                    {r.asked.length > 0 && ` · asked ${[...new Set(r.asked)].map((a) => AGENTS[a].name).join(", ")}`}
                  </div>
                </div>
              </header>
              {r.lastWords && <p className="rcard-words"><Rich text={r.lastWords} /></p>}
              {r.wrote.length > 0 && (
                <ul className="rcard-wrote">
                  {r.wrote.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              )}
              <div className="rcard-tools">
                {tools.map(([t, n]) => (
                  <code key={t} className="tool">
                    {prettyTool(t)}
                    {n > 1 && <span className="times">×{n}</span>}
                  </code>
                ))}
              </div>
              <footer>{r.tokens.toLocaleString()} tokens · {r.runs} run{r.runs > 1 ? "s" : ""}</footer>
            </article>
          );
        })}
      </div>
      {updates.length > 0 && (
        <div className="history">
          <span className="eyebrow">Board history</span>
          {updates.map((u) => (
            <div key={u.id} className="hist-row">
              <span className={`pill pill-${u.status}`}>{STATUS_LABEL[u.status]}</span>
              <span className="hist-note"><Rich text={u.note} /></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------- drafts ---

export function Drafts({ drafts }: { drafts: Draft[] }) {
  if (!drafts.length) return <Empty title="No drafts" body="Customer Service saves replies here. Nothing is ever sent — drafts wait for a human to read." />;
  return (
    <div className="drafts">
      {drafts.map((d) => (
        <article key={d.id} className="letter">
          <div className="letter-stamp">Draft · not sent</div>
          <div className="letter-meta">
            <span>To <b>{d.recipient}</b></span>
            <span>#{d.id} · {d.created_at}</span>
          </div>
          <h3>{d.subject}</h3>
          <p>{d.body}</p>
          <div className="letter-by">Written by {actorName(d.author)}</div>
        </article>
      ))}
    </div>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      <span>{body}</span>
    </div>
  );
}
