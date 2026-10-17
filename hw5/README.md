# Campus Customs Multi-Agent Operations: MGT 409 Homework 5

An agent team that runs the Campus Customs shop desk. It has three pieces that talk to each other:

| Piece | Folder | What it does |
|---|---|---|
| **MCP server** | `mcp_server/` | FastMCP server: the *only* way agents read or change shop data (17 tools over `data/campus_customs_new.db`). |
| **Backend** | `backend/` | FastAPI + PydanticAI. Five agents (Boss, Inventory, Accounting, Facilities, Customer Service), any of which can delegate to any other. Every agent uses **`gpt-6-luna` through Portkey**. |
| **Dashboard** | `frontend/` | React + Vite + TypeScript "Desk": watch the agents work live, approve payments, and see checking cash drop. |

**Safety rules built into the code:**
- **Agents only *prepare* payments.** Cash moves only when a named human approves on the dashboard (`POST /api/approvals/{id}/approve`).
- **No negative balances:** the pay tool refuses any payment the account can't cover.
- **Vendor block:** a vendor with an open invoice can't be paid for new product.
- **Nothing is sent:** customer messages stay as drafts on the board.
- **One model only:** `gpt-6-luna` is the only model in the code.

---

## Requirements

- **Python** 3.12+ (developed on 3.14)
- **Node.js** 20+ (developed on 24)
- **A Portkey API key** with access to `gpt-6-luna`

## Setup (once)

From this `hw5/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then put your real key in .env: PORTKEY_API_KEY=...
cd frontend && npm install && cd ..
```

`.env` is ignored by git. Never commit it.

## The two database files

| File | Role |
|---|---|
| `data/campus_customs.db` | **Original** shop data (tables `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, `invoices`). Never written to. Keep it untouched: it's the reset source. |
| `data/campus_customs_new.db` | **Working copy.** The MCP server and backend read and write only this file. As committed, it holds the **final state of the graded run**: all 3 tickets resolved, checking **$152.00** (see `output/`). |

### Copy the original to the working copy (clean start)

With the backend stopped:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

This restores the starting state: shop date 2026-08-31, checking $3,400.00, 3 open tickets, invoice 501 open, rent due 2026-09-02. The MCP server recreates its board tables (`approval_requests`, `drafts`, `ticket_updates`) on its first write.

---

## Start the MCP server

The backend **starts its own copy of the MCP server automatically** over stdio (`backend/mcp_link.py`), so you don't need to start it separately to use the app.

To run it on its own (for example, to inspect its tools from an MCP client):

```bash
python mcp_server/server.py          # from hw5/, venv active; speaks MCP over stdio
```

MCP clients such as Claude Code pick it up from `hw5/.mcp.json` (server name `campus-customs`). When it's launched that way, the human-only tools (approve, pay, reset) refuse to run, because only the backend holds the approval key. See `mcp_server/README.md` for all tools.

## Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000    # venv active
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- CORS: the Vite page origin (`http://localhost:5173`) is allowed.

## Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. The board calls the backend at `http://localhost:8000`; set `VITE_API_URL` to change it.

## Reset the database before a full three-ticket run

Always reset first, so the run starts from the original values ($3,400.00 checking). Any of these works:

1. **On the board:** click **Fresh start** (top right), then **Reset**. This is disabled while the team is working.
2. **Through the API:**
   ```bash
   curl -X POST http://localhost:8000/api/reset -H "Content-Type: application/json" -d '{"requested_by":"Your Name"}'
   ```
3. **With the backend stopped:** `cp data/campus_customs.db data/campus_customs_new.db` (as above).

Then run the three tickets:
1. Pick a ticket and click **Start the team**.
2. When a payment or purchase order appears under **Needs your approval**, type your name in **Signing as** and click **Approve & pay** twice. The first click arms the button, the second pays.
3. The ticket resumes automatically so the Boss can finish it.
4. Repeat until all three cards show **Resolved**.

A reset never deletes history: `output/audit_trail.json` is append-only and records the reset itself.

**Without the UI** (from `backend/`, venv active):

```bash
python -m agents.team --reset --approver "Your Name"                   # reset the working DB
python -m agents.team --all                                            # run every open ticket
python -m agents.team --approve 1 --approver "Your Name" --resume      # approve + pay request #1, then finish its ticket
```

---

## Layout

```
hw5/
├── AI_prompts.md            prompt log, one section per problem
├── requirements.txt         Python dependencies
├── .env.example             PORTKEY_API_KEY placeholder (copy to .env)
├── .mcp.json                MCP server entry for MCP clients
├── data/                    campus_customs.db (original) + campus_customs_new.db (working copy)
├── mcp_server/              server.py (17 MCP tools) + README.md
├── backend/
│   ├── main.py              FastAPI routes
│   ├── models.py            data types (Pydantic)
│   ├── config.py            gpt-6-luna via Portkey, paths, token limits
│   ├── mcp_link.py          the backend's MCP connection (per-agent tool filtering, audit hook)
│   ├── audit.py             append-only output/audit_trail.json
│   ├── agents/              boss.py, inventory.py, accounting.py, facilities.py, customer_service.py, team.py
│   └── prompts/             boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
├── frontend/                React + Vite + TypeScript dashboard
└── output/
    ├── harness.md           tables, MCP tools, agents, routes, dashboard, safety, run results
    ├── mcp_smoke.json       MCP tool smoke test
    ├── desk_tickets.html    Expected vs. Actual per ticket, Cash, Reflection
    ├── design.md            dashboard design spec
    ├── resolved_tickets.json
    ├── resolved_board.html  dashboard screenshots of each resolved ticket
    ├── audit_trail.json     every agent-loop step of the graded run
    └── github_url.txt
```

## The graded run, in one line

Starting at **$3,400.00**, three payments were each approved by a human:
- invoice 501, **$840** (ticket 101)
- rent, **$2,400** (ticket 102)
- a one-tee purchase order, **$8** (ticket 101)

Ticket 103 was resolved with a discount and no spending. Checking ended at **$152.00**, matching `cash_accounts`. Details are in `output/desk_tickets.html` (Cash tab).
