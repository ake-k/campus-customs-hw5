"""Facilities: handles the shop space side, including leases, rent, and due dates."""

from models import AgentProfile

PROFILE = AgentProfile(
    id="facilities",
    name="Facilities",
    role="Shop space: leases, landlord, rent amount and due dates, and whether a rent notice matches the lease.",
    prompt_file="facilities.md",
    mcp_tools=(
        "get_desk",
        "get_ticket",
        "get_lease_and_cash",
        "list_approval_requests",
    ),
    request_limit=8,
    ask_limit=2,
    total_tokens_limit=50_000,
)
