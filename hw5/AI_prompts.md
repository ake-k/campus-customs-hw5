# AI Prompts Log — Homework 5 (Campus Customs Multi-Agent Operations)

This file logs the prompts given to the AI assistant (Claude Code) while completing Homework 5, organized by problem. Each section lists the problem number and title, the prompts given, any follow-up prompts, and a one-sentence note on what the first prompt was missing when a follow-up was needed.

---

## Problem 1: Vibe coder prompts

### Prompt 1
> Hi Claude! Today, we'll be working in the Homework 5 folder, and I want you to put all my work in there. Please confirm that you can read/write the Homework 5 folder.

### Prompt 2
> @"/Users/akekankirawatana/Downloads/data.zip"
> First, I'll describe the Scenario for Homework 5 (don't do anything yet):
>
> "Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board -- customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. You will build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests.
>
> Your agent team has full connectivity -- any agent may delegate tasks to any other agent for help. In this assignment you will build these agents:
>
> * Boss -- reads each ticket, decides who should work on it, and makes final calls
> * Inventory -- checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock
> * Accounting -- watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval
> * Facilities -- handles the shop space side (leases, rent, etc.)
> * Customer Service -- drafts messages for customers"
>
> Attached, find the original shop database, campus_customs.db, with tables for desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices.
>
> Tools will update the database as tickets get resolved. Create a copy of the database file campus_customs_new.db and point the MCP server and backend at that working copy. Keep the original shop database untouched -- we will need it to reset when we restart resolving the tickets later.
>
> Here are the rules of the shop:
>
> * "The field desk.date_today is "today" for the shop. Use this date to determine what is overdue.
> * Vendor lead times come from the vendors table
> * A vendor will not ship new product while they still have an open unpaid invoice
> * Human approval is required for any payments (IMPORTANT: Points will be deducted if this is not done). If payment is made, make sure to update the relevant table.
> * If there is not enough cash, the pay tool must refuse -- no negative balances
> * Cash only goes out in this homework -- we did not model revenue, so no money comes in
> * Before a full run to resolve the tickets, make sure to reset the database to its original values
> * Do NOT email customers or call real vendors. Drafts stay on the board"
>
> Use PORTKEY_API_KEY for AI calls. For this assignment, use ONLY gpt-6-luna through Portkey for every agent (IMPORTANT: Points will be deducted if any other model shows up in the code or runs).
>
> FInal submission of the assignment will be via a public GitHub repo (see screenshot attached for the expected file tree).
>
> *(Attached: screenshot of the required `hw5/` folder structure.)*

### Prompt 3
> Problem 1: Vibe coder prompts
>
> Create AI_prompts.md and update as we go. This file is the log of what I tell you. Put one section for each problem. Each section must include the problem number and title, at least one prompt I gave you, and one follow-up prompt if it was needed (with a one-sentence note on what was lacking from the first prompt).

*Note:* The AI created the repo folder at `Homework 5/hw5/` and a Python virtual environment at `Homework 5/.venv` (outside the repo, matching the Homework 4 layout), then started this log.

**Follow-up needed?** No. These prompts were clear and were completed as asked.

---

## Problem 2: Study the Campus Customs database

### Prompt 1
> Problem 2: Study the Campus Customs database
>
> Copy data/campus_customs.db to data/campus_customs_new.db -- later problems will update that working copy.
>
> Explain the three open tickets to me, including how they link to other tables.
>
> Start output/harness.md and for eacht able, list the fileds and a short, one-line summary on why that table matters for the agent.
>
> The harness will be updated in later problems.

*Note:* The AI unzipped `data.zip` (leaving out macOS `__MACOSX` files), placed the original at `data/campus_customs.db` and made it read-only so it can't be changed by accident, copied it to `data/campus_customs_new.db` (checksums match), explained tickets 101–103 and their links, and started `output/harness.md` with every table's fields, a one-line reason each table matters, and the starting state.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 3: Build the MCP server

