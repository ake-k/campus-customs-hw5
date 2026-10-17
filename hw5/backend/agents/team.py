"""Runs the Campus Customs agent team.

- Full connectivity: every agent has the same `ask_agent` tool and can ask any
  other agent. Guards stop loops: no asking yourself or anyone up your chain
  (they are waiting on you), chains stop at MAX_DEPTH, each agent has its own
  ask limit, and the whole team shares MAX_DELEGATIONS_PER_TICKET.
- Agent loop: each agent runs with `agent.iter()`, so every step (model
  request, model response with tool calls and token usage, MCP tool call and
  result, delegation) is appended to output/audit_trail.json as it happens.
- Shop facts and changes come only from the MCP server (mcp_link.TOOLSET).

CLI (run from hw5/backend/):
    python -m agents.team 101             # work one ticket
    python -m agents.team --all           # work every open ticket
    python -m agents.team --reset         # restore the working DB from the original
    python -m agents.team --approve 2 --approver "Your Name" [--resume]   # approving also pays
    python -m agents.team --reject 2 --approver "Your Name"
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.usage import UsageLimits

import audit
from config import MAX_DELEGATIONS_PER_TICKET, MAX_DEPTH, MODEL_NAME, MODEL_SETTINGS, PROMPTS_DIR, build_model
from mcp_link import TOOLSET, human_call, system_call, toolset_for
from models import AgentId, AgentProfile, AuditEvent, Delegation, TicketDecision, TicketRun

from . import TEAM


# ------------------------------------------------------------ run state ---

@dataclass
class RunState:
    """One team run on one ticket: shared budget, delegations, usage, audit."""

    run_id: str
    ticket_id: int | None
    shop_date: str | None = None
    seq: int = 0
    delegations: list[Delegation] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=lambda: {"requests": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0})
    listeners: list[asyncio.Queue] = field(default_factory=list)  # live feed for the dashboard

    def log(self, agent: str, depth: int, chain: tuple[str, ...], event: str, **data: Any) -> None:
        self.seq += 1
        entry = AuditEvent(
            seq=self.seq, ts=audit.now_utc(), shop_date=self.shop_date, run_id=self.run_id,
            ticket_id=self.ticket_id, agent=agent, depth=depth, chain=list(chain), event=event,
            data=audit.clip(data),
        )
        audit.append(entry)
        for q in self.listeners:
            q.put_nowait(entry.model_dump())


@dataclass
class AgentDeps:
    """What one running agent knows about itself and the run it belongs to."""

    state: RunState
    chain: tuple[AgentId, ...]  # agent ids from the Boss down to this agent
    asks: int = 0

    @property
    def profile(self) -> AgentProfile:
        return TEAM[self.chain[-1]]

    @property
    def depth(self) -> int:
        return len(self.chain) - 1

    def log(self, event: str, **data: Any) -> None:
        self.state.log(self.profile.id, self.depth, self.chain, event, **data)


# --------------------------------------------------------- delegation ---

async def ask_agent(ctx: RunContext[AgentDeps], agent_id: AgentId, question: str) -> str:
    """Ask another Campus Customs teammate to do a task or answer a question, and wait for their reply.

    Args:
        agent_id: Who to ask: "boss", "inventory", "accounting", "facilities", or "customer_service".
        question: A self-contained request. They cannot see your conversation, so include the ticket id,
            SKUs, sizes, quantities, amounts, and decisions they need.
    """
    deps, state = ctx.deps, ctx.deps.state
    me = deps.profile

    def blocked(reason: str) -> str:
        deps.log("delegation_blocked", to_agent=agent_id, question=question, reason=reason)
        state.delegations.append(Delegation(from_agent=me.id, to_agent=agent_id, question=question,
                                            depth=deps.depth + 1, status="blocked", reply=reason))
        return f"Not sent: {reason}"

    if agent_id not in TEAM:
        return blocked(f"There is no teammate called {agent_id!r}. Choose one of: {', '.join(TEAM)}.")
    if agent_id == me.id:
        return blocked("You can't ask yourself. Do it with your own tools.")
    if agent_id in deps.chain:
        return blocked(f"{TEAM[agent_id].name} is waiting on your answer, so they can't take a new ask. Reply with what you have.")
    if deps.depth >= MAX_DEPTH:
        return blocked("This chain of asks is already as deep as allowed. Answer with what you have.")
    if deps.asks >= me.ask_limit:
        return blocked(f"You've used all {me.ask_limit} of your asks. Answer with what you have.")
    if sum(d.status != "blocked" for d in state.delegations) >= MAX_DELEGATIONS_PER_TICKET:
        return blocked("The team has used its delegation budget for this ticket. Answer with what you have.")

    deps.asks += 1
    delegation = Delegation(from_agent=me.id, to_agent=agent_id, question=question, depth=deps.depth + 1)
    state.delegations.append(delegation)
    deps.log("delegation_started", to_agent=agent_id, question=question)
    result = await run_agent(agent_id, question, state, deps.chain + (agent_id,))
    delegation.reply, delegation.status = str(result["output"]), result["status"]
    deps.log("delegation_finished", to_agent=agent_id, status=delegation.status, reply=delegation.reply)
    return delegation.reply


# ------------------------------------------------------------- agents ---

def _team_section(deps: AgentDeps) -> str:
    me = deps.profile
    asker = "the operations desk (a human-run dashboard)" if deps.depth == 0 else TEAM[deps.chain[-2]].name
    lines = [
        "## Working with your team",
        f"You are **{me.name}** (id `{me.id}`). This request came from {asker}; your reply goes back to them.",
    ]
    if deps.depth >= MAX_DEPTH:
        lines.append("You are at the end of a long chain of asks and cannot ask anyone else. Answer from your own tools.")
        return "\n".join(lines)
    lines.append(f"Use `ask_agent` to ask any teammate for help (at most {me.ask_limit} asks in this task):")
    waiting = [TEAM[a].name for a in deps.chain[:-1]]
    for p in TEAM.values():
        if p.id != me.id and p.id not in deps.chain:
            lines.append(f"- `{p.id}`: {p.name}. {p.role}")
    if waiting:
        lines.append(f"Waiting on your answer (don't ask them): {', '.join(waiting)}.")
    lines.append(
        "Ask only when a teammate owns the tool or knowledge you need. Make each ask self-contained and specific "
        "(ticket id, SKU, size, qty, amounts). Send independent asks in the same step so they run in parallel. "
        f"Never ask the same thing twice. The whole team shares {MAX_DELEGATIONS_PER_TICKET} asks per ticket."
    )
    return "\n".join(lines)


def _summarize_request(node: Any) -> dict[str, Any]:
    parts = node.request.parts
    prompts = [p.content for p in parts if isinstance(p, UserPromptPart)]
    returns = [p.tool_name for p in parts if isinstance(p, ToolReturnPart)]
    return {"user_prompt": prompts[0] if prompts else None, "tool_results_sent": returns, "parts": len(parts)}


def _summarize_response(resp: Any) -> dict[str, Any]:
    return {
        "model": MODEL_NAME,  # the model we request (the only one used)
        "provider_deployment": resp.model_name,  # Portkey's name for the deployment that served it
        "text": " ".join(p.content for p in resp.parts if isinstance(p, TextPart)) or None,
        "tool_calls": [{"tool": p.tool_name, "args": p.args_as_dict()} for p in resp.parts if isinstance(p, ToolCallPart)],
        "usage": {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        "finish_reason": resp.finish_reason,
    }


async def run_agent(agent_id: AgentId, prompt: str, state: RunState, chain: tuple[AgentId, ...]) -> dict[str, Any]:
    """Run one agent's loop to completion. Sub-agent failures come back as status 'error'; the Boss re-raises."""
    deps = AgentDeps(state=state, chain=chain)
    profile = deps.profile
    is_lead = agent_id == "boss" and deps.depth == 0
    tools = [ask_agent] if deps.depth < MAX_DEPTH else []
    instructions = (PROMPTS_DIR / profile.prompt_file).read_text(encoding="utf-8") + "\n\n" + _team_section(deps)
    agent = Agent(
        build_model(),
        name=profile.name,
        deps_type=AgentDeps,
        output_type=TicketDecision if is_lead else str,
        instructions=instructions,
        toolsets=[toolset_for(profile)],
        tools=tools,
        model_settings=MODEL_SETTINGS,
    )
    limits = UsageLimits(request_limit=profile.request_limit, total_tokens_limit=profile.total_tokens_limit)
    deps.log("agent_started", prompt=prompt, mcp_tools=list(profile.mcp_tools), can_delegate=bool(tools),
             limits={"requests": profile.request_limit, "total_tokens": profile.total_tokens_limit, "asks": profile.ask_limit})
    try:
        async with agent.iter(prompt, deps=deps, usage_limits=limits) as run:
            step = 0
            async for node in run:
                if Agent.is_model_request_node(node):
                    step += 1
                    deps.log("model_request", step=step, **_summarize_request(node))
                elif Agent.is_call_tools_node(node):
                    deps.log("model_response", step=step, **_summarize_response(node.model_response))
            output, usage = run.result.output, run.usage
        for key in state.usage:
            state.usage[key] += getattr(usage, key) or 0
        dumped = output.model_dump() if isinstance(output, TicketDecision) else output
        deps.log("agent_finished", output=dumped, usage={k: getattr(usage, k) for k in state.usage})
        return {"output": output, "status": "done"}
    except Exception as exc:
        deps.log("agent_failed", error=f"{type(exc).__name__}: {exc}")
        if is_lead:
            raise
        return {"output": f"{profile.name} could not finish: {type(exc).__name__}: {exc}", "status": "error"}


