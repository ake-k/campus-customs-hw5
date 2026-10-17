"""The backend's single connection to the Campus Customs MCP server.

All shop facts and all database changes go through this MCP toolset. There is
no second tools layer. Each agent sees only the MCP tools its role allows,
every call is written to the audit trail, and the calling agent's id is stamped
on writes (agents can't claim to be someone else).

Human-only tools (approving and paying, resetting the database) need a key that
is generated fresh each time the backend starts. It is passed to the MCP server
process and used only by human_call(); it never appears in a prompt, so no
agent can approve a payment.
"""

from __future__ import annotations

import os
import secrets
import sys
import time
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset

from config import MCP_SERVER_SCRIPT, REPO_ROOT, WORKING_DB
from models import AgentProfile

HUMAN_APPROVAL_KEY = secrets.token_urlsafe(32)
HUMAN_ONLY_TOOLS = frozenset({"decide_approval", "pay_approved_request", "reset_working_database"})
ACTING_AGENT_TOOLS = frozenset({"update_ticket", "request_payment_approval", "save_customer_draft"})


async def _process_tool_call(ctx: RunContext[Any], call_tool: CallToolFunc, name: str, args: dict[str, Any]) -> Any:
    """Runs around every MCP call an agent makes: permission check, identity stamp, audit."""
    deps = ctx.deps
    profile: AgentProfile = deps.profile
    if name in HUMAN_ONLY_TOOLS or name not in profile.mcp_tools:
        reason = f"{profile.name} is not allowed to call {name}."
        deps.log("tool_denied", tool=name, args=args, reason=reason)
        return {"error": f"Refused: {reason}"}
    if name in ACTING_AGENT_TOOLS:
        args = {**args, "acting_agent": profile.id}
    deps.log("tool_call", tool=name, args=args)
    started = time.perf_counter()
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        deps.log("tool_result", tool=name, ok=False, error=f"{type(exc).__name__}: {exc}",
                 ms=round((time.perf_counter() - started) * 1000))
        raise
    ok = not (isinstance(result, dict) and "error" in result)
    deps.log("tool_result", tool=name, ok=ok, result=result, ms=round((time.perf_counter() - started) * 1000))
    return result


TOOLSET = MCPToolset(
    Client(
        StdioTransport(
            command=sys.executable,
            args=[str(MCP_SERVER_SCRIPT)],
            env={
                "CC_DB_PATH": str(WORKING_DB),
                "CC_HUMAN_APPROVAL_KEY": HUMAN_APPROVAL_KEY,
                "PATH": os.environ.get("PATH", ""),
            },
            cwd=str(REPO_ROOT),
            keep_alive=True,
        )
    ),
    id="campus-customs",
    process_tool_call=_process_tool_call,
)


def toolset_for(profile: AgentProfile):
    """The slice of the MCP server one agent can see: only its role's tools, never human-only ones."""
    allowed = frozenset(profile.mcp_tools) - HUMAN_ONLY_TOOLS
    return TOOLSET.filtered(lambda ctx, tool_def: tool_def.name in allowed)


async def system_call(name: str, args: dict[str, Any] | None = None) -> Any:
    """Read-only lookups the backend itself needs (e.g. the shop date for the audit trail)."""
    if name in HUMAN_ONLY_TOOLS:
        raise PermissionError(f"{name} is human-only; use human_call()")
    async with TOOLSET:
        return await TOOLSET.direct_call_tool(name, args or {})


async def human_call(name: str, args: dict[str, Any]) -> Any:
    """Only for actions a person takes on the dashboard (approve/reject and pay, reset the DB)."""
    if name not in HUMAN_ONLY_TOOLS:
        raise PermissionError(f"{name} is not a human-only tool")
    async with TOOLSET:
        return await TOOLSET.direct_call_tool(name, {**args, "approval_key": HUMAN_APPROVAL_KEY})
