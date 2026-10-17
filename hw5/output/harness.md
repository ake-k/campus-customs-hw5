# Harness — Campus Customs Multi-Agent Operations

This file describes the environment the agent team works in:
1. the **database tables**
2. the **MCP tools** over them
3. the **five agents**
4. the **API routes**
5. the **dashboard**
6. the **safety rules**

It ends with how to run everything and what the full run produced.

- **Original database (read-only, used for resets):** `data/campus_customs.db`
- **Working copy (the one tools read and update):** `data/campus_customs_new.db`
- **"Today" for the shop:** `desk.date_today` = **2026-08-31**. Never use the computer's clock.

---

## Database tables

### `desk`
| Field | Type | Notes |
|---|---|---|
| `date_today` | TEXT | The shop's current date (ISO `YYYY-MM-DD`) |
| `notes` | TEXT | Free-text notes for the desk (empty at start) |

**Why it matters:** This is the agents' clock. Every "is it overdue?" or "when will it arrive?" check uses this date.

### `tickets`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Ticket number |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override`, … |
| `requester` | TEXT | Who raised the ticket (customer, landlord, student org) |
| `subject` | TEXT | Short title |
| `sku` | TEXT | Product involved → `inventory.sku` / `pricing.sku` (nullable) |
| `size` | TEXT | Size involved → `inventory.size` (nullable) |
| `qty` | INTEGER | Quantity requested (nullable) |
| `lease_id` | INTEGER FK | → `leases.id` (nullable) |
| `invoice_id` | INTEGER FK | → `invoices.id`, a bill blocking this ticket (nullable) |
| `status` | TEXT | `open` at start, then moves to resolved/waiting states |
| `notes` | TEXT | The request in the requester's words |
| `created_at` | TEXT | ISO timestamp with timezone |

**Why it matters:** This is the board. Boss reads it to route work, and its foreign keys point agents to the rows they need.

### `inventory`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT | Product code (PK part 1) |
| `name` | TEXT | Product name |
| `size` | TEXT | `S`/`M`/`L`/`XL`, or `OS` for one-size items (PK part 2) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle in the shop |

**Why it matters:** Inventory uses it to check stock by SKU and size and to find shortfalls against ticket quantities.

### `pricing`
| Field | Type | Notes |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `unit_cost` | REAL | What the shop pays the vendor per unit |
| `list_price` | REAL | Normal selling price per unit |

**Why it matters:** Accounting uses it for margins and for the floor on any discount, and to cost restock orders.

### `vendors`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Vendor ID |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What they supply (apparel reprint, mugs/small goods, courier) |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** Inventory picks the vendor that can restock an item and uses `lead_days` to give an honest arrival date.

### `invoices`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Invoice number |
| `vendor_id` | INTEGER FK | → `vendors.id` |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | Due date (ISO) |
| `status` | TEXT | `open` (unpaid) or `paid` |
| `description` | TEXT | What the bill was for |

**Why it matters:** An open invoice blocks new shipments from that vendor, and one past `desk.date_today` is overdue.

### `leases`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Lease ID |
| `space_name` | TEXT | Shop space |
| `landlord` | TEXT | Who is paid |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Next rent due date (ISO) |
| `notes` | TEXT | Free-text notes |

**Why it matters:** Facilities uses it to check rent amount and due date, and moves `next_due` forward a month after rent is paid.

### `cash_accounts`
| Field | Type | Notes |
|---|---|---|
| `name` | TEXT PK | Account name (`checking`) |
| `balance` | REAL | Current cash |
| `date` | TEXT | Date the balance was last updated |

**Why it matters:** This is the only source of money. The pay tool must refuse any payment that would make the balance negative.

### `payments`
| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Payment ID |
| `kind` | TEXT | What was paid (e.g. `invoice`, `rent`, `purchase_order`) |
| `ref_id` | INTEGER | ID of the invoice/lease/PO paid |
| `amount` | REAL | Amount paid |
| `account` | TEXT | → `cash_accounts.name` |
| `paid_at` | TEXT | Date paid (shop date) |
| `approved_by` | TEXT NOT NULL | Human who approved the payment |

**Why it matters:** This is the record of every payment, and the required `approved_by` field shows a human approved each one. It is empty at start.

