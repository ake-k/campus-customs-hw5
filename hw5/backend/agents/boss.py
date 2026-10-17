"""Boss: reads each ticket, decides who should work on it, and makes final calls."""

from models import AgentProfile

PROFILE = AgentProfile(
    id="boss",
    name="Boss",
    role="Operations lead: reads each ticket, routes it to the right teammates, makes the final call, and records it on the board.",
    prompt_file="boss.md",
    mcp_tools=(
        "get_desk",
        "list_open_tickets",
        "get_ticket",
        "get_cash_position",
        "list_approval_requests",
        "update_ticket",
    ),
    request_limit=20,
    ask_limit=6,
    total_tokens_limit=150_000,
)
