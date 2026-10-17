# The Desk: dashboard design

**What it is:** the React + Vite + TypeScript dashboard in `frontend/` where a person watches the Campus Customs agent team work tickets and approves every payment. Start it with `npm run dev` (http://localhost:5173). It talks to the FastAPI backend on port 8000.

**Design goal:** make watching agents feel like sitting in a small, calm operations room, not reading a log file. The person should always know three things at a glance:
1. **What is happening right now**: who is working and who asked whom.
2. **What needs me**: payments waiting for a signature.
3. **What it cost**: how much money is left.

Every choice below serves one of those three.

---

## 1. Visual language: Liquid Glass

The project's design rule is Apple's Liquid Glass, so the desk is built from **frosted glass panels floating over slowly drifting color fields**:
- **Panels:** `backdrop-filter: blur(30px) saturate(180%)`, a hairline white edge, a soft shadow, and a top highlight so each panel catches light like a pane of glass.
- **Background:** three large blurred color blobs (blue, pink, mint) drift over about 28 seconds.
  - **Why:** the room feels alive even when the team is idle, and the motion is slow enough not to compete with the real activity.
- **Type and shape:** the system San Francisco font, generous 20–24 px corner radii, and pill-shaped controls (segmented tabs, status pills, buttons). It's quiet and native-feeling on a Mac and doesn't call attention to itself.
- **Light and dark:** both are fully supported through `prefers-color-scheme`. The dark room uses deeper versions of the same fields so agent colors stay readable.
- **Reduced motion:** every animation is switched off for people who ask for it (`prefers-reduced-motion`).

**Why glass for an ops tool:** a translucent surface makes the layers obvious (board, floor, money) without heavy borders or boxes. The glass stays neutral, so **color is reserved for meaning**: agents, money, and status.

## 2. Layout: a three-column room

```
┌ Top bar: The Desk · shop date · model · team status · Fresh start ┐
│ Board rail  │ Ticket hero                         │ Checking (cash)  │
│  #101       │ Agent Floor (live pentagon)         │ Approvals inbox  │
│  #103       │ Live feed | Recap | Drafts          │                  │
│  ─Resolved─ │                                     │                  │
│  #102 ✓     │                                     │                  │
└─────────────┴─────────────────────────────────────┴──────────────────┘
```

- **Left, the board:** the tickets, like cards pinned to a wall. You pick one; you don't hunt for it.
- **Center, the stage:** the selected ticket. Its facts come first, then the agents working on it, then the detail of what they said.
- **Right, money:** cash and approvals sit together on purpose. The moment a payment request appears, you see in the same glance how much cash it would use.
- **Fixed in place:** the rail and the money column are sticky. While you scroll through a long agent conversation, the board and your checkbook stay in view.
- **Responsive:**
  - below 1240 px wide, money moves under the stage as two side-by-side cards;
  - below 860 px, everything stacks in one column.

## 3. The Agent Floor: how agents read differently

This is the centerpiece and the most deliberate choice. Instead of a flat list, the five agents sit **in a pentagon**:
- the **Boss at the head**;
- **Inventory and Accounting** on either side;
- **Facilities and Customer Service** at the bottom.

**Every pair is joined by a faint line.** That's the full-connectivity rule drawn literally: any agent may ask any other, and you can see it.

### Each agent has its own color
The same color is used everywhere: its ring on the floor, its name in the feed, its recap card, and its tool chips.

| Agent | Color | Initials | Why this color |
|---|---|---|---|
| Boss | violet `#7c5cff` | B | Authority and final calls; also the brand gradient, since the Boss runs the desk |
| Inventory | blue `#0a84ff` | In | Calm and factual: counts and lead times |
| Accounting | green `#22a06b` | Ac | Money |
| Facilities | orange `#f08c00` | Fa | Building and space; warm and physical |
| Customer Service | pink `#e8467c` | CS | Friendly and human: the voice to customers |

After a few minutes you stop reading names and just *see* who is talking.

### Agents show what they're doing (their "mood")
Each avatar's ring changes with what the agent is doing, so you can read the floor without reading text:
- **Thinking:** the ring gently breathes.
- **Using a tool:** a half ring spins, and the status line says which tool ("Using get cash position").
- **Asking or waiting on a teammate:** the ring turns dashed and rotates slowly.
- **Done:** a solid ring plus a green check badge.
- **Error:** a red ring plus a "!" badge.
- **Not involved in this run:** dimmed and desaturated, so the eye goes to the agents actually working.

### Delegations light up
When one agent asks another, the line between them **glows in the asker's color with dashes flowing toward the agent being asked**. When the reply comes back, the line settles into a faint solid trace, so after a run the floor keeps a picture of the conversation's shape. Blocked asks (a loop or the budget limit) show as red dashes.
- **Why:** with full connectivity, peer-to-peer asks (for example Facilities → Accounting) are the interesting part. A flowing line makes them obvious at a glance in a way a log line never would.

### Speech bubbles
Each agent's latest words appear in a small glass bubble under it (above it, for the bottom row), clamped to three lines and tinted with the agent's color. You get the gist on the floor and read it in full in the feed.

## 4. Feed, Recap, Drafts: three ways to read a run

A segmented control under the floor switches between them.

- **Live feed:** a chat-style timeline, one row per thing that happened, in the agent's color.
  - **What it shows:** asks appear as "Boss → Accounting asked" with the full question in an indented bubble. Replies use ↩. Tool calls are compact monospace chips with their arguments, and get a ✓ when the result comes back.
  - **What it hides:** the model's internal request/response bookkeeping, so the feed reads like a conversation, not a trace.
  - **Scrolling:** it follows new rows only if you're already near the bottom, so it never yanks you away from something you're reading.
- **Recap:** opens **automatically when a run you watched finishes**. That's the "so what happened?" moment.
  - **The Boss's call:** shown on top with its status and a highlighted "**Your move:**" line when a human is needed.
  - **One card per agent that took part:** who asked it, whom it asked, its final words, what it changed on the board (e.g. "Filed request #1 · Elm City Properties $2400"), its tools with counts, and its token use.
  - **Board history:** the ticket's status notes appear at the bottom.
- **Drafts:** customer messages shown as **paper letters**, in a serif typeface on warm off-white, with a red "**Draft · not sent**" stamp.
  - **Why:** the shop rule is that nothing is ever sent. Making drafts look like unsent letters, visibly different from everything else on the glass desk, makes that impossible to miss.

## 5. How resolved tickets show up

- **Status pills** use one color per state:
  - Open: neutral grey
  - In progress: blue
  - **Needs your approval: amber**
  - Waiting on vendor: violet
  - **Resolved: green**
  - Declined: red

  The same pill style appears on the card, in the ticket header, and in the recap.
- **While the team works,** the ticket's card shimmers with a moving sheen and its pill says "Team working". You can see which ticket is busy even when another one is selected.
- **When a ticket is resolved,** a green **RESOLVED** seal stamps onto its card with a short scale-in, and the card **moves below a "Resolved" divider**. The open tickets rise to the top, so the board always shows what's left to do. The rail header keeps count: "2 open · 1 resolved".
- **Pending approvals** show on the ticket card as an amber "1 to approve", so a waiting payment is visible from the board too.

## 6. How cash shows up

- **The checking balance is the largest number on the screen,** in a confident money-green with tabular figures. Cash is the one constraint that ties all the tickets together.
- **It counts down when money leaves.** After a payment, the number eases from the old balance to the new one over about a second, and a red "−$2,400.00" drops away beside it. You *see* the money leave. That matches the requirement that the balance drop after an approved payment, and it makes each approval feel like the real decision it is.
- **The meter** shows where the starting cash has gone:
  - **grey** for paid;
  - **amber stripes** for "awaiting you" (requests filed but not yet decided);
  - **green** for free.

  If approving everything waiting would overdraw the account, an amber note says so, before you click anything.
- **The payments list** shows every payment with **who approved it**: "Rent · approved by …  −$2,400.00". The human's name is part of the record, as it is in the database.

## 7. Approving a payment: designed for care

- **The inbox lives next to cash** and has a count badge. The empty state says: *"Agents can only prepare payments — they land here for you."* That states the safety rule in plain words.
- **You sign once.** A "Signing as" field holds your name, remembered in the browser. Approve and reject stay disabled until a name is there, because the backend records a named human on every payment.
- **Each request card** shows the kind (rent, vendor invoice, purchase order), the ticket, the amount, the payee, purchase-order details, the agent's reason, and who prepared it.
- **Approving takes two clicks, on purpose.** The first click arms the button: it turns into "Confirm · pay $2,400.00", pulses, and the card gets a green ring. The second click pays. If you don't confirm within 5 seconds, it disarms on its own.
  - **Why:** this is real money, so the extra click is cheap insurance against a stray one. Reject is a single click because it moves no money.
- **After approval:** a toast confirms "Paid $2,400.00 to Elm City Properties. Checking is now $1,000.00." The balance counts down, the request moves to the "decided" list, and the team **resumes the ticket automatically** so the Boss can finish it. You watch that happen on the floor.
- **If a payment is refused** (not enough cash, or the vendor has an unpaid invoice), the toast says why in red. The card stays as "approved by …, payment refused" with a "Try payment again" button, so nothing is silently lost.

## 8. The small things

- **The top bar** shows the shop's date (`desk.date_today`, never the computer's clock), the model in use (`gpt-6-luna`), and a team-status light: green when idle, a pulsing blue ping while working, red if the backend is offline. If the backend is unreachable, a banner says exactly how to start it.
- **Fresh start** (reset) asks to confirm inline ("Reset all tickets and cash?") and is disabled while the team is working, so a demo can't be wiped mid-run by accident.
- **Run button:** a bright gradient pill that says what it will do ("Start the team", "Run the team again", or "Team busy on another ticket"). While running, its dot pulses.
- **Facts strip:** each ticket's header shows its key facts from the database (on hand vs. needed, list/cost, rent and due date, linked invoice), and red marks the problem (a shortfall, an unpaid invoice). You know what the team is up against before you press go.
- **Polling:** the desk checks for new events every 1.2 s while the team works and every 4 s when idle, and fetches only new events since the last one it saw. It stays live without hammering the backend.

## 9. Why it should be enjoyable

The team's work is mostly invisible: model calls and database reads. The desk makes it something you can **watch** (rings breathing, lines flowing between colleagues, speech bubbles filling in), **understand** (the recap tells the story after the fact), and **control** (nothing costs money until you sign). The glass keeps it calm; the color carries the meaning; and the two moments that matter, a ticket getting resolved and money leaving the account, each get a small, satisfying animation so they feel as significant as they are.