### Prompt 1
> Problem 3: Build the MCP server
>
> Write an MCP server in mcp_server/ using FastMCP. It will talk to the DB. Do not connect or run it yet.
>
> Every agent from hereon uses tools in this MCP server. We will add more tools to it later; for now, write just the three tools we need for the tickets in the database. Keep the names clear. Never invent any data, and use only the information in the database.
>
> In the harness, list each of the three MCP tools. For each, include which table it reads, which ticket it helps unlock (e.g., 101, 102, or 103), and a one-sentence note on why that tool is the right one for that ticket. Don't write vague rationales like "reads inventory," but be specific and tie the tool to the ticket.
>
> Also create a short mcp_server/README.md that explains what the MCP server is for, which DB it uses, and the three tools it has.

*Note:* The AI installed FastMCP in the venv and wrote `mcp_server/server.py` with three read-only tools: `get_invoice_status` (101), `get_lease_and_cash` (102), and `check_stock_and_margin` (103). It checked them by calling the Python functions directly, without starting or connecting the server, and confirmed both databases were unchanged. It then added an MCP tools table to `output/harness.md` and wrote `mcp_server/README.md`.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt 1
> Problem 4: Add the MCP server to vibe coder and test each tool
>
> Add the MCP server to this project so you can call the tools. Save the .mcp.json at the project root or however you prefer to save local MCP server lists.
>
> Now, test each of the three MCP tools. Save the evidence to output/mcp_smoke.json. For every tool, include the prompt you asked, the tool name, and the tool output (which must match values in the DB).

*Note:* The AI saved `hw5/.mcp.json` (server `campus-customs`) with relative paths so it works on a grader's machine, and made the server resolve the database path relative to the repo. It launched the server from that config over stdio with a real MCP client, called all three tools, and checked each returned value against a direct read-only SQLite query. All values matched, and the evidence is in `output/mcp_smoke.json`.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 5: Build the agent team and grow the MCP tools

### Prompt 1
> Problem 5: Build the agent team and grow the MCP tools
>
> Build the agentic team for Campus Customs using PydanticAI, comprising Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivitiy.
>
> Put the agent promtps in backend/prompts/ (one file per agent). Put data types in backend/models.py, and the agent files under backend/ (ensure the five roles are clear). Use Porkey API key and gpt-6-luna only for every agent.
>
> Ensure the prompts for each agent are detailed as possible, covering all aspects of an agent's work and scope. Each agent should know all the shop rules that are relevant to its task. The five agents are:
>
> * Boss (reads each ticket, decides who should work on it, and makes final calls)
> * Inventory (checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock)
> * Accounting (watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval)
> * Facilities (handles the shop space side, including leases, rent, eetc.)
> * Customer Service (drafts messages for custoers)
>
> Add any tools the agents will need to the MCP serve so they can work on the open tickets. Shop facts should come from the MCP server over the new DB (do not create a second shop-tools layer that bypasses the MCP).
>
> Have the agents add to output/audit_trail.json as they run -- enough data from each agent-loop step should be recorded to be auditable later. Append to the file and don't wipe it after each run.
>
> In the harness, list eacha gent and each MCP tool (including the ones just added) along with which table the tool uses. Add a short safety section with guardrails a real business would want when the agents touch real customers and real money, plus limits that keep token use in check.
>
> Update mcp_server/README.md.

*Note:* The AI grew the MCP server from 3 to 16 tools:
- **New read tools:** desk, tickets, vendors, cash position, discount quotes, and approval requests.
- **New write tools:** ticket updates, payment / purchase-order requests, a pay tool that only pays human-approved requests, and customer drafts.
- **Two human-only tools** (approve a payment, reset the database), which need a key the backend holds and agents never see.

It built the five PydanticAI agents on `gpt-6-luna` via Portkey:
- one role file each in `backend/agents/`
- detailed prompts in `backend/prompts/`
- data types in `backend/models.py`
- an `ask_agent` tool that lets any agent ask any other, with limits that stop loops
- each agent's loop runs step by step with `agent.iter()` and is logged to an append-only `output/audit_trail.json`

