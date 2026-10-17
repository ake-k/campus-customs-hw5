"""Campus Customs MCP server.

Exposes the shop database to the agent team as MCP tools. Every tool works on
the WORKING copy (data/campus_customs_new.db); the original
data/campus_customs.db is only ever read, by the reset tool, to restore the
working copy.

Rules baked into the tools:
- "Today" is desk.date_today, never the computer's clock.
- Return only what is in the database (plus simple arithmetic on it). Amounts
  for payments are looked up here, never taken from the caller. If a row is
  missing, return an error instead of guessing.
- Payments need a human: decide_approval records the decision and
  pay_approved_request moves the cash. Both need the human approval key the
  backend holds (used only by its approve route). Agents never get that key,
  so agents can prepare payments but cannot approve or make them.
- The pay tool refuses if cash would go negative, and refuses purchase orders to
  a vendor that still has an open (unpaid) invoice.
- Nothing is sent: customer messages are saved as drafts on the board.
"""

from __future__ import annotations

import calendar
import hmac
import os
import shutil
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = REPO_ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.getenv("CC_DB_PATH", "data/campus_customs_new.db"))
if not DB_PATH.is_absolute():
    DB_PATH = REPO_ROOT / DB_PATH
if DB_PATH.resolve() == ORIGINAL_DB.resolve():
    raise SystemExit("CC_DB_PATH points at the original database; use the working copy.")

# Set by the backend when it launches this server. Without it, approvals and
# resets are refused, so no MCP client can approve a payment on its own.
HUMAN_APPROVAL_KEY = os.getenv("CC_HUMAN_APPROVAL_KEY", "")

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}
TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "waiting_on_vendor", "resolved", "declined")
CLOSED_STATUSES = ("resolved", "declined")

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Tools for the Campus Customs shop database. Use desk.date_today as today. "
        "Only report values these tools return; never invent data. Payments need human approval."
    ),
)

# Board tables the agents write to. They live only in the working copy and are
# created on first use, so a reset (which restores the original file) clears them.
_BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoices.id or leases.id (NULL for purchase orders)
    payee TEXT NOT NULL,
    vendor_id INTEGER,
    sku TEXT, size TEXT, qty INTEGER, unit_cost REAL,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | approved | rejected | paid
    decided_by TEXT, decided_at TEXT, decision_note TEXT,
    payment_id INTEGER,
    expected_arrival TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


# ---------------------------------------------------------------- helpers ---

