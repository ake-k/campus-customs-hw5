"""Accounting: watches cash and invoices, checks margins, and prepares payments / POs for human approval.

Accounting only prepares payments. Cash moves when a human approves on the dashboard (POST /api/approvals/{id}/approve)."""

from models import AgentProfile

PROFILE = AgentProfile(
    id="accounting",
    name="Accounting",
    role="Cash and invoices: cash position, margins and discount pricing, and files payment / purchase-order requests for a human to approve (approving on the dashboard is what pays).",
    prompt_file="accounting.md",
    mcp_tools=(
        "get_desk",
        "get_ticket",
        "get_cash_position",
        "get_invoice_status",
        "get_lease_and_cash",
        "check_stock_and_margin",
        "quote_discount",
        "list_vendors",
        "list_approval_requests",
        "request_payment_approval",
    ),
    request_limit=12,
    ask_limit=2,
    total_tokens_limit=80_000,
)