### Board tables (added by the MCP server to the working copy only)
The original database has none of these. The MCP server creates them inside `campus_customs_new.db` on its first write, so a reset (which copies the original back over the working copy) clears them.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `approval_requests` | `id`, `ticket_id`, `kind` (invoice / rent / purchase_order), `ref_id`, `payee`, `vendor_id`, `sku`, `size`, `qty`, `unit_cost`, `amount`, `account`, `reason`, `requested_by`, `status` (pending / approved / rejected / paid), `decided_by`, `decided_at`, `decision_note`, `payment_id`, `expected_arrival`, `created_at` | Where agents **prepare** payments and purchase orders. A human's decision and the resulting payment are recorded here, so this is the approval queue the dashboard shows. |
| `drafts` | `id`, `ticket_id`, `recipient`, `subject`, `body`, `author`, `status` (always `draft`), `created_at` | Customer Service's messages. They stay on the board and are never sent. |
| `ticket_updates` | `id`, `ticket_id`, `status`, `note`, `author`, `created_at` | The Boss's status changes and reasons. It records the board's history without overwriting the original ticket request. |

---

## Starting state (2026-08-31)

| Item | Value |
|---|---|
| Cash (`checking`) | $3,400.00 |
| Open invoices | #501 — Bulldog Print Co, $840.00, due 2026-08-28 (**3 days overdue**) |
| Rent | Chapel Street shop, $2,400.00, due 2026-09-02 (in 2 days) |
| Open tickets | 101 (customer order), 102 (rent notice), 103 (price override) |
| Payments | none |

---

## Open tickets and how they link to other tables

| Ticket | Type · requester | Links | What the links show |
|---|---|---|---|
| **101** | `customer_order` · Tauhid Zaman: 1 × CC-TEE-WHITE, size S | `sku`+`size` → `inventory`, `pricing`; `invoice_id` 501 → `invoices` → `vendors` (id 1) | 0 size-S tees on hand (short 1); $28 list / $8 cost. Invoice 501 is an open $840 bill to Bulldog Print Co (apparel reprint, 5 lead days), due 2026-08-28 and 3 days overdue, so the vendor won't reprint the tee until it's paid. |
| **102** | `rent_notice` · Elm City Properties: "rent due in 2 days" | `lease_id` 1 → `leases`; cash → `cash_accounts` | Chapel Street shop, $2,400/month, due 2026-09-02 (2 days, not overdue). Paying it means a `payments` row, lower `cash_accounts`, and `leases.next_due` → 2026-10-02. |
| **103** | `price_override` · Yale AI Club: 20 × CC-HOOD-NAVY, size M, bulk discount | `sku`+`size` → `inventory`, `pricing`; restock vendor via `vendors` / `invoices` | 8 on hand (short 12); $58 list / $22 cost ($36 margin per hoodie, so any discount must stay above $22). Restocking 12 costs $264, and the apparel vendor is blocked by invoice 501. |

**Cash links all three.** Cash is $3,400. Rent ($2,400) plus invoice 501 ($840) leaves $160, which can't cover the $264 hoodie restock.

---

## MCP tools that unlock the three tickets

These were the first three tools. They read only the working copy, `data/campus_customs_new.db`, and use `desk.date_today` as "today". The full list of tools, including the ones added for the agent team, is under **All MCP tools** below.

| Tool | Tables read | Unlocks ticket | Why this tool is the right one for that ticket |
|---|---|---|---|
| `get_invoice_status(invoice_id)` | `invoices`, `vendors`, `desk` | **101** (Bulldog tee, size S) | Ticket 101 has `invoice_id = 501`. This tool shows that invoice 501 is $840, open and 3 days overdue to Bulldog Print Co, so that vendor won't reprint the out-of-stock tee until it's paid. It also returns the 5-day lead time the customer reply needs. |
| `get_lease_and_cash(lease_id)` | `leases`, `cash_accounts`, `desk` | **102** (rent notice) | Ticket 102 has `lease_id = 1`. This tool confirms the $2,400 Chapel Street rent is due 2026-09-02 (2 days away, not overdue) and that the $3,400 in checking covers it, leaving $1,000 before any other payment. That's what Accounting needs before asking a human to approve the rent payment. |
| `check_stock_and_margin(sku, size, qty_needed)` | `inventory`, `pricing` | **103** (Yale AI Club bulk hoodie discount) | Ticket 103 asks for 20 CC-HOOD-NAVY in size M at a discount. This tool shows only 8 are on hand (12 short) and that each hoodie costs $22 and lists at $58, so the $36/unit margin is the room Boss has for a discount without selling below cost. |