It tested all three tickets plus a human approval → payment → resume flow on a scratch copy of the database, so the real working copy and audit trail were not touched. It then updated the harness (agents, all tools and their tables, safety and token limits) and the MCP README, and added `requirements.txt`, `.env.example`, and `.gitignore`.

**Follow-up needed?** No. The prompt was detailed enough to complete as asked.

---

## Problem 6: Plan the three tickets

### Prompt 1
> Problem 6: Plan the three tickets
>
> Before writing the backend, create output/desk_tickets.html (a page that can be double-clicked with one tab per ticket) and write a short summary of what we expect the agentic team do on each open ticket under an "Expected" section (we will record what the agents actually did when we run them later in an "Actual" section). Also add Cash and Reflection tabs for later problems (leave them blank for now).
>
> For each ticket, write what we expect the agentic team to do:
>
> * Who the Boss should call first and why
> * All the agent delegations we'd expect (not simply "Boss calls everyone")
> * Which MCP tools we  expect that run to use

*Note:* The AI built `output/desk_tickets.html` as one self-contained page (no external files, so it opens with a double-click) in the project's Liquid Glass style. It has five tabs: Ticket 101, Ticket 102, Ticket 103, Cash, and Reflection. Each ticket tab shows:
- the ticket's facts from the database
- an **Expected** section: who the Boss calls first and why, each expected delegation in order (including peer-to-peer asks such as Accounting → Inventory and the follow-up after a human approves), the MCP tools expected per agent, and the expected first-run outcome
- an empty **Actual** section

Cash and Reflection are left blank. The AI checked the page in a browser in light and dark mode and confirmed every tab switches.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 7: Backend routes

