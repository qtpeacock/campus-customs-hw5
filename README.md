# Campus Customs Multi-Agent Operations (HW5)

An agent team that runs the Campus Customs shop board. Open tickets (customer orders, rent, unpaid bills, discount requests) are worked by five agents: **Boss, Inventory, Accounting, Facilities and Customer Service**. A person watches them on a React dashboard and approves anything that spends money.

The app has three pieces that talk to each other:

```
React dashboard (frontend/, http://localhost:5173)
   │  calls http://localhost:8000/api/...
   ▼
FastAPI backend + agent team (backend/main.py, http://localhost:8000)
   │  every shop fact and change goes through MCP (stdio)
   ▼
MCP server (mcp_server/server.py, FastMCP, 19 tools)
   ▼
SQLite working copy: data/campus_customs_new.db
```

Every agent uses **gpt-6-luna** through Portkey. Agents can only *request* payments, orders and discounts. Cash moves only when a person clicks **Approve & pay**.

## What's in the repo

```
hw5/
├── AI_prompts.md            the prompts I gave my vibe coder, problem by problem
├── requirements.txt         Python packages
├── .env.example             template for your .env (the real .env is never committed)
├── .gitignore
├── .mcp.json                registers the MCP server for Claude Code
├── README.md
├── data/
│   ├── campus_customs.db        original database (never changed; the reset point)
│   └── campus_customs_new.db    working copy the app reads and writes
├── mcp_server/
│   ├── server.py            the Campus Customs MCP server (19 tools)
│   └── README.md
├── frontend/                React + Vite + TypeScript dashboard (the "Ops Desk")
├── backend/
│   ├── main.py              the agent team, audit trail, FastAPI routes and command line
│   ├── models.py            data types
│   └── prompts/             one prompt per agent: boss, inventory, accounting, facilities, customer_service
└── output/
    ├── harness.md           the full spec: tables, MCP tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json       MCP tool tests from Claude Code
    ├── desk_tickets.html    plan vs. actual for each ticket, the cash ledger, and the reflection
    ├── design.md            dashboard design choices
    ├── resolved_tickets.json
    ├── resolved_board.html  a screenshot of the board for each resolved ticket
    ├── audit_trail.json     every agent-loop step (append-only)
    └── github_url.txt
```

## What you need

- **Python 3.11+** (built and tested on 3.13)
- **Node.js 20+** and npm (tested on Node 24)
- A **Portkey API key** that can reach `gpt-6-luna`

## Setup (once)

From the repo folder:

1. **Your key.** Copy `.env.example` to `.env` and put your key in it:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` so it says `PORTKEY_API_KEY=...`. The backend reads it from there, and `.env` is in `.gitignore`.
2. **Python packages:**
   ```bash
   python -m venv .venv
   ```
   ```bash
   .venv/Scripts/python.exe -m pip install -r requirements.txt
   ```
   On macOS or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python.exe`, here and below.
3. **Dashboard packages:**
   ```bash
   cd frontend && npm install
   ```

## The two databases

Both databases are committed under `data/`, so the app runs right after cloning.

- `data/campus_customs.db` is the **original**. Nothing ever writes to it, and it's the reset point.
- `data/campus_customs_new.db` is the **working copy**. The MCP server and backend read and write only this file. As committed, it holds the **end state of my graded full run**: all three tickets resolved, checking at **$152.00**. See `output/desk_tickets.html` → Cash.

**When you need a clean run, copy the original database onto the working copy.** Do it with the backend stopped, or use the Reset button described below:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

In Windows PowerShell:

```bash
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
```

## Run the app

Use three terminals, all starting in the repo folder.

### 1. Start the MCP server

```bash
.venv/Scripts/python.exe mcp_server/server.py
```

This runs the Campus Customs MCP server over stdio, as a standalone check. **For the app itself you can skip this step:** the FastAPI backend starts its own copy of the server automatically, pointed at `data/campus_customs_new.db`. Claude Code also starts it from `.mcp.json` when a session opens in this folder. (`.mcp.json` uses the Windows path `.venv/Scripts/python.exe`; on macOS or Linux, change it to `.venv/bin/python`.)

### 2. Start the FastAPI backend

Activate the virtual environment, then start uvicorn from the `backend/` folder:

```bash
.venv\Scripts\Activate.ps1
```
(macOS or Linux: `source .venv/bin/activate`)

```bash
cd backend
```

```bash
uvicorn main:app --reload --port 8000
```

The backend is now at http://localhost:8000, with interactive docs at http://localhost:8000/docs. It allows the dashboard's origin (`http://localhost:5173`).

### 3. Start the React board

```bash
cd frontend
```

```bash
npm run dev
```

This opens the Ops Desk at http://localhost:5173.

## A full three-ticket run

1. **Reset the database first.** Click **↺ Reset board** in the top-right of the dashboard, or call the reset route:
   ```bash
   curl -X POST http://localhost:8000/api/reset
   ```
   You can also use the copy command above. Checking goes back to **$3,400.00**, tickets 101–103 reopen, and the board's approvals and drafts are cleared. The audit trail is append-only and is never wiped.
2. **Run the team on each ticket, oldest first.** Click **#101**, then **▶ Run agent team**, and watch the Handsome Dans and the live feed. When it finishes, do the same for **#102**, then **#103**. Only one run happens at a time.
3. **Approve or reject** each request under **Your call**. Type your name in **Approving as** first; the buttons stay off until you do. For ticket 101, approve the invoice payment *before* the purchase order, because the vendor won't ship while its invoice is unpaid and the app refuses the order until then.
4. A ticket **resolves automatically** when its last request is decided, with confetti. Checking should end at **$152.00**: $3,400 − $2,400 rent − $840 invoice 501 − $8 tee order. The hoodie discount moves no cash.

You can also run the team without the dashboard:

```bash
.venv/Scripts/python.exe backend/main.py board
```

The other forms are `… ticket 101` and `… ask Inventory "question"`.

## Rules the app enforces

- "Today" is `desk.date_today` (2026-08-31), never the real clock.
- Agents only *request* payments, purchase orders and discounts. Cash moves only through `POST /api/approvals/{id}/approve` after a person clicks Approve. The approver must be a person, not an agent name.
- No negative balances: requests and payments the cash can't cover are refused. Cash only goes out; there's no revenue.
- A vendor with an open unpaid invoice won't ship, so its purchase orders stay blocked until the invoice is paid.
- Customer messages are drafts only. Nothing is ever emailed.
- Only `gpt-6-luna`, with token caps per task and per response, and an append-only audit trail of every step.

The details are in `output/harness.md`.