**Also used:** ticket 101 calls `check_stock_and_margin('CC-TEE-WHITE', 'S', 1)` to confirm 0 tees are on hand. Ticket 103 calls `get_invoice_status(501)` because its 12-hoodie restock would also come from the blocked apparel vendor.

---

## Agent team (`backend/agents/`, prompts in `backend/prompts/`)

All five agents are PydanticAI agents on **`gpt-6-luna` through Portkey**. That's the only model in the code; it's set as a constant in `backend/config.py` and can't be overridden from the environment. Every agent has the `ask_agent` tool and can delegate to **any** other agent (full connectivity). Shop facts and changes come **only** from the MCP server. Each agent sees just the MCP tools its role needs.

| Agent | Role | MCP tools it can call | Limits per run (requests / tokens / asks) |
|---|---|---|---|
| **Boss** (`boss.py`) | Reads each ticket, routes it to teammates, makes the final call, records it on the board. Returns a structured `TicketDecision`. | `get_desk`, `list_open_tickets`, `get_ticket`, `get_cash_position`, `list_approval_requests`, `update_ticket` | 20 / 150k / 6 |
| **Inventory** (`inventory.py`) | Stock by SKU and size, shortfalls, which vendor can restock, blocked or not, earliest arrival. Read-only. | `get_desk`, `get_ticket`, `check_stock_and_margin`, `list_vendors`, `get_invoice_status` | 10 / 60k / 2 |
| **Accounting** (`accounting.py`) | Cash and invoices, margins and discount pricing. Files payment / PO requests for human approval. **Never pays**: the dashboard's approve route does. | `get_desk`, `get_ticket`, `get_cash_position`, `get_invoice_status`, `get_lease_and_cash`, `check_stock_and_margin`, `quote_discount`, `list_vendors`, `list_approval_requests`, `request_payment_approval` | 12 / 80k / 2 |
| **Facilities** (`facilities.py`) | Leases, landlord, rent amount and due date; checks a rent notice against the lease. Read-only. | `get_desk`, `get_ticket`, `get_lease_and_cash`, `list_approval_requests` | 8 / 50k / 2 |
| **Customer Service** (`customer_service.py`) | Writes honest replies to requesters and saves them as drafts on the board, never sent. | `get_desk`, `get_ticket`, `check_stock_and_margin`, `quote_discount`, `save_customer_draft` | 8 / 50k / 2 |

**Agent loop.** `backend/agents/team.py` runs each agent with `agent.iter()`. Each step appends an event to `output/audit_trail.json`: `agent_started`, `model_request`, `model_response` (text, tool calls, token usage, model), `tool_call` and `tool_result` (args, result, ms), `delegation_started/finished/blocked`, and `agent_finished` (output, usage). Every event carries the run id, ticket, shop date, agent, depth and chain. Human approvals and DB resets are logged too. The file is append-only.

## All MCP tools (`mcp_server/server.py`)

Board tables: `approval_requests`, `drafts` and `ticket_updates` are created by the MCP server **inside the working copy only**. A reset restores the original file, which clears them.

| Tool | Tables it uses | Reads / writes | Who can call it |
|---|---|---|---|
| `get_desk` | `desk` | read | all agents |
| `list_open_tickets` | `tickets` | read | Boss |
| `list_tickets` | `tickets`, `ticket_updates`, `approval_requests`, `drafts` | read | backend only (`GET /api/tickets`) |
| `get_ticket` | `tickets`, `inventory`, `pricing`, `leases`, `invoices`, `vendors`, `ticket_updates`, `approval_requests`, `drafts` | read | all agents |
| `update_ticket` | `tickets`, `ticket_updates`, `desk` | **write** | Boss |
| `check_stock_and_margin` | `inventory`, `pricing` | read | Inventory, Accounting, Customer Service |
| `list_vendors` | `vendors`, `invoices`, `desk` | read | Inventory, Accounting |
| `get_invoice_status` | `invoices`, `vendors`, `desk` | read | Inventory, Accounting |
| `get_lease_and_cash` | `leases`, `cash_accounts`, `desk` | read | Accounting, Facilities |
| `get_cash_position` | `cash_accounts`, `invoices`, `vendors`, `leases`, `approval_requests`, `payments`, `desk` | read | Boss, Accounting |
| `quote_discount` | `pricing` | read (calculation only) | Accounting, Customer Service |
| `list_approval_requests` | `approval_requests` | read | Boss, Accounting, Facilities |
| `request_payment_approval` | `invoices`, `vendors`, `leases`, `inventory`, `pricing`, `cash_accounts`, `tickets`, `approval_requests` | **write** (pending request; amount looked up, never supplied) | Accounting |
| `pay_approved_request` | `approval_requests`, `cash_accounts`, `payments`, `invoices`, `leases`, `vendors` | **write** (only if human-approved; refuses overdraft or a blocked vendor) | **Human only**: called by `POST /api/approvals/{id}/approve` with the approval key |
| `save_customer_draft` | `drafts`, `tickets` | **write** (draft only, never sent) | Customer Service |
| `decide_approval` | `approval_requests` | **write** | **Human only**: needs the dashboard's approval key |
| `reset_working_database` | copies `campus_customs.db` → `campus_customs_new.db` | **write** | **Human only**: needs the approval key |

