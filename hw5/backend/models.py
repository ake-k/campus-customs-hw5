"""Data types shared by the agent team, the audit trail, and the API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentId = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "awaiting_approval", "waiting_on_vendor", "resolved", "declined"]


class AgentProfile(BaseModel):
    """Who an agent is and what it may touch. One per role file in backend/agents/."""

    id: AgentId
    name: str
    role: str  # one line, shown to teammates so they know whom to ask
    prompt_file: str  # file name in backend/prompts/
    mcp_tools: tuple[str, ...]  # the only MCP tools this agent can see or call
    request_limit: int  # max model requests in one run of this agent
    ask_limit: int  # max delegations this agent may make in one run
    total_tokens_limit: int  # max tokens in one run of this agent


class Delegation(BaseModel):
    """One ask from one agent to another (any agent may ask any other)."""

    from_agent: AgentId
    to_agent: AgentId
    question: str
    depth: int
    status: Literal["running", "done", "error", "blocked"] = "running"
    reply: str | None = None


class TicketDecision(BaseModel):
    """The Boss's final call on a ticket: the structured output of a Boss run."""

    ticket_id: int
    status: TicketStatus = Field(description="The status you set on the board with update_ticket.")
    assigned_to: list[AgentId] = Field(description="Teammates who worked on this ticket.")
    decision: str = Field(description="Your final call in 1-3 sentences, with the key numbers from the tools.")
    actions_taken: list[str] = Field(default_factory=list, description="What the team actually did (tool calls that changed the board).")
    approval_request_ids: list[int] = Field(default_factory=list, description="Payment/PO requests waiting on or decided by a human.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts saved on the board.")
    needs_human: str | None = Field(default=None, description="What a human must do next, if anything.")


class TicketRun(BaseModel):
    """Everything one run of the team on one ticket produced."""

    run_id: str
    ticket_id: int
    decision: TicketDecision | None = None
    error: str | None = None
    delegations: list[Delegation] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    """One line of output/audit_trail.json: one step of one agent loop."""

    seq: int  # order within the run
    ts: str  # wall-clock UTC time the step was recorded
    shop_date: str | None  # desk.date_today at the time
    run_id: str
    ticket_id: int | None
    agent: AgentId | Literal["human", "system"]
    depth: int  # 0 = Boss at the top; +1 per delegation
    chain: list[str]  # who asked whom to reach this agent
    event: Literal[
        "run_started", "run_finished", "run_failed",
        "agent_started", "agent_finished", "agent_failed",
        "model_request", "model_response",
        "tool_call", "tool_result", "tool_denied",
        "delegation_started", "delegation_finished", "delegation_blocked",
        "human_decision", "payment_made", "payment_refused", "database_reset",
    ]
    data: dict[str, Any] = Field(default_factory=dict)
