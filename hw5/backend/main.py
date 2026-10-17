"""Campus Customs operations API: the backend the React dashboard calls.

Start from hw5/backend/:
    uvicorn main:app --reload --port 8000

Every shop fact comes from the MCP server (through mcp_link). Agents only
prepare payments; POST /api/approvals/{id}/approve is the one route that moves
cash, and only after a named human approves.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.team import decide_payment, new_run_id, reset_database, resume_note, work_ticket
from config import AUDIT_TRAIL, MODEL_NAME, WORKING_DB
from mcp_link import TOOLSET, system_call

# One team run at a time: tickets compete for the same cash, so runs go in order.
TEAM_LOCK = asyncio.Lock()
RUNS: dict[str, dict[str, Any]] = {}  # run_id -> status/result, newest last (this process only)
_TASKS: set[asyncio.Task] = set()  # strong references so background runs aren't garbage-collected


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with TOOLSET:  # keep one MCP server process for the life of the API
        yield


app = FastAPI(title="Campus Customs Operations API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    # The Vite dashboard (npm run dev) is served from http://localhost:5173. Any local port is
    # allowed so a second dev copy (e.g. a test desk on 5174) works; nothing off this machine is.
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------- bodies ---

class RunRequest(BaseModel):
    instruction: str | None = Field(default=None, description="Optional note for the Boss, e.g. what changed.")


class ApprovalBody(BaseModel):
    approver: str = Field(min_length=2, description="Full name of the person approving or rejecting.")
    note: str = ""
    resume: bool = Field(default=True, description="Have the Boss finish the ticket after the decision.")


class ResetBody(BaseModel):
    requested_by: str = Field(min_length=2)


# ------------------------------------------------------------ helpers ---

def _check(result: Any, status: int = 400) -> Any:
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status, result["error"])
    return result


def _team_busy() -> bool:
    return TEAM_LOCK.locked() or any(r["status"] in ("queued", "running") for r in RUNS.values())


async def _run_in_background(run_id: str, ticket_id: int, instruction: str | None) -> None:
    run = RUNS[run_id]
    async with TEAM_LOCK:
        run["status"] = "running"
        try:
            result = await work_ticket(ticket_id, instruction, run_id=run_id)
            run["status"] = "error" if result.error else "done"
            run["result"] = result.model_dump()
        except Exception as exc:  # never let a background task die silently
            run["status"], run["result"] = "error", {"error": f"{type(exc).__name__}: {exc}"}


def _start_run(ticket_id: int, instruction: str | None) -> dict[str, Any]:
    run_id = new_run_id()
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "instruction": instruction,
                    "status": "queued", "result": None}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id, instruction))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return RUNS[run_id]


def _summarize(e: dict[str, Any]) -> str:
    """One readable line per audit event, for the dashboard feed."""
    d, who = e.get("data", {}), e["agent"]
    match e["event"]:
        case "model_response":
            calls = ", ".join(c["tool"] for c in d.get("tool_calls", []))
            said = (d.get("text") or "").strip()
            if said and calls:
                return f"{who} said: {said} · then called {calls}"
            return f"{who} said: {said}" if said else f"{who} decided to call {calls}"
        case "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in d.get("args", {}).items() if k != "acting_agent")
            return f"{who} → {d.get('tool')}({args})"
        case "tool_result":
            return f"{d.get('tool')} → {who}: {'ok' if d.get('ok') else 'error'} ({d.get('ms')} ms)"
        case "tool_denied":
            return f"{who} was refused {d.get('tool')}: {d.get('reason')}"
        case "delegation_started":
            return f"{who} asked {d.get('to_agent')}: {d.get('question')}"
        case "delegation_finished":
            return f"{d.get('to_agent')} replied to {who}: {d.get('reply')}"
        case "delegation_blocked":
            return f"{who} could not ask {d.get('to_agent')}: {d.get('reason')}"
        case "agent_started":
            return f"{who} started: {d.get('prompt')}"
        case "agent_finished":
            out = d.get("output")
            return f"{who} finished: {out.get('decision') if isinstance(out, dict) else out}"
        case "agent_failed" | "run_failed":
            return f"{who} failed: {d.get('error')}"
        case "human_decision":
            return f"{d.get('approver')} {d.get('decision')} request #{d.get('request_id')}"
        case "payment_made":
            r = d.get("result", {})
            return f"Paid request #{d.get('request_id')}: ${r.get('amount', 0):,.2f} to {r.get('payee')} · checking now ${r.get('balance_after', 0):,.2f}"
        case "payment_refused":
            return f"Payment for request #{d.get('request_id')} refused: {d.get('result', {}).get('error')}"
        case "database_reset":
            return f"Database reset by {d.get('requested_by')}"
        case "run_started":
            return f"Run started on ticket {d.get('ticket_id')}"
        case "run_finished":
            return f"Run finished: {d.get('decision', {}).get('status')} · {d.get('decision', {}).get('decision')}"
        case "model_request":
            return f"{who} → model (step {d.get('step')})"
    return e["event"]


def _read_audit() -> list[dict[str, Any]]:
    if not AUDIT_TRAIL.exists() or not AUDIT_TRAIL.stat().st_size:
        return []
    try:
        return json.loads(AUDIT_TRAIL.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # mid-write is prevented by atomic replace, but be safe
        return []


# ------------------------------------------------------------- routes ---

@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Liveness plus the facts the dashboard header shows."""
    desk = await system_call("get_desk")
    return {"ok": True, "model": MODEL_NAME, "database": WORKING_DB.name, "shop_date": desk.get("date_today"),
            "team_busy": _team_busy()}