def _connect(read_only: bool = True) -> closing[sqlite3.Connection]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    if not read_only:
        conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
        conn.executescript(_BOARD_SCHEMA)
    else:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return closing(conn)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _today(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("desk.date_today is missing")
    return row["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _board_rows(conn: sqlite3.Connection, table: str, ticket_id: int) -> list[dict]:
    if not _has_table(conn, table):
        return []
    return _rows(conn, f"SELECT * FROM {table} WHERE ticket_id = ? ORDER BY id", (ticket_id,))


def _open_invoices(conn: sqlite3.Connection, vendor_id: int | None = None) -> list[dict]:
    sql = """SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount, i.due_date, i.description
             FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"""
    params: tuple = ()
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"
        params = (vendor_id,)
    return _rows(conn, sql + " ORDER BY i.due_date", params)


def _human_key_ok(key: str) -> bool:
    return bool(HUMAN_APPROVAL_KEY) and hmac.compare_digest(key, HUMAN_APPROVAL_KEY)


# ------------------------------------------------------- desk and tickets ---

@mcp.tool
def get_desk() -> dict:
    """Return the shop's 'today' (desk.date_today) and desk notes. Use this
    date for every overdue / due-soon / arrival calculation."""
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
    return {"date_today": row["date_today"], "notes": row["notes"]} if row else {"error": "desk is empty"}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket on the board that is not resolved or declined,
    with its type, requester, subject, and linked sku/size/qty/lease/invoice."""
    with _connect() as conn:
        today = _today(conn)
        tickets = _rows(
            conn,
            f"SELECT * FROM tickets WHERE status NOT IN ({','.join('?' * len(CLOSED_STATUSES))}) ORDER BY id",
            CLOSED_STATUSES,
        )
    return {"today": today, "count": len(tickets), "tickets": tickets}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and closed) with its status, whether it is still
    open, and counts of its board items (updates, payment requests, drafts)."""
    with _connect() as conn:
        today = _today(conn)
        tickets = _rows(conn, "SELECT * FROM tickets ORDER BY id")
        for t in tickets:
            t["is_open"] = t["status"] not in CLOSED_STATUSES
            for table in ("ticket_updates", "approval_requests", "drafts"):
                t[f"{table}_count"] = len(_board_rows(conn, table, t["id"]))
            pending = [r for r in _board_rows(conn, "approval_requests", t["id"]) if r["status"] == "pending"]
            t["pending_approvals"] = len(pending)
    return {"today": today, "tickets": tickets}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket with everything it links to: the inventory row and
    price for its sku/size, its lease, its invoice (with vendor), plus the
    board history for it (status updates, approval requests, customer drafts)."""
    with _connect() as conn:
        today = _today(conn)
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket with id={ticket_id}"}
        ticket = dict(t)
        linked: dict = {}
        if ticket["sku"]:
            linked["inventory"] = _rows(conn, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (ticket["sku"],))
            linked["pricing"] = _rows(conn, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
        if ticket["lease_id"] is not None:
            linked["lease"] = _rows(conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],))
        if ticket["invoice_id"] is not None:
            linked["invoice"] = _rows(
                conn,
                """SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days
                   FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?""",
                (ticket["invoice_id"],),
            )
        board = {
            "updates": _board_rows(conn, "ticket_updates", ticket_id),
            "approval_requests": _board_rows(conn, "approval_requests", ticket_id),
            "drafts": _board_rows(conn, "drafts", ticket_id),
        }
    return {"today": today, "ticket": ticket, "linked": linked, "board": board}


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "awaiting_approval", "waiting_on_vendor", "resolved", "declined"],
    note: str,
    acting_agent: str = "",
) -> dict:
    """Set a ticket's status and add a note to its board history (who did
    what, and why). The original ticket request is kept unchanged."""
    if not note.strip():
        return {"error": "A note explaining the status change is required."}
    with _connect(read_only=False) as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}"}
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        cur = conn.execute(
            "INSERT INTO ticket_updates (ticket_id, status, note, author, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, status, note.strip(), acting_agent or "unknown", today),
        )
        conn.execute("COMMIT")
    return {"ticket_id": ticket_id, "status": status, "update_id": cur.lastrowid, "date": today}


# ---------------------------------------------------------- inventory side ---

@mcp.tool
def check_stock_and_margin(sku: str, size: str, qty_needed: int) -> dict:
    """Check on-hand stock for one SKU and size against a requested quantity,
    and return its unit cost, list price, and per-unit margin.

    Use for orders and discount requests: shows the shortfall and the cost
    floor that any discount must stay above.
    """
    with _connect() as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            return {"error": f"No inventory row for sku={sku!r}, size={size!r}"}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if price is None:
            return {"error": f"No pricing row for sku={sku!r}"}

    on_hand = item["qty"]
    unit_cost, list_price = price["unit_cost"], price["list_price"]
    return {
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "location": item["location"],
        "qty_on_hand": on_hand,
        "qty_needed": qty_needed,
        "can_fill_from_stock": on_hand >= qty_needed,
        "shortfall": max(qty_needed - on_hand, 0),
        "unit_cost": unit_cost,
        "list_price": list_price,
        "margin_per_unit_at_list": round(list_price - unit_cost, 2),
        "margin_pct_at_list": round((list_price - unit_cost) / list_price * 100, 1),
        "order_total_at_list": round(list_price * qty_needed, 2),
    }


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty and lead time, and whether it is
    blocked from shipping because it still has an open unpaid invoice.
    Expected arrival assumes an order placed today (desk.date_today)."""
    with _connect() as conn:
        today = _today(conn)
        vendors = _rows(conn, "SELECT id, name, specialty, lead_days FROM vendors ORDER BY id")
        for v in vendors:
            open_inv = _open_invoices(conn, v["id"])
            v["open_invoices"] = open_inv
            v["open_invoice_total"] = round(sum(i["amount"] for i in open_inv), 2)
            v["blocked_from_shipping"] = bool(open_inv)
            v["arrival_if_ordered_today"] = (date.fromisoformat(today) + timedelta(days=v["lead_days"])).isoformat()
    return {"today": today, "vendors": vendors}


# ------------------------------------------------------------- money side ---

@mcp.tool
def get_invoice_status(invoice_id: int) -> dict:
    """Look up one vendor invoice: amount, due date, status, days overdue
    (as of desk.date_today), and the vendor's specialty and lead time.

    An open invoice means that vendor will NOT ship new product until it is
    paid, so this tells you whether a restock is blocked.
    """
    with _connect() as conn:
        today = _today(conn)
        row = conn.execute(
            """
            SELECT i.id, i.amount, i.due_date, i.status, i.description,
                   v.id AS vendor_id, v.name AS vendor_name, v.specialty, v.lead_days
            FROM invoices i JOIN vendors v ON v.id = i.vendor_id
            WHERE i.id = ?
            """,
            (invoice_id,),
        ).fetchone()
    if row is None:
        return {"error": f"No invoice with id={invoice_id}"}

    is_open = row["status"] == "open"
    days_past_due = _days_between(row["due_date"], today)
    return {
        "today": today,
        "invoice_id": row["id"],
        "description": row["description"],
        "amount": row["amount"],
        "due_date": row["due_date"],
        "status": row["status"],
        "is_overdue": is_open and days_past_due > 0,
        "days_overdue": max(days_past_due, 0) if is_open else 0,
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "vendor_specialty": row["specialty"],
        "vendor_lead_days": row["lead_days"],
        "vendor_blocked_from_shipping": is_open,
    }


@mcp.tool
def get_lease_and_cash(lease_id: int) -> dict:
    """Look up one lease's rent and next due date (with days until due as of
    desk.date_today) alongside the current cash balance, so you can tell
    whether rent is due and whether the shop can cover it.
    """
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}"}
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    days_until_due = _days_between(today, lease["next_due"])
    total_cash = sum(a["balance"] for a in accounts)
    return {
        "today": today,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "lease_notes": lease["notes"],
        "cash_accounts": [dict(a) for a in accounts],
        "total_cash": total_cash,
        "cash_covers_rent": total_cash >= lease["monthly_rent"],
        "cash_after_rent": round(total_cash - lease["monthly_rent"], 2),
    }