# ------------------------------------------------------- entry points ---

async def _shop_date() -> str | None:
    desk = await system_call("get_desk")
    return desk.get("date_today") if isinstance(desk, dict) else None


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def work_ticket(ticket_id: int, instruction: str | None = None, run_id: str | None = None,
                      listeners: list[asyncio.Queue] | None = None) -> TicketRun:
    """Have the Boss work one ticket (delegating as needed) and record its decision."""
    state = RunState(run_id=run_id or new_run_id(), ticket_id=ticket_id, listeners=listeners or [])
    async with TOOLSET:  # one MCP server connection for the whole run
        state.shop_date = await _shop_date()
        state.log("system", 0, (), "run_started", ticket_id=ticket_id, instruction=instruction)
        prompt = f"Work ticket #{ticket_id}."
        if instruction:
            prompt += f"\n\nUpdate from the operations desk: {instruction}"
        try:
            result = await run_agent("boss", prompt, state, ("boss",))
        except Exception as exc:
            state.log("system", 0, (), "run_failed", error=f"{type(exc).__name__}: {exc}", usage=state.usage)
            return TicketRun(run_id=state.run_id, ticket_id=ticket_id, error=str(exc),
                             delegations=state.delegations, usage=state.usage)
        decision: TicketDecision = result["output"]
        state.log("system", 0, (), "run_finished", decision=decision.model_dump(), usage=state.usage,
                  delegations=len(state.delegations))
    return TicketRun(run_id=state.run_id, ticket_id=ticket_id, decision=decision,
                     delegations=state.delegations, usage=state.usage)