@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    """All tickets with status and whether each is still open."""
    board = _check(await system_call("list_tickets"))
    active = {r["ticket_id"]: r["status"] for r in RUNS.values() if r["status"] in ("queued", "running")}
    for t in board["tickets"]:
        t["state"] = "open" if t["is_open"] else "resolved"
        t["run_status"] = active.get(t["id"])
    return board


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket with its linked rows and board history (updates, requests, drafts)."""
    return _check(await system_call("get_ticket", {"ticket_id": ticket_id}), 404)


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, body: RunRequest | None = None) -> dict[str, Any]:
    """Start the agent team on a ticket. Runs in the background; poll /api/events and /api/runs/{run_id}."""
    _check(await system_call("get_ticket", {"ticket_id": ticket_id}), 404)
    if any(r["ticket_id"] == ticket_id and r["status"] in ("queued", "running") for r in RUNS.values()):
        raise HTTPException(409, f"Ticket {ticket_id} already has a run in progress.")
    return _start_run(ticket_id, body.instruction if body else None)


@app.get("/api/runs")
async def list_runs() -> list[dict[str, Any]]:
    """Runs started by this server process, newest first."""
    return list(reversed(RUNS.values()))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Status of one run (queued / running / done / error) and the Boss's decision when finished."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} in this server session.")
    return RUNS[run_id]


@app.get("/api/events")
async def events(
    after: int = Query(-1, description="Return events with index greater than this (use the last 'cursor')."),
    limit: int = Query(200, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
    detail: bool = Query(False, description="Include full event data, not just the summary line."),
) -> dict[str, Any]:
    """Recent agent events from the audit trail: what each agent said, asked, and which tools it used."""
    all_events = _read_audit()
    rows = []
    for index, e in enumerate(all_events):
        if index <= after or (ticket_id is not None and e.get("ticket_id") != ticket_id) or (run_id and e.get("run_id") != run_id):
            continue
        row = {"index": index, "ts": e["ts"], "run_id": e["run_id"], "ticket_id": e["ticket_id"], "agent": e["agent"],
               "depth": e["depth"], "event": e["event"], "summary": _summarize(e)}
        if detail:
            row["data"] = e["data"]
        rows.append(row)
    rows = rows[-limit:]
    return {"events": rows, "cursor": len(all_events) - 1, "team_busy": _team_busy()}


@app.get("/api/approvals")
async def approvals(status: str = "", ticket_id: int = 0) -> dict[str, Any]:
    """Payment / purchase-order requests the agents prepared, and their human decision."""
    return await system_call("list_approval_requests", {"status": status, "ticket_id": ticket_id})


async def _decide(request_id: int, decision: Literal["approved", "rejected"], body: ApprovalBody) -> dict[str, Any]:
    if body.approver.strip().lower() in {"boss", "inventory", "accounting", "facilities", "customer service", "customer_service"}:
        raise HTTPException(400, "The approver must be a person, not an agent.")
    result = await decide_payment(request_id, decision, body.approver.strip(), body.note)
    _check(result, 404 if "No approval request" in result.get("error", "") else 409)
    resumed = None
    if body.resume:
        resumed = _start_run(result["request"]["ticket_id"], resume_note(result, body.approver.strip()))
    payment = result["payment"]
    if payment and "error" in payment:  # approved, but the pay tool refused (e.g. not enough cash)
        return {**result, "paid": False, "resumed_run": resumed}
    return {**result, "paid": bool(payment), "resumed_run": resumed}


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: ApprovalBody) -> dict[str, Any]:
    """A human approves a prepared payment or purchase order, and this route pays it.
    The only route that changes cash. It refuses if cash would go negative or the vendor is blocked."""
    return await _decide(request_id, "approved", body)


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: ApprovalBody) -> dict[str, Any]:
    """A human rejects a prepared payment or purchase order. No cash moves."""
    return await _decide(request_id, "rejected", body)


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts, plus what is waiting on approval."""
    pos = _check(await system_call("get_cash_position"))
    checking = next((a for a in pos["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(500, "No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "shop_date": pos["today"],
        "unpaid_requests_total": pos["unpaid_payment_requests_total"],
        "balance_after_unpaid_requests": round(checking["balance"] - pos["unpaid_payment_requests_total"], 2),
        "payments": pos["payments_made"],
    }


@app.post("/api/reset")
async def reset(body: ResetBody) -> dict[str, Any]:
    """Restore the working DB from the original campus_customs.db for a fresh run.
    The audit trail is kept (append-only); a reset event is added to it."""
    if _team_busy():
        raise HTTPException(409, "The team is working on a ticket. Wait for it to finish before resetting.")
    result = _check(await reset_database(body.requested_by.strip()), 500)
    RUNS.clear()
    return result