@mcp.tool
def get_cash_position() -> dict:
    """Show cash on hand against everything it is committed to: open vendor
    invoices (with days overdue), rent coming due, and payment requests that
    are pending or approved but not yet paid. No money comes in, so this is
    the full picture for deciding what the shop can afford."""
    with _connect() as conn:
        today = _today(conn)
        accounts = _rows(conn, "SELECT name, balance, date FROM cash_accounts")
        invoices = _open_invoices(conn)
        for i in invoices:
            i["days_overdue"] = max(_days_between(i["due_date"], today), 0)
        leases = _rows(conn, "SELECT id, space_name, landlord, monthly_rent, next_due FROM leases ORDER BY next_due")
        for lease in leases:
            lease["days_until_due"] = _days_between(today, lease["next_due"])
        requests = (
            _rows(conn, "SELECT id, ticket_id, kind, ref_id, payee, amount, status FROM approval_requests "
                        "WHERE status IN ('pending', 'approved') ORDER BY id")
            if _has_table(conn, "approval_requests") else []
        )
        paid = _rows(conn, "SELECT * FROM payments ORDER BY id")
    cash = round(sum(a["balance"] for a in accounts), 2)
    requested = round(sum(r["amount"] for r in requests), 2)
    return {
        "today": today,
        "cash_accounts": accounts,
        "total_cash": cash,
        "open_invoices": invoices,
        "open_invoice_total": round(sum(i["amount"] for i in invoices), 2),
        "leases": leases,
        "unpaid_payment_requests": requests,
        "unpaid_payment_requests_total": requested,
        "cash_after_unpaid_requests": round(cash - requested, 2),
        "payments_made": paid,
    }


