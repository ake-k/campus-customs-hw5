"""Customer Service: drafts messages for customers. Drafts stay on the board and are never sent."""

from models import AgentProfile

PROFILE = AgentProfile(
    id="customer_service",
    name="Customer Service",
    role="Customer messages: writes honest, friendly replies to requesters and saves them as drafts on the board (never sent).",
    prompt_file="customer_service.md",
    mcp_tools=(
        "get_desk",
        "get_ticket",
        "check_stock_and_margin",
        "quote_discount",
        "save_customer_draft",
    ),
    request_limit=8,
    ask_limit=2,
    total_tokens_limit=50_000,
)