async def open_ticket_ids() -> list[int]:
    board = await system_call("list_open_tickets")
    return [t["id"] for t in board.get("tickets", [])]


async def decide_payment(request_id: int, decision: str, approver: str, note: str = "") -> dict[str, Any]:
    """A human approves or rejects a payment request. Approving also pays it: this is the
    only path by which cash leaves the shop. Agents only prepare requests.

    Returns {"request", "decision", "payment"}; "payment" holds the pay result (or the
    refusal, e.g. not enough cash), and is None for rejections.
    """
    requests = (await system_call("list_approval_requests", {}))["requests"]
    request = next((r for r in requests if r["id"] == request_id), None)
    if request is None:
        return {"error": f"No approval request with id={request_id}"}
    state = RunState(run_id=new_run_id(), ticket_id=request["ticket_id"], shop_date=await _shop_date())

    if request["status"] == "pending":
        result = await human_call("decide_approval", {"request_id": request_id, "decision": decision,
                                                     "approver": approver, "note": note})
        state.log("human", 0, (), "human_decision", request_id=request_id, decision=decision,
                  approver=approver, note=note, result=result)
        if "error" in result:
            return {"error": result["error"], "request": request}
    elif not (request["status"] == "approved" and decision == "approved"):
        # Already decided. The one retry allowed: paying an approved request a refusal left unpaid.
        return {"error": f"Request #{request_id} is already {request['status']}.", "request": request}

    payment = None
    if decision == "approved":
        payment = await human_call("pay_approved_request", {"request_id": request_id})
        state.log("human", 0, (), "payment_refused" if "error" in payment else "payment_made",
                  request_id=request_id, approver=approver, result=payment)
    updated = next(r for r in (await system_call("list_approval_requests", {}))["requests"] if r["id"] == request_id)
    return {"request": updated, "decision": decision, "payment": payment}