@mcp.tool
def quote_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price a bulk order at a percentage off list price, and show the margin
    left per unit and in total. Flags any price at or below unit cost.
    This only calculates; it does not change any price."""
    if qty <= 0 or not 0 <= discount_pct < 100:
        return {"error": "qty must be > 0 and discount_pct must be between 0 and 100"}
    with _connect() as conn:
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if p is None:
        return {"error": f"No pricing row for sku={sku!r}"}
    unit_price = round(p["list_price"] * (1 - discount_pct / 100), 2)
    margin = round(unit_price - p["unit_cost"], 2)
    return {
        "sku": sku,
        "qty": qty,
        "discount_pct": discount_pct,
        "list_price": p["list_price"],
        "unit_cost": p["unit_cost"],
        "unit_price_after_discount": unit_price,
        "order_total": round(unit_price * qty, 2),
        "order_total_at_list": round(p["list_price"] * qty, 2),
        "margin_per_unit": margin,
        "margin_pct": round(margin / unit_price * 100, 1) if unit_price else None,
        "total_margin": round(margin * qty, 2),
        "at_or_below_cost": unit_price <= p["unit_cost"],
        "max_discount_pct_before_cost": round((1 - p["unit_cost"] / p["list_price"]) * 100, 1),
    }


@mcp.tool
def list_approval_requests(status: str = "", ticket_id: int = 0) -> dict:
    """List payment / purchase-order requests on the board. Optionally filter
    by status (pending, approved, rejected, paid) and/or ticket_id."""
    with _connect() as conn:
        if not _has_table(conn, "approval_requests"):
            return {"requests": []}
        sql, params = "SELECT * FROM approval_requests WHERE 1=1", []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if ticket_id:
            sql += " AND ticket_id = ?"
            params.append(ticket_id)
        return {"requests": _rows(conn, sql + " ORDER BY id", tuple(params))}


@mcp.tool
def request_payment_approval(
    ticket_id: int,
    kind: Literal["invoice", "rent", "purchase_order"],
    reason: str,
    invoice_id: int = 0,
    lease_id: int = 0,
    vendor_id: int = 0,
    sku: str = "",
    size: str = "",
    qty: int = 0,
    acting_agent: str = "",
) -> dict:
    """Put a payment or purchase order on the board for a HUMAN to approve.
    Nothing is paid here. The amount is looked up from the database, never
    supplied by the caller:
      - kind="invoice": pass invoice_id; amount = the invoice amount.
      - kind="rent": pass lease_id; amount = the lease's monthly_rent.
      - kind="purchase_order": pass vendor_id, sku, size, qty; amount = qty x pricing.unit_cost.
    """
    if not reason.strip():
        return {"error": "A reason is required so the human approver knows why."}
    with _connect(read_only=False) as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}"}
        fields: dict = {"vendor_id": None, "sku": None, "size": None, "qty": None, "unit_cost": None, "ref_id": None}
        warnings: list[str] = []
        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
                (invoice_id,),
            ).fetchone()
            if inv is None:
                return {"error": f"No invoice with id={invoice_id}"}
            if inv["status"] != "open":
                return {"error": f"Invoice {invoice_id} is already {inv['status']}; nothing to pay."}
            fields.update(ref_id=inv["id"], vendor_id=inv["vendor_id"])
            payee, amount = inv["vendor_name"], inv["amount"]
        elif kind == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
            if lease is None:
                return {"error": f"No lease with id={lease_id}"}
            fields.update(ref_id=lease["id"])
            payee, amount = lease["landlord"], lease["monthly_rent"]
        else:
            vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            item = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
            price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
            if vendor is None:
                return {"error": f"No vendor with id={vendor_id}"}
            if item is None or price is None:
                return {"error": f"No inventory/pricing row for sku={sku!r}, size={size!r}"}
            if qty <= 0:
                return {"error": "qty must be positive for a purchase order"}
            fields.update(vendor_id=vendor_id, sku=sku, size=size, qty=qty, unit_cost=price["unit_cost"])
            payee, amount = vendor["name"], round(qty * price["unit_cost"], 2)
            if _open_invoices(conn, vendor_id):
                warnings.append(f"{vendor['name']} has an open unpaid invoice; this PO cannot be paid or shipped until it is cleared.")

        dup = conn.execute(
            "SELECT id, status FROM approval_requests WHERE ticket_id = ? AND kind = ? AND status IN ('pending','approved') "
            "AND COALESCE(ref_id, -1) = COALESCE(?, -1) AND COALESCE(sku, '') = COALESCE(?, '') AND COALESCE(size, '') = COALESCE(?, '')",
            (ticket_id, kind, fields["ref_id"], fields["sku"], fields["size"]),
        ).fetchone()
        if dup is not None:
            return {"error": f"Request #{dup['id']} for this is already {dup['status']}; not creating a duplicate.",
                    "existing_request_id": dup["id"]}

        cash = conn.execute("SELECT COALESCE(SUM(balance), 0) AS c FROM cash_accounts").fetchone()["c"]
        committed = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS c FROM approval_requests WHERE status IN ('pending','approved')"
        ).fetchone()["c"]
        if amount > cash:
            return {"error": f"Refused: ${amount:,.2f} is more than the ${cash:,.2f} cash on hand."}
        if amount > cash - committed:
            warnings.append(
                f"Cash ${cash:,.2f} minus other unpaid requests ${committed:,.2f} leaves ${cash - committed:,.2f}, "
                f"less than this ${amount:,.2f}. Not every request can be paid."
            )

        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """INSERT INTO approval_requests
               (ticket_id, kind, ref_id, payee, vendor_id, sku, size, qty, unit_cost, amount, account,
                reason, requested_by, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'checking', ?, ?, 'pending', ?)""",
            (ticket_id, kind, fields["ref_id"], payee, fields["vendor_id"], fields["sku"], fields["size"],
             fields["qty"], fields["unit_cost"], amount, reason.strip(), acting_agent or "unknown", today),
        )
        conn.execute("COMMIT")
    return {
        "request_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "payee": payee,
        "amount": amount,
        "cash_on_hand": cash,
        "warnings": warnings,
        "next_step": "Waiting for a human on the dashboard. Approving it there also makes the payment; agents never pay.",
    }


@mcp.tool
def pay_approved_request(request_id: int, approval_key: str) -> dict:
    """HUMAN ONLY (dashboard approve route). Pay a request that a human has
    already approved. Requires the human approval key, so agents can prepare
    payments but never move cash. Refuses if the request is not approved, if
    cash would go negative, if the bill was already paid, or if a purchase
    order's vendor still has an open invoice. On success it updates
    cash_accounts, adds a payments row (approved_by = the human), and updates
    the related table: invoice -> paid, lease -> next_due moves one month,
    purchase order -> expected arrival from the vendor's lead_days."""
    if not _human_key_ok(approval_key):
        return {"error": "Refused: payments are made only by the dashboard after a human approves."}
    with _connect(read_only=False) as conn:
        today = _today(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
            if req is None:
                return {"error": f"No approval request with id={request_id}"}
            if req["status"] != "approved" or not req["decided_by"]:
                return {"error": f"Refused: request #{request_id} is '{req['status']}'. Only human-approved requests can be paid."}
            acct = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (req["account"],)).fetchone()
            if acct is None:
                return {"error": f"No cash account named {req['account']!r}"}
            amount = req["amount"]
            if acct["balance"] < amount:
                return {"error": f"Refused: ${amount:,.2f} would overdraw {req['account']} "
                                 f"(balance ${acct['balance']:,.2f}). No negative balances."}

            result: dict = {}
            if req["kind"] == "invoice":
                inv = conn.execute("SELECT status, amount FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
                if inv is None or inv["status"] != "open":
                    return {"error": f"Refused: invoice {req['ref_id']} is not open."}
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
                result["invoice"] = {"id": req["ref_id"], "status": "paid"}
            elif req["kind"] == "rent":
                lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
                if lease is None:
                    return {"error": f"Refused: lease {req['ref_id']} not found."}
                new_due = _add_month(lease["next_due"])
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
                result["lease"] = {"id": req["ref_id"], "paid_for_due_date": lease["next_due"], "next_due": new_due}
            else:
                blocking = _open_invoices(conn, req["vendor_id"])
                if blocking:
                    ids = ", ".join(str(i["id"]) for i in blocking)
                    return {"error": f"Refused: {req['payee']} still has open invoice(s) {ids}. Pay those first."}
                lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
                arrival = (date.fromisoformat(today) + timedelta(days=lead["lead_days"])).isoformat()
                conn.execute("UPDATE approval_requests SET expected_arrival = ? WHERE id = ?", (arrival, request_id))
                result["purchase_order"] = {"vendor": req["payee"], "sku": req["sku"], "size": req["size"],
                                            "qty": req["qty"], "expected_arrival": arrival}

            new_balance = round(acct["balance"] - amount, 2)
            conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today, req["account"]))
            pay = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (req["kind"], req["ref_id"] if req["kind"] != "purchase_order" else request_id,
                 amount, req["account"], today, req["decided_by"]),
            )
            conn.execute("UPDATE approval_requests SET status = 'paid', payment_id = ? WHERE id = ?",
                         (pay.lastrowid, request_id))
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
    return {
        "request_id": request_id,
        "payment_id": pay.lastrowid,
        "kind": req["kind"],
        "payee": req["payee"],
        "amount": amount,
        "approved_by": req["decided_by"],
        "paid_at": today,
        "balance_before": acct["balance"],
        "balance_after": new_balance,
        **result,
    }


