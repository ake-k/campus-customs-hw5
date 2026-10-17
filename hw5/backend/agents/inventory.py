"""Inventory: checks stock by SKU and size, spots shortfalls, and finds which vendor can restock."""

from models import AgentProfile

PROFILE = AgentProfile(
    id="inventory",
    name="Inventory",
    role="Stock specialist: on-hand stock by SKU and size, shortfalls, which vendor can restock, whether that vendor is blocked, and when it could arrive.",
    prompt_file="inventory.md",
    mcp_tools=(
        "get_desk",
        "get_ticket",
        "check_stock_and_margin",
        "list_vendors",
        "get_invoice_status",
    ),
    request_limit=10,
    ask_limit=2,
    total_tokens_limit=60_000,
)