## Safety

### Guardrails a real business would want
- **A human approves every payment, and the code enforces it, not just the prompts.**
  - Agents can only *prepare* a payment. No agent has a pay tool.
  - Cash moves only through `POST /api/approvals/{id}/approve`, which records the person's decision (`decide_approval`) and then pays (`pay_approved_request`).
  - Both tools need a random key the backend generates at startup and never puts in a prompt, and they reject agent names as approvers.
  - `pay_approved_request` also refuses anything a named human hasn't approved.
  - The approver's name is written to `payments.approved_by`.
- **Agents can't move money on their own.** Payment amounts are looked up from the database, never typed in by an agent. Duplicate requests are refused. Requests and payments above cash on hand are refused, so no balance can go negative. A purchase order to a vendor with an open invoice can't be paid.
- **Least privilege.** Each agent sees only its role's MCP tools. The backend checks again on every call and logs refusals as `tool_denied`. It also writes the calling agent's id on every write, so an agent can't claim to be someone else.
- **Nothing leaves the shop.** There are no email, SMS or vendor tools at all. Customer messages are saved as drafts for a human to review. The Customer Service prompt forbids sharing costs, margins, vendor names, bills or cash with customers.
- **No made-up facts.** Tools return only database values and arithmetic on them, and return an error rather than guess. The prompts require every number to come from a tool.
- **The original data is protected.** `campus_customs.db` is read-only on disk. The MCP server refuses to run against it and only reads it to reset the working copy. Resets are human-only and logged.
- **Everything is auditable.** Every model step, tool call, delegation, human decision and reset is appended to `output/audit_trail.json` with timestamps, the shop date, the run id and the agent chain.
- **For production, a business would add:** login for approvers, two-person approval above a dollar limit, daily spending caps, an alert when cash drops below a floor, and an audit log that can't be edited.

### Limits that keep token use in check
- **Per agent run:** a request limit (Boss 20, Accounting 12, Inventory 10, Facilities and Customer Service 8) and a total-token limit (Boss 150k, Accounting 80k, Inventory 60k, Facilities and Customer Service 50k), enforced by PydanticAI `UsageLimits`.
- **Per model response:** at most 4,000 output tokens (`max_tokens`).
- **Delegation:**
  - Each agent has its own ask limit (Boss 6, the others 2), and the whole team shares 10 asks per ticket.
  - A chain of asks stops at depth 3.
  - No agent can ask itself or anyone up its chain who is waiting on it, so loops can't form.
- **Small context:** each agent gets only its own prompt, its role's tools and a self-contained question, not the whole conversation. Tool results are compact JSON.
- **Measured:** on test runs, a ticket used about 8–18 model requests and 25k–53k tokens in total.

---

## Backend routes (`backend/main.py`)