async def reset_database(requested_by: str) -> dict[str, Any]:
    """Restore the working DB from the original before a full run (human action)."""
    result = await human_call("reset_working_database", {})
    state = RunState(run_id=new_run_id(), ticket_id=None, shop_date=await _shop_date())
    state.log("human", 0, (), "database_reset", requested_by=requested_by, result=result)
    return result


def resume_note(decided: dict[str, Any], approver: str) -> str:
    """What the Boss is told when a ticket is resumed after a human decision."""
    req, pay = decided["request"], decided.get("payment")
    note = f"A human ({approver}) {decided['decision']} payment request #{req['id']} (${req['amount']:,.2f} to {req['payee']})."
    if pay and "error" not in pay:
        note += f" The dashboard paid it: payment #{pay['payment_id']}, checking is now ${pay['balance_after']:,.2f}."
    elif pay:
        note += f" The payment was refused: {pay['error']}"
    return note


# ---------------------------------------------------------------- CLI ---

def _print_run(run: TicketRun) -> None:
    print(f"\n=== Ticket {run.ticket_id} (run {run.run_id}) ===")
    if run.error:
        print("ERROR:", run.error)
    else:
        print(run.decision.model_dump_json(indent=2))
    for d in run.delegations:
        print(f"  {d.from_agent} -> {d.to_agent} [{d.status}]: {d.question[:100]}")
    print("  usage:", run.usage)


async def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    ap.add_argument("tickets", nargs="*", type=int)
    ap.add_argument("--all", action="store_true", help="work every open ticket, in id order")
    ap.add_argument("--reset", action="store_true", help="restore the working DB from the original first")
    ap.add_argument("--approve", type=int, metavar="REQUEST_ID")
    ap.add_argument("--reject", type=int, metavar="REQUEST_ID")
    ap.add_argument("--approver", default="")
    ap.add_argument("--resume", action="store_true", help="after --approve/--reject, have the Boss finish that ticket")
    args = ap.parse_args()

    if args.reset:
        print(await reset_database(args.approver or "cli"))
    for req, decision in ((args.approve, "approved"), (args.reject, "rejected")):
        if req:
            res = await decide_payment(req, decision, args.approver)
            print(res)
            if args.resume and "error" not in res:
                _print_run(await work_ticket(res["request"]["ticket_id"], resume_note(res, args.approver)))
    ids = await open_ticket_ids() if args.all else args.tickets
    for tid in ids:
        _print_run(await work_ticket(tid))


if __name__ == "__main__":
    asyncio.run(_main())