# ----------------------------------------------------------- customer side ---

@mcp.tool
def save_customer_draft(ticket_id: int, recipient: str, subject: str, body: str, acting_agent: str = "") -> dict:
    """Save a message for a customer as a DRAFT on the ticket's board. It is
    never emailed or sent anywhere; a human reviews drafts on the dashboard."""
    if not (recipient.strip() and subject.strip() and body.strip()):
        return {"error": "recipient, subject, and body are all required"}
    with _connect(read_only=False) as conn:
        today = _today(conn)
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}"}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, author, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, recipient.strip(), subject.strip(), body.strip(), acting_agent or "unknown", today),
        )
    return {"draft_id": cur.lastrowid, "ticket_id": ticket_id, "status": "draft", "sent": False}


# ------------------------------------------- human-only (needs approval key) ---

@mcp.tool
def decide_approval(
    request_id: int, decision: Literal["approved", "rejected"], approver: str, approval_key: str, note: str = ""
) -> dict:
    """HUMAN ONLY. Record a person's approve/reject decision on a payment
    request. Requires the human approval key held by the dashboard backend;
    agents do not have it and cannot approve payments."""
    if not _human_key_ok(approval_key):
        return {"error": "Refused: a valid human approval key is required. Agents cannot approve payments."}
    name = approver.strip()
    if not name or name.lower() in AGENT_NAMES:
        return {"error": "Refused: the approver must be a named human, not an agent."}
    with _connect(read_only=False) as conn:
        today = _today(conn)
        req = conn.execute("SELECT status FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"No approval request with id={request_id}"}
        if req["status"] != "pending":
            return {"error": f"Request #{request_id} is already {req['status']}."}
        conn.execute(
            "UPDATE approval_requests SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (decision, name, today, note.strip() or None, request_id),
        )
    return {"request_id": request_id, "status": decision, "decided_by": name, "decided_at": today}


@mcp.tool
def reset_working_database(approval_key: str) -> dict:
    """HUMAN ONLY. Restore the working copy from the original database
    (data/campus_customs.db is read, never written). Run before a full run."""
    if not _human_key_ok(approval_key):
        return {"error": "Refused: a valid human approval key is required to reset the database."}
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    os.chmod(DB_PATH, 0o644)  # the original is read-only; the working copy must stay writable
    with _connect() as conn:
        today = _today(conn)
        open_count = conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
    return {"reset": True, "database": DB_PATH.name, "date_today": today, "open_tickets": open_count}


if __name__ == "__main__":
    mcp.run(show_banner=False)