Start from `hw5/backend/` with `uvicorn main:app --reload --port 8000` (API at http://localhost:8000, docs at `/docs`). Every route gets its data from the MCP server.

| Route | What it does |
|---|---|
| `GET /api/tickets` | Lists the three tickets with their status, whether each is open or resolved, and counts of pending approvals, drafts and updates. |
| `GET /api/tickets/{id}` | Returns one ticket with its linked rows and board history (updates, payment requests, drafts). |
| `POST /api/tickets/{id}/run` | Starts the agent team on that ticket in the background (one run at a time) and returns a `run_id`. |
| `GET /api/runs/{run_id}` | Returns a run's status (queued / running / done / error) and the Boss's final decision. `GET /api/runs` lists all runs. |
| `GET /api/events?after=&ticket_id=&run_id=` | Returns recent agent events from the audit trail, one readable line each (what each agent said, asked, and which tools it called), with a `cursor` so the board can poll for new ones. |
| `GET /api/approvals?status=&ticket_id=` | Lists the payment / purchase-order requests the agents prepared and their human decision. |
| `POST /api/approvals/{id}/approve` | A named human approves a request, and **this route pays it**. It is the only route that changes cash, and it refuses an overdraft or a blocked vendor. By default it then resumes the ticket so the Boss can finish it. |
| `POST /api/approvals/{id}/reject` | A named human rejects a request. No cash moves. |
| `GET /api/cash` | Returns the current `checking` balance from `cash_accounts`, plus unpaid requests and payments made. |
| `POST /api/reset` | Restores `campus_customs_new.db` from the original `campus_customs.db` for a fresh run. Refused while the team is working; the audit trail is kept. |
| `GET /api/health` | Returns the model (`gpt-6-luna`), the database, the shop date, and whether the team is busy. |

---

## Dashboard (`frontend/`)

React + Vite + TypeScript. Start it from `hw5/frontend/` with `npm install` (first time only) and then `npm run dev`, and open http://localhost:5173.
- **Backend address:** it calls the backend at `http://localhost:8000` (set in `src/api.ts`; `VITE_API_URL` can override it).
- **CORS:** the backend allows the Vite origin `http://localhost:5173` (plus other local ports).
- **Live updates:** the desk polls `/api/events` with a cursor, every 1.2 s while the team works and every 4 s when idle, and refreshes tickets, cash and approvals after each poll.
- **Design notes:** see `output/design.md`.

---

## How to run it

1. **Set up (once):**
   - `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
   - copy `.env.example` to `.env` and set `PORTKEY_API_KEY`
   - `cd frontend && npm install`
2. **Backend:** `cd backend && uvicorn main:app --reload --port 8000`, with the venv active.
3. **Dashboard:** `cd frontend && npm run dev`, then open http://localhost:5173.
4. **Before a full run:** click **Fresh start** on the desk, or `POST /api/reset`. This restores `campus_customs_new.db` from the original `campus_customs.db`.
5. **Run tickets:** pick each ticket and click **Start the team**.
6. **Approve payments:** type your name under "Signing as" and use **Approve & pay**. Approving resumes the ticket automatically, so the Boss can finish it.

The CLI does the same without the UI, from `backend/`:
- `python -m agents.team --reset --approver "Name"`
- `python -m agents.team --all`
- `python -m agents.team --approve N --approver "Name" --resume`

## Full run (Problem 9)

Starting from a reset database at **$3,400.00** checking, all three tickets were run from the dashboard until **resolved**.

### Money moved
| Payment | Ticket | Kind | Payee | Amount | Approved by | Checking after |
|---|---|---|---|---|---|---|
| — | — | start (after reset) | — | — | — | $3,400.00 |
| #1 | 101 | invoice 501 | Bulldog Print Co | −$840.00 | Ake Kankirawatana | $2,560.00 |
| #2 | 102 | rent, lease 1 | Elm City Properties | −$2,400.00 | Ake Kankirawatana | $160.00 |
| #3 | 101 | purchase order (1 × CC-TEE-WHITE S @ $8) | Bulldog Print Co | −$8.00 | Ake Kankirawatana | **$152.00** |

Ticket 103 moved no cash. The Boss gave 10% off the 8 in-stock hoodies and declined the $264 restock because only $160 was left. The ending balance, **$152.00**, equals `cash_accounts.balance`; $3,400.00 − $3,248.00 in `payments` = $152.00.

### Team activity
- **Runs:** 6 team runs (101 ×3, 102 ×2, 103 ×1).
- **Totals:** 80 model requests, 81 MCP tool calls plus 15 agent-to-agent delegations, about 254k tokens, all on `gpt-6-luna`.
- **Refusals:** zero denied tool calls.
- **Payments:** zero agent payment attempts. Every payment went through the approve route after a named human approved it.

### Where the details are
- `desk_tickets.html`: Expected vs. Actual for each ticket, plus the Cash tab
- `resolved_tickets.json`: per-ticket outcome, agent contributions, approvals
- `resolved_board.html`: dashboard screenshots
- `audit_trail.json`: every agent-loop step, append-only

**Before the run,** the Boss prompt got a concrete definition of `resolved`: "the shop has done everything it can right now". Under it, a paid order still in transit counts as resolved, and so does a recorded decision not to spend.