### Prompt 1
> Problem 7: Backend routes
>
> The React frontend dashboard we will create in Problem 8 needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following:
>
> * Return three tickets and whether each is open or resolved
> * Take a ticket id and run your agent team on that ticket
> * Return recent agent events (i.e., what each agent said and which tools they used) so the board can refresh
> * Approve a payment of purchase after a human approves (i.e., agents only prepare the pay, and this route is what actually changes cash)
> * Return the current checking balance from cash_accounts
> * Reset the database to the original values when you want to try a fresh run
>
> From the backend/ folder, start the server with (to turn on the backend at http://localhost:8000):
> uvicorn main:app --reload --port 8000
>
> In the harness, write a short, one-line summary of each route (what URL and what it does).

*Note:* This prompt changed one Problem 5 design choice. In Problem 5, Accounting paid a request after a human approved it. Now agents only *prepare* payments: the pay tool became human-only (it needs the backend's approval key), Accounting lost it, and `POST /api/approvals/{id}/approve` records the person's decision and then pays. The prompts, harness, MCP README, and desk-tickets plan were updated to match.

The AI wrote `backend/main.py` with these routes:
- tickets list and detail
- start a run in the background (one at a time)
- run status
- an events feed with one readable line per audit event and a cursor for polling
- approvals list, approve (pays), and reject
- checking balance
- reset

It tested every route on a scratch database through a test server, including:
- a full ticket-102 run, approve → paid → resumed to resolved
- the refusals: an agent named as approver, double approval, a purchase order to the blocked vendor, an agent calling the pay tool without the key, and a reset during a run

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 8: Agent dashboard

### Prompt 1
> Problem 8: Agent dashboard
>
> Build the frontend dashboard in frontend/ with React, Vite, and TypeScript. The page should call the routes built in Problem 7. At minimum, the board should list all three tickets, let me pick one ticket and start the agent team on it, show each agent and what they are saying or doing while the ticket runs, mark a ticket resolved when the run finishes, show a short sumamry of what each agent did on that ticket, let a human approve a pay or purchase when asked, and show the checking balance (it should drop after an approved pay).
>
> Make the dashboard look good, with an innovative and user-friendly layout and feel.
>
> Tell the frontend to talk to the backend at port 8000, and on the backend, allow the Vite page origin (usually port 5173) so the browser is allowed to call the routes.
>
> Start the board with the following command so I can open the React desk in my browser and pick tickets/watch agents work:
> npm run dev
>
> Write output/design.md with the specifications for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up, etc.) and why. Ensure the desgin and creative choices made are intentional (and document them in design.md); make the desk feel special and something humans would actually enjoy using.

*Note:* The AI built "The Desk", a Liquid Glass dashboard (`frontend/`, React 19 + Vite + TypeScript) on port 5173 that calls the backend on port 8000. The backend's CORS allows the Vite origin. The page has:
- a ticket rail; resolved tickets get a stamped seal and move under a "Resolved" divider
- an **Agent Floor**: the five agents in a pentagon with their own colors; status rings for thinking, using a tool, asking, or done; speech bubbles; and delegation lines that glow and flow from asker to asked
- three tabs: Live feed, a Recap that opens on its own when a run finishes (one card per agent), and Drafts styled as unsent letters
- a cash card whose balance counts down after a payment
- an approvals inbox with a "Signing as" name and a two-click "Approve & pay"

It tested the whole flow in a browser against a scratch database: started ticket 102 from the UI, watched Facilities → Accounting light up live, approved the $2,400 rent (the balance counted down $3,400 → $1,000), and watched the resumed run mark the ticket resolved. It checked light and dark mode, then wrote `output/design.md` explaining each design choice.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 9: Resolve the tickets

### Prompt 1
> Problem 9: Resolve the tickets
>
> Before testing the agents on a full run over the three tickets, reset the working DB again and start clean. Note the starting checking balance. Then, run all three tickets on the board until each is resolved. Open the app in my native browser so I can watch.
>
> Update output/desk_tickets.html from Problem 6 and on each ticket tab, fill in the "Actual" section from the run, indicating which agents worked, what they delegated, and which tools they used. Keep the "Expected" section from before unchanged. Write a brief sentence noting whether the Actual differed from the Expected, and if so, how/where.
>
> On the cash tab of the same output/desk_tickets.html, itemize the money:
>
> * Starting checking balance (after the reset)
> * For each ticket, how cash changed when that ticket resolved, and why (which pay/purchase, dollar amount, etc.)
> * Ending checking balance, which must match cash_accounts in the working database
>
> Ensure the cash math is correct (graders will be checking that the cash math is correct, not just whether the board shows every ticket resolved). Also save:
>
> * output/resolved_tickets.json (id, final status, short outcome, what each agent contributed, and any human approvals for each ticket)
> * output/resolved_board.html (a page that can be double-clicked with a screenshot of the React board for EACH of the resolved tickets, i.e., 101, 102, and 103)
>
> Append these real runs to output/audit_trail.json. Finish the harness so it covers the tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

*Note:* Before the run, the AI found that the Boss prompt's definition of `resolved` meant tickets 101 (waiting on a vendor) and 103 (a restock it couldn't afford) could never reach it. It rewrote the definition as "the shop has done everything it can right now": a paid order in transit counts, and so does a recorded decision not to spend.

The AI then:
- reset the working DB through the API (starting checking **$3,400.00**)
- opened the desk in the user's browser and queued tickets 101, 102 and 103
- left every payment approval to the user, who approved all three on the dashboard: invoice 501 $840, rent $2,400, and a 1-tee purchase order $8

All three tickets were resolved after 6 team runs, ending at **$152.00**, which matches `cash_accounts`. The AI filled the Actual and Cash tabs from the audit trail and database, left the Expected sections unchanged (checked with a diff), and wrote `resolved_tickets.json` (cash math checked in code). It saved two embedded screenshots per ticket in `resolved_board.html` and finished the harness with the board tables, a run guide, and the run results.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 10: Reflection

