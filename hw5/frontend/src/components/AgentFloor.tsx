import { AGENTS, AGENT_ORDER } from "../agents";
import type { Floor } from "../derive";
import { Rich } from "./Rich";
import type { AgentId } from "../types";

const PAIRS: [AgentId, AgentId][] = AGENT_ORDER.flatMap((a, i) => AGENT_ORDER.slice(i + 1).map((b) => [a, b] as [AgentId, AgentId]));

export function AgentFloor({ floor, idleHint }: { floor: Floor; idleHint: string }) {
  const live = floor.running;
  const anyTouched = AGENT_ORDER.some((a) => floor.agents[a].touched);

  return (
    <div className={`floor ${live ? "is-live" : ""}`} aria-label="Agent floor">
      <svg className="floor-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {/* Full connectivity: every agent can ask every other, so every pair has a faint line. */}
        {PAIRS.map(([a, b]) => (
          <line key={`${a}-${b}`} className="mesh" x1={AGENTS[a].x} y1={AGENTS[a].y} x2={AGENTS[b].x} y2={AGENTS[b].y} vectorEffect="non-scaling-stroke" />
        ))}
        {floor.edges.map((e, i) => (
          <line
            key={i}
            className={`edge edge-${e.status}`}
            x1={AGENTS[e.from].x}
            y1={AGENTS[e.from].y}
            x2={AGENTS[e.to].x}
            y2={AGENTS[e.to].y}
            stroke={AGENTS[e.from].color}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>

      {AGENT_ORDER.map((id) => {
        const meta = AGENTS[id];
        const st = floor.agents[id];
        const dim = anyTouched && !st.touched;
        const bubbleUp = meta.y > 60;
        return (
          <div
            key={id}
            className={`seat mood-${st.mood} ${dim ? "is-dim" : ""}`}
            style={{ left: `${meta.x}%`, top: `${meta.y}%`, ["--ink" as string]: meta.color }}
          >
            {st.said && bubbleUp && <Bubble text={st.said} up />}
            <div className="avatar" title={`${meta.name}: ${meta.role}`}>
              <span className="ring" />
              <span className="initials">{meta.initials}</span>
              {st.mood === "done" && <span className="badge-done" aria-label="done">✓</span>}
              {st.mood === "error" && <span className="badge-err" aria-label="error">!</span>}
            </div>
            <div className="seat-name">{meta.name}</div>
            <div className="seat-doing" aria-live="polite">{st.touched ? st.doing : meta.role}</div>
            {st.said && !bubbleUp && <Bubble text={st.said} />}
          </div>
        );
      })}

      {!anyTouched && <div className="floor-hint">{idleHint}</div>}
    </div>
  );
}

function Bubble({ text, up = false }: { text: string; up?: boolean }) {
  return (
    <div className={`bubble ${up ? "bubble-up" : ""}`} title={text.replace(/\*\*/g, "")}>
      <Rich text={text} />
    </div>
  );
}
