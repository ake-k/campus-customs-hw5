# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that gives the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service) access to the shop database. **It is the only way the agents read or change shop data.** The backend has no second tools layer, so every fact comes from the database and every change goes through the rules enforced here.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy. Tools read it and write to it as tickets are resolved.
- **Never written:** `data/campus_customs.db`, the original. The server refuses to start if pointed at it. It is only read by `reset_working_database` to restore the working copy.
- **Board tables:** `approval_requests`, `drafts` and `ticket_updates` are created inside the working copy on first write, so a reset clears them.
- **Override:** set the `CC_DB_PATH` environment variable to use a different file (a relative path resolves against `hw5/`).
- **"Today":** always `desk.date_today` (2026-08-31 at start), never the computer's clock.

## Tools

### Read
| Tool | Tables | What it returns |
|---|---|---|
| `get_desk()` | `desk` | The shop's today and desk notes |
| `list_open_tickets()` | `tickets` | Every ticket not resolved or declined |
| `list_tickets()` | `tickets` + board tables | Every ticket, open or not, with counts of its updates, requests and drafts (used by the dashboard) |
| `get_ticket(ticket_id)` | `tickets` + linked `inventory`, `pricing`, `leases`, `invoices`, `vendors`, and board tables | One ticket with everything it links to and its board history |
| `check_stock_and_margin(sku, size, qty_needed)` | `inventory`, `pricing` | On hand vs. needed, shortfall, unit cost, list price, margin |
| `list_vendors()` | `vendors`, `invoices` | Specialty, lead days, blocked-by-open-invoice flag, arrival if ordered today |
| `get_invoice_status(invoice_id)` | `invoices`, `vendors` | Amount, due date, days overdue, vendor lead time, blocked flag |
| `get_lease_and_cash(lease_id)` | `leases`, `cash_accounts` | Rent, next due, days until due, whether cash covers it |
| `get_cash_position()` | `cash_accounts`, `invoices`, `leases`, `approval_requests`, `payments` | Cash vs. every commitment, plus payments made |
| `quote_discount(sku, qty, discount_pct)` | `pricing` | Discounted price, totals, margin, at-or-below-cost flag (calculation only) |
| `list_approval_requests(status, ticket_id)` | `approval_requests` | Payment / PO requests and their human decision |

### Write (agents)
| Tool | What it does |
|---|---|
| `update_ticket(ticket_id, status, note)` | Sets the ticket status and adds a note to `ticket_updates` |
| `request_payment_approval(ticket_id, kind, reason, ...)` | Files a **pending** request for a human (`invoice`, `rent`, or `purchase_order`). The amount is looked up from the DB. Refuses duplicates and amounts above cash on hand. |
| `save_customer_draft(ticket_id, recipient, subject, body)` | Saves a draft on the board. **Never sends anything.** |

### Human only (need the backend's approval key)
| Tool | What it does |
|---|---|
| `decide_approval(request_id, decision, approver, approval_key)` | Records a named person's approve/reject decision |
| `pay_approved_request(request_id, approval_key)` | Pays **only a human-approved** request. Refuses an overdraft or a PO to a vendor with an open invoice. Updates `cash_accounts` and `payments` (with `approved_by`), plus `invoices` → paid, `leases.next_due` + 1 month, or the PO's expected arrival. Called only by the backend's approve route, so **agents prepare payments but never make them**. |
| `reset_working_database(approval_key)` | Copies the original DB over the working copy |

The backend generates the approval key at startup and passes it to this server as `CC_HUMAN_APPROVAL_KEY`. Only its human routes use the key (`POST /api/approvals/{id}/approve` and `/reject`, `POST /api/reset`), and agents never see it. Without it (for example, when launched from `.mcp.json`), approvals, payments and resets are refused.

## Running

From the `hw5/` folder, with the virtual environment active:

```bash
python mcp_server/server.py
```

This runs over stdio. MCP clients such as Claude Code pick it up from `hw5/.mcp.json` (server name `campus-customs`). The backend launches its own copy through `backend/mcp_link.py`. A smoke test of the first three tools is in `output/mcp_smoke.json`.