### Prompt 1
> Problem 10: Reflection
>
> Write to the Reflection tab in output/desk_tickets.html my reflection on the following questions:
>
> * How would you evaluate the performance of the agents on each ticket and why?
> * For each ticket, how did the Actual run compare to the Expected plan?
> * What would have been simpler as one agent with tools, and why?
> * Describe three new problems that Campus Customs might face that this agent team could solve with the tools we built
> * Describe three new problems Campus Customs might face that this agent team could NOT solve with the tools we built (and explain the tools and/or agents we would need in order to solve them)
>
> My brief reflection is below -- clean it up and make it more detailed/thorough:
>
> "The run handled all three tickets correctly but inefficiently. Ticket #101 (tee) had accurate facts and the right sequence (pay the blocked vendor's overdue invoice, then order, then tell the customer 09-05) but took three runs and about 135k tokens and left cluttered duplicate drafts. Ticket #102 (rent) was correct and fast apart from an unneeded Customer Service detour and a pointless resume after approval. Ticket #103 (hoodies) showed sound judgment: a 10% discount that stayed above cost, and a declined $264 restock because only $160 was left, though the Boss's stated reasoning was slightly off. The main paths matched the plan, but the peer-to-peer delegations did not, and the whole thing cost about 254k tokens, which suggests a single agent or plain workflow code would have done these tickets more cheaply. The team's real value is permissions and customer-facing voice, not capability. New problems it could solve today include a mug order, a size swap, and a bulk discount filled from stock. Problems it couldn't solve require recording sales and cash in, adjusting inventory, real email intake and sending, and forward-looking planning. That last gap is the biggest risk: the shop is down to $152 with $2,400 rent coming due, and no agent can forecast or act on it."
>
> Ensure every answer is tied to THIS app and the three tickets that were ran (use the ticket tabs and Cash tab on the same page as evidence). Avoid generic AI slop without Campus Customs details.

*Note:* The AI expanded the user's reflection into the Reflection tab, one section per question, using evidence from the ticket tabs, the Cash tab, `audit_trail.json`, and the working database:
- **Per-ticket numbers:** runs, model calls and tokens for each ticket (135,149 / 71,935 / 47,173).
- **Why #101 cost so much:** Inventory ran twice in one run, and three drafts were left for Tauhid.
- **#103's reasoning:** "rent takes priority" pointed at the October rent, which $160 couldn't cover either.
- **Problems the team could solve,** with real figures: a Crest Mug order from Elm City Gifts ($42, arrives 09-03), a size-M swap (5 in stock), and 30 caps at 15% off ($561.00).
- **Problems it couldn't solve,** each with the tools and agents needed: recording sales and inventory, email intake and sending, and cash forecasting for $152 against $2,400 due 2026-10-02.

The AI re-checked every number against the data and confirmed the tab renders.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---

## Problem 11: Submit to GitHub

### Prompt 1
> Problem 11: Submit to GitHub
>
> Push the code to a public GitHub repository so graders can clone it. Give me the repo URL in the chat. Also, put the repo URL in output/github_url.txt
>
> Do NOT put the real .env in the GitHub repo. DO include both database files under data/ (the original and the working copy) so graders can easily run the app.
>
> The expected file layout is attached again. README should explain how to copy the original DB to the working copy when a clean run is needed, how to start the MCP server, how to start the FastAPI backend, how to start the React board, and how to reset the DB before a full three-ticket run.
>
> *(Attached: screenshot of the required `hw5/` folder structure.)*

*Note:* The AI first stopped the backend and dashboard so the working database was settled (integrity ok, $152.00, all tickets resolved). It then wrote `hw5/README.md` covering:
- setup
- the two database files and copying the original over the working copy
- starting the MCP server, the FastAPI backend, and the React board
- three ways to reset before a full run (board button, API, file copy)

It checked every file for the real Portkey key and other tokens (none found). Following the Homework 4 setup, it published only the `hw5/` folder (plus a short root README) to the public repo `ake-k/campus-customs-hw5`, with both database files included and `.env`, `.venv`, `node_modules` and caches excluded. The URL is in `output/github_url.txt`.

**Follow-up needed?** No. The prompt was clear and was completed as asked.

---
