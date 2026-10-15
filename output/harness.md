# Campus Customs Multi-Agent Operations — Harness

The complete spec for Campus Customs Multi-Agent Operations: an agent team that works the shop's ticket board, and a human who watches the agents and approves anything that spends money. It has three pieces that talk to each other:

```
 Browser: Ops Desk dashboard (frontend/, React + Vite + TypeScript, http://localhost:5173)
   │  fetch → http://localhost:8000/api/...      (CORS allows the Vite origin)
   ▼
 FastAPI backend (backend/main.py, :8000)
   ├─ ticket runs → the agent team (backend/main.py, PydanticAI, gpt-6-luna via Portkey)
   │     Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service   (full connectivity: ask_teammate)
   ├─ human approve / reject, cash, reset, events (from output/audit_trail.json)
   │  every shop fact and every change goes through ↓  (stdio MCP connection)
   ▼
 Campus Customs MCP server (mcp_server/server.py, FastMCP, 19 tools)
   ▼
 SQLite working copy: data/campus_customs_new.db   (reset from data/campus_customs.db)
```

**Contents**
0. [How to run](#0-how-to-run)
1. [Database: tables and fields](#1-database)
2. [How the tables link](#2-how-the-tables-link)
3. [The three open tickets](#3-the-three-open-tickets)
4. [The first three MCP tools, tied to the tickets](#4-the-first-three-mcp-tools-problem-3-tied-to-the-tickets)
5. [The agent team](#5-the-agent-team)
6. [All MCP tools](#6-all-mcp-tools)
7. [Safety: shop rules, guardrails and token limits](#7-safety)
8. [Backend routes](#8-backend-routes-backendmainpy-fastapi)
9. [The dashboard](#9-the-dashboard-frontend)
10. [Full run results](#10-full-run-results-problem-9)

## 0. How to run

From the `HW5/` folder (Windows paths shown; on macOS or Linux use `.venv/bin/...`):

1. **Data:** unzip `data.zip` so `data/campus_customs.db` exists, then copy it to `data/campus_customs_new.db`.
2. **Key:** put `PORTKEY_API_KEY=...` in `HW5/.env` (or the folder above it). It is read from the environment and never printed or committed.
3. **Python:** `python -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements.txt` (fastmcp, pydantic-ai-slim, python-dotenv, fastapi, uvicorn).
4. **Backend:** `.venv\Scripts\Activate.ps1`, then `cd backend` and `uvicorn main:app --reload --port 8000`. It starts the MCP server itself. Docs are at http://localhost:8000/docs.
5. **Dashboard:** `cd frontend`, then `npm install` (first time only) and `npm run dev`. That opens http://localhost:5173.
6. **Before a full run:** press **↺ Reset board** on the dashboard (or `POST /api/reset`), so tickets, cash, invoices and leases start from the original values.
7. **Without the dashboard:** `python backend/main.py ticket 101`, `… board`, or `… ask Inventory "…"`.
8. **For the vibe coder (Claude Code):** `.mcp.json` registers the MCP server as `campus-customs` when a session opens in `HW5/`.

## 1. Database

| File | Role |
|---|---|
| `data/campus_customs.db` | Original. Never changed. Copy it over the working copy to reset before a full run. |
| `data/campus_customs_new.db` | Working copy. The MCP server and backend read and write this file. |

Shop "today" is `desk.date_today` = **2026-08-31**. SQLite foreign keys are declared but not enforced (`PRAGMA foreign_keys` is off), so the tools must check links themselves.

### desk

| Field | Type | Holds |
|---|---|---|
| `date_today` | TEXT | The shop's "today" (`2026-08-31`) |
| `notes` | TEXT | Free-text desk notes (empty) |

**Why it matters:** every agent measures "overdue" and "due soon" against this date, not the real clock.

### tickets

| Field | Type | Holds |
|---|---|---|
| `id` | INTEGER PK | Ticket number (101–103) |
| `type` | TEXT | `customer_order`, `rent_notice`, `price_override` |
| `requester` | TEXT | Who raised it (customer, landlord, student org) |
| `subject` | TEXT | Short title |
| `sku` | TEXT | Product asked for → `inventory`, `pricing` |
| `size` | TEXT | Size asked for → `inventory` |
| `qty` | INTEGER | Units asked for |
| `lease_id` | INTEGER FK | → `leases.id` |
| `invoice_id` | INTEGER FK | → `invoices.id` |
| `status` | TEXT | `open` (all three now) |
| `notes` | TEXT | The request in plain words |
| `created_at` | TEXT | ISO timestamp with offset |

**Why it matters:** this is the board. Boss reads each open ticket here, routes it to the other agents, and closes it when it's resolved.

### inventory

| Field | Type | Holds |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `name` | TEXT | Product name |
| `size` | TEXT PK | S/M/L/XL, or OS (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle |

**Why it matters:** Inventory checks stock by SKU *and* size here to spot shortfalls (the key is `sku` + `size`).

### pricing

| Field | Type | Holds |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `unit_cost` | REAL | What the shop pays per unit |
| `list_price` | REAL | What the shop charges per unit |

**Why it matters:** Accounting uses cost against price to check margins on discounts and to cost restock orders.

### vendors

| Field | Type | Holds |
|---|---|---|
| `id` | INTEGER PK | Vendor number |
| `name` | TEXT | Vendor name |
| `specialty` | TEXT | What they supply (apparel reprint, mugs and small goods, local courier) |
| `lead_days` | INTEGER | Days from order to delivery |

**Why it matters:** Inventory picks the restock vendor by specialty and uses `lead_days` to say when stock can arrive.

### leases

| Field | Type | Holds |
|---|---|---|
| `id` | INTEGER PK | Lease number |
| `space_name` | TEXT | The rented space |
| `landlord` | TEXT | Who is owed rent |
| `monthly_rent` | REAL | Rent amount |
| `next_due` | TEXT | Next rent due date |
| `notes` | TEXT | Free text (empty) |

**Why it matters:** Facilities checks rent amounts and due dates here. After an approved rent payment, `next_due` moves forward.

### cash_accounts

| Field | Type | Holds |
|---|---|---|
| `name` | TEXT PK | Account name (`checking`) |
| `balance` | REAL | Cash available ($3,400.00) |
| `date` | TEXT | Date of the balance |

**Why it matters:** Accounting checks this before any payment. The pay tool must refuse if the balance would go negative, and no money ever comes in.

### payments

| Field | Type | Holds |
|---|---|---|
| `id` | INTEGER PK | Payment number |
| `kind` | TEXT | What was paid (an invoice or rent) |
| `ref_id` | INTEGER | The invoice or lease id it pays (no FK, so `kind` says which table) |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Which `cash_accounts.name` it came from |
| `paid_at` | TEXT | When it was paid |
| `approved_by` | TEXT | The human who approved it (required) |

**Why it matters:** this is the record of approved payments (empty now). `approved_by` cannot be blank, which fits the rule that every payment needs human approval.

### invoices

| Field | Type | Holds |
|---|---|---|
| `id` | INTEGER PK | Invoice number |
| `vendor_id` | INTEGER FK | → `vendors.id` |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT | When it was due |
| `status` | TEXT | `open` (unpaid) or paid |
| `description` | TEXT | What it was for |

**Why it matters:** Accounting finds unpaid bills here, and Inventory checks it because a vendor with an open invoice will not ship new product.

## 2. How the tables link

```
tickets.invoice_id ──► invoices.id ──(vendor_id)──► vendors.id
tickets.lease_id   ──► leases.id
tickets.sku/size   ··► inventory (sku, size)     tickets.sku ··► pricing.sku
payments.ref_id    ··► invoices.id or leases.id   (which one depends on payments.kind)
payments.account   ··► cash_accounts.name
vendors ··► products only through vendors.specialty (no sku column)
```
`──►` is a declared foreign key; `··►` is a link by matching values only.

## 3. The three open tickets

> Sections 1–4 describe the **original** data, before the Problem 9 full run: invoice 501 open, rent due 2026-09-02, checking $3,400. For the end state (all three resolved, invoice 501 paid, rent paid through 2026-10-02, checking $152.00), see section 10.

**Ticket 101 — customer order (Tauhid Zaman): 1 × Classic Bulldog Tee, size S**
- `inventory`: CC-TEE-WHITE size S has **0** on hand (M 5, L 3, XL 2), so we're short 1.
- `invoice_id` 501 → **$840.00** to Bulldog Print Co ("Rush reprint CC-TEE-WHITE S"), due 2026-08-28, still `open`, which makes it **3 days overdue**.
- Bulldog Print Co (apparel reprint, 5 lead days) won't ship new product until invoice 501 is paid.
- `pricing`: $8.00 cost, $28.00 list, a $20.00 margin per unit.

**Ticket 102 — rent notice (Elm City Properties)**
- `lease_id` 1 → Chapel Street shop, **$2,400.00** a month, `next_due` 2026-09-02 (**due in 2 days**, not yet overdue).
- The requester matches `leases.landlord`.

**Ticket 103 — price override (Yale AI Club): 20 × Basic Hoodie, size M, bulk discount**
- `inventory`: CC-HOOD-NAVY size M has **8** on hand (S 4, L 14, XL 6), so we're short 12.
- `pricing`: $22.00 cost, $58.00 list, a $36.00 margin per unit at list. Any discount cuts into that $36.
- No invoice link, but the apparel restock vendor is Bulldog Print Co again, which is blocked by invoice 501.

**Cash picture:** checking has **$3,400.00**. Invoice 501 plus rent comes to $3,240.00, which leaves $160.00. Restocking the 12 missing hoodies at cost ($264.00) would push the balance $104.00 below zero, so the agents can't pay for everything at once.

## 4. The first three MCP tools (Problem 3, tied to the tickets)

The tools live in `mcp_server/server.py` (FastMCP) and every agent uses them. They read the working copy `data/campus_customs_new.db`, return only what's in the database, and measure dates against `desk.date_today`. A missing SKU, invoice or lease returns `found: false`; the tools never guess. See `mcp_server/README.md`.

| Ticket | Tools that unlock it |
|---|---|
| 101 — tee size S | `check_stock` + `get_invoice` |
| 102 — rent notice | `get_lease` |
| 103 — 20 hoodies, bulk discount | `check_stock` (+ `get_invoice` for the restock vendor) |

### `check_stock(sku, size, qty_needed?)`
- **Reads:** `inventory`. It returns the row for that `sku` + `size`, plus the SKU's other sizes.
- **Unlocks:** 101 and 103.
- **Why it's the right tool for 101:** Ticket 101 asks for 1 × CC-TEE-WHITE in size S. `check_stock("CC-TEE-WHITE", "S", 1)` returns 0 on hand and a shortfall of 1, so Inventory knows the order can't ship from the shelf and needs a reprint.
- **Why it's the right tool for 103:** The Yale AI Club wants 20 × CC-HOOD-NAVY in size M. `check_stock("CC-HOOD-NAVY", "M", 20)` returns 8 on hand and a shortfall of 12, so Boss knows any bulk discount also depends on restocking 12 hoodies.

### `get_invoice(invoice_id)`
- **Reads:** `invoices` joined to `vendors`, plus `desk.date_today`.
- **Unlocks:** 101, and the restock behind 103.
- **Why it's the right tool for 101:** Ticket 101 carries `invoice_id` 501. `get_invoice(501)` shows $840.00 owed to Bulldog Print Co, 3 days overdue as of 2026-08-31, with `vendor_will_ship: false`. That's exactly why the size-S tee can't be reprinted until Accounting gets that bill approved and paid.
- **Why it matters for 103:** Bulldog Print Co is also the apparel-reprint vendor (5 lead days) for the 12 missing hoodies. So the same `vendor_will_ship: false` means 103's restock is blocked by invoice 501 too.

### `get_lease(lease_id)`
- **Reads:** `leases`, plus `desk.date_today`.
- **Unlocks:** 102.
- **Why it's the right tool for 102:** Ticket 102 is Elm City Properties' rent notice, linked by `lease_id` 1. `get_lease(1)` confirms from the lease itself, not the email, that $2,400.00 is due 2026-09-02, 2 days from today, and that the landlord matches the requester. Facilities can then hand Accounting the exact amount to queue for approval.

Problem 5 grew the server to 17 tools. The full list is in section 6.

## 5. The agent team

Five PydanticAI agents work the board. They share one MCP connection, one model and one audit trail, and every agent can hand work to every other (**full connectivity**).

| Agent | Job | MCP tools it can see | Hands back |
|---|---|---|---|
| **Boss** | Reads each ticket, routes work to teammates, checks their answers, makes the final call, sets the ticket status | `set_ticket_status`, plus read-only `check_stock`, `get_pricing`, `list_vendors`, `get_invoice`, `list_unpaid_invoices`, `get_lease`, `get_cash_position`, `list_approvals` + common | `BossDecision` |
| **Inventory** | Stock by SKU and size, shortfalls, which vendor can restock, lead times, whether the vendor will ship | `check_stock`, `list_vendors`, `get_invoice`, `get_pricing` + common | `TeamReport` |
| **Accounting** | Cash, invoices and margins. The **only** agent that can file payment, purchase-order and price-override requests for human approval | `get_cash_position`, `list_unpaid_invoices`, `get_invoice`, `list_vendors`, `get_pricing`, `get_lease`, `list_approvals`, `request_payment`, `request_purchase_order`, `request_price_override` + common | `TeamReport` |
| **Facilities** | The shop space: checks rent notices against the lease, judges urgency, hands rent to Accounting | `get_lease`, `get_cash_position`, `list_approvals` + common | `TeamReport` |
| **Customer Service** | Drafts replies to customers and other requesters. Drafts only, never sent | `draft_customer_message`, `check_stock`, `get_pricing`, `list_approvals` + common | `TeamReport` |

"Common" = `get_shop_date`, `list_tickets`, `get_ticket`, `add_ticket_note`. Every agent also has `ask_teammate(teammate, task)`.

**Where things are** (Problem 11 folded the earlier `agents.py`, `audit.py` and `team.py` into `main.py` to match the required repo layout)

| File | What it holds |
|---|---|
| `backend/prompts/boss.md`, `inventory.md`, `accounting.md`, `facilities.md`, `customer_service.md` | One detailed prompt per agent: job, teammates and when to ask them, tools, the shop rules that agent needs, what it must never do, and the shape of its answer |
| `backend/models.py` | Data types: `AgentName`, `TicketStatus`, `Fact`, `TeamReport`, `BossDecision`, `DelegationRefused`, `TeamDeps` / `TeamBudget` (state shared down a delegation chain), `AuditEntry` |
| `backend/main.py` | Everything that runs, in six labeled parts: (1) setup, model and token limits; (2) the append-only audit trail writer; (3) the five agents (each role's tool list, `ask_teammate`, and `run_agent`, the agent loop); (4) entry points that work a ticket, work the board, or ask one agent; (5) the FastAPI routes; (6) the command line: `python backend/main.py ticket 101`, `… board`, `… ask Inventory "…"`. |

**Model.** Every agent uses `gpt-6-luna` through Portkey (`PORTKEY_API_KEY` from `.env`), via the OpenAI-compatible Responses API. The model name is a constant in `backend/main.py` and is never read from the environment, so no other model can slip in. (The chat-completions endpoint rejects function tools for this model while it is reasoning, so the team uses `/v1/responses`.) Responses report the model as `gpt-6-luna-global`, Portkey's deployment name for `gpt-6-luna`, and that is what the audit trail's `model` field shows.

**Agent loop.** `run_agent()` steps through each run with `agent.iter()`: model request → model response (text and tool calls) → tool results → next request, until the agent calls `final_result` with its typed report. An output check sends the agent back if it tries to answer without making at least one MCP lookup. `work_board()` is the outer loop: Boss works each open ticket in turn.

**Delegation.** `ask_teammate` runs the teammate's own loop and returns its report. The teammate shares the asker's usage counter, so limits cover the whole tree. It refuses delegating to yourself, delegating back up the chain (no A → B → A cycles), going past depth 2, and going past 8 hand-offs per task. A refusal comes back as `ok: false` with the reason, so the agent finishes with what it has.

**Audit trail (`output/audit_trail.json`).** Append-only, never wiped. Every agent-loop step writes entries:
- `run_start`: the task and the delegation chain.
- `model_request`, then `model_response`: the model name, text, tool calls and tokens.
- `tool_call` (arguments) and `tool_result` (a shortened result, including a teammate's whole report).
- `retry` and `delegation_refused`.
- `run_end` or `run_error`: the output, tokens for this run and for the whole task, and the duration.

`root_run_id` groups a whole task, and `parent_run_id` and `depth` show who asked whom. Entries are written as the run goes, so a crash still leaves its history, using an atomic replace. Emails and card-like numbers are masked.

**Smoke test (scratch copy of the database, working copy untouched).** Boss on ticket 101 asked Inventory, Accounting and Customer Service. It filed approval #1 (pay invoice 501, $840) and #2 (purchase order, 1 × CC-TEE-WHITE S, $8; blocked until 501 is paid), saved draft #1 to Tauhid Zaman, and set the ticket to `waiting_approval`. No money moved. That took 18 requests, about 70k input and 3.3k output tokens.

## 6. All MCP tools

`mcp_server/server.py` reads and writes `data/campus_customs_new.db`. The request tools never move money, and drafts are never sent.

| Tool | Tables it uses | Reads / writes | Used by |
|---|---|---|---|
| `get_shop_date` | `desk` | read | all |
| `list_tickets` | `tickets` | read | all |
| `get_ticket` | `tickets`, `ticket_updates`, `approvals`, `drafts` | read | all |
| `check_stock` | `inventory` | read | Boss, Inventory, Customer Service |
| `get_pricing` | `pricing`, `inventory` (name) | read | Boss, Inventory, Accounting, Customer Service |
| `list_vendors` | `vendors`, `invoices`, `desk` | read | Boss, Inventory, Accounting |
| `get_invoice` | `invoices`, `vendors`, `desk` | read | Boss, Inventory, Accounting |
| `list_unpaid_invoices` | `invoices`, `vendors`, `desk` | read | Boss, Accounting |
| `get_lease` | `leases`, `desk` | read | Boss, Accounting, Facilities |
| `get_cash_position` | `cash_accounts`, `approvals` | read | Boss, Accounting, Facilities |
| `list_approvals` | `approvals` | read | Boss, Accounting, Facilities, Customer Service |
| `request_payment` | reads `invoices` or `leases`, `cash_accounts`; writes `approvals`, `ticket_updates` | write (request only) | Accounting |
| `request_purchase_order` | reads `vendors`, `inventory`, `pricing`, `invoices`, `cash_accounts`; writes `approvals`, `ticket_updates` | write (request only) | Accounting |
| `request_price_override` | reads `pricing`, `inventory`; writes `approvals`, `ticket_updates` | write (request only) | Accounting |
| `draft_customer_message` | writes `drafts`, `ticket_updates` | write (draft only) | Customer Service |
| `add_ticket_note` | writes `ticket_updates`, `tickets.status` (open → in_progress) | write | all |
| `set_ticket_status` | writes `tickets.status`, `ticket_updates`; reads `approvals` | write | Boss. It refuses to resolve while requests are open, refuses `waiting_approval` when nothing is waiting, and never changes a ticket that is already resolved. |
| `approve_request` | reads `approvals`, `invoices`, `vendors`; writes `cash_accounts.balance`, `payments`, `invoices.status` or `leases.next_due`, `approvals`, `ticket_updates`, and `tickets.status` (→ resolved once the ticket's last request is decided) | write (**spends cash**) | **Humans only**, via `POST /api/approvals/{id}/approve` |
| `reject_request` | writes `approvals`, `ticket_updates`, and `tickets.status` (→ resolved once the ticket's last request is decided) | write | **Humans only**, via `POST /api/approvals/{id}/reject` |

The last two (added in Problem 7) are never given to an agent: `backend/main.py` asserts that no role's tool list includes them, and `approve_request` refuses an agent's name as the approver.

**Board tables the MCP server adds** to the working copy on first use (a reset starts them empty):
- `approvals`: requests waiting for a human, with the kind, amount, status (pending/approved/rejected/paid), who asked and why.
- `drafts`: customer messages, with status `draft`.
- `ticket_updates`: every note and status change, by agent.

## 7. Safety

**The shop rules, and where each one is enforced.** Each rule is enforced in code, not just stated in a prompt.

| Shop rule | Enforced by |
|---|---|
| `desk.date_today` is "today" | Every date calculation in the MCP tools uses `_today()` (`desk.date_today`), never the real clock. `get_shop_date` gives agents the date, and every prompt repeats the rule. |
| Vendor lead times come from `vendors` | `list_vendors`, `get_invoice` and `request_purchase_order` read `vendors.lead_days`, and earliest arrival = shop date + lead days. |
| A vendor won't ship while it has an open unpaid invoice | `get_invoice` and `list_vendors` return `will_ship: false`. A purchase order to that vendor is marked blocked, and `approve_request` **refuses to place it** until the invoice is paid. |
| Human approval for any payment, and update the tables when paid | Agents only have `request_*` tools, which write `approvals` rows with status `pending`. Only `approve_request` spends cash, and only from `POST /api/approvals/{id}/approve` after a person clicks Approve on the dashboard. It refuses an agent's name as approver. In one transaction it updates `cash_accounts.balance`, adds a `payments` row (`approved_by` = the person), and sets `invoices.status = paid` or moves `leases.next_due` a month. |
| Not enough cash → the pay tool refuses, no negative balances | `request_*` refuses when balance minus committed requests can't cover the amount, and `approve_request` checks the balance again and refuses rather than going negative. |
| Cash only goes out | No tool adds money. `get_cash_position` and the prompts say sales never count as cash. |
| Reset before a full run | `POST /api/reset` and the dashboard's **Reset board** copy the original database over the working copy. |
| Never email customers or call vendors | No messaging tool exists. `draft_customer_message` saves to `drafts` with status `draft`, and nothing is ever sent. |
| Only `gpt-6-luna` | `MODEL_NAME` is a constant in `backend/main.py` and is never read from `.env`. The audit trail records the model of every response. |

**Guardrails for real customers and real money**
- **Humans approve all money.** Agents can only *request* payments, purchase orders and discounts (`approvals`, status `pending`). No agent has a tool that pays, orders or changes a price. Cash moves only when a person clicks Approve (`POST /api/approvals/{id}/approve` → `approve_request`). That step refuses again if the balance would go negative, or if a purchase order's vendor still has an open invoice.
- **Amounts come from the database, not the model.** Request tools look up the invoice amount, rent or unit cost themselves.
- **No negative balances.** Cash-out requests are refused if balance minus what is already committed can't cover them. No revenue is counted, and duplicate requests are refused.
- **No selling below cost.** Price overrides below unit cost (or at or above list) are refused.
- **The vendor rule is visible.** Purchase orders to a vendor with an open invoice are marked blocked.
- **Customers only get drafts.** There is no email tool. The Customer Service prompt keeps internal finances, vendor issues and approval ids out of messages and forbids promising unapproved discounts or dates.
- **Least privilege.** Each agent sees only the MCP tools its role needs. Only Boss can change ticket status, and a ticket can't be resolved while its approvals are open.
- **A person's decision is final.** Once a ticket is resolved (by a person deciding its last request, or by Boss), no agent can reopen it, and the dashboard won't start a run on a ticket whose requests are still waiting on a person. Problem 9 found a race where a run started during an approval reopened a ticket, and this closed it.
- **Grounded answers.** An output check rejects any answer made without an MCP lookup, and reports list each fact with its source tool.
- **Traceability.** An append-only, redacted audit trail records every step. The original database is never touched, and the API key is read from `.env` and never logged.
- **Still needed in a real business:** logins and roles for approvers, two-person approval and daily spending caps above a threshold, alerts on refusals and errors, and retention rules for personal data in drafts and logs.

**Limits that keep token use in check**
- Per top-level task (one ticket, or one question), shared by every teammate it asks: **40 model requests, 80 tool calls, 400k tokens** (`UsageLimits`). Hitting a cap stops the whole task.
- Per response: **3,000 output tokens max** and **low reasoning effort**. A normal step uses about 130 output tokens (90% use under 500). The cap was 6,000 until Problem 8 showed that about 1 in 17 responses looped to the cap. Report lists are also capped (10 facts, 8 actions, 6 blockers or next steps).
- Delegation: **depth 2**, **8 hand-offs per task**, no self-delegation, no cycles.
- **Tool-output only:** agents must finish by calling `final_result`. In an early smoke test, free-text answers ran to the token cap twice, and this closed that hole.
- Compact tool results, prompts that say to use what a teammate already found instead of repeating work, and `get_ticket` first so finished work isn't redone.

## 8. Backend routes (`backend/main.py`, FastAPI)

Start it from `backend/` with the HW5 venv active: `uvicorn main:app --reload --port 8000`. It serves http://localhost:8000, with interactive docs at `/docs`. CORS allows the dashboard on `localhost:5173`. Every route reads or changes shop data through the MCP server.

- `GET /api/health` reports whether the backend is up, the model, the MCP server, the database file, and any run in progress.
- `GET /api/tickets` returns every ticket with its status, whether it is `open` or `resolved`, and its approvals, drafts and updates from the board.
- `POST /api/tickets/{ticket_id}/run` starts the agent team (Boss first) on one ticket in the background and returns its `root_run_id`. It answers 409 if a run is already going, so only one runs at a time.
- `GET /api/runs` lists the ticket runs since the backend started, newest first.
- `GET /api/runs/{root_run_id}` gives one run's status (`running` / `done` / `failed`) and Boss's final decision.
- `GET /api/events?since=&limit=&ticket_id=&root_run_id=` returns recent agent events from `output/audit_trail.json`: what each agent said, which tools it used, and who it asked. Pass `next_since` back to get only new events.
- `POST /api/approvals/{approval_id}/approve` (body `approved_by`, `note`) records a person's approval. For a payment or purchase order this is the only thing that spends cash: it updates `cash_accounts`, `payments` and `invoices` or `leases`. It answers 409 when refused.
- `POST /api/approvals/{approval_id}/reject` (body `decided_by`, `note`) records a person's rejection and frees the cash the request was holding.
- `GET /api/cash` returns the checking balance from `cash_accounts`, plus what pending requests already hold and what is still available.
- `POST /api/reset` copies `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run. The audit trail is kept, and it answers 409 during a run.

*Windows note:* with `--reload`, uvicorn serves requests on an event loop that can't start subprocesses. The agents and their stdio MCP connection therefore run on their own background event loop (`TeamLoop` in `main.py`), and the routes hand work to it.

## 9. The dashboard (`frontend/`)

The **Ops Desk** is a React 19 + Vite 8 + TypeScript app (`npm run dev` → http://localhost:5173) that calls the backend directly at `http://localhost:8000` (`src/api.ts`). The look and the reasons for it are in `output/design.md`.

| Part | What it does | Routes it uses |
|---|---|---|
| Top bar scorecard | Checking balance, plus a bar that shrinks as money goes out (free / held for approvals / spent). A "−$X · what" chip appears after each payment. | `GET /api/cash`, `GET /api/tickets` (to total what was paid) |
| Team strip | Five SVG Handsome Dans (Boss, Inventory, Accounting, Facilities, Customer Service) showing who is working, waiting or done right now. Click a Dan to filter the feed. | `GET /api/events` |
| Ticket cards | The three tickets as game cards, with status and an Open → Agents → Your call → Done track. Click to select (also `#ticket-101` in the URL). | `GET /api/tickets` |
| Run agent team | Starts Boss on the selected ticket. One run at a time. | `POST /api/tickets/{id}/run`, `GET /api/runs/{id}` |
| Live feed | Every agent step as it happens (asks, lookups, board actions, reports), indented by who asked whom, with view filters. | `GET /api/events?root_run_id=…&since=…` (every 1.5 s) |
| What each agent did / Boss's call | One card per agent (answer, tools, who it asked), and Boss's final decision. | `GET /api/events`, `GET /api/runs` |
| Your call (approvals) | Pending payments, orders and discounts, each with **Approve & pay** and **Reject**. A person's name is required. Hovering previews the balance after paying. | `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject` |
| Drafts and board notes | Customer drafts (never sent) and every note or status change on the ticket. | `GET /api/tickets` |
| Reset board | Fresh start from the original data. | `POST /api/reset` |
| Celebration | Confetti, plus a wiggle dance by the agent who closed the ticket, when a ticket turns resolved. Off when the system asks for reduced motion. | (from the ticket status change) |

When a person decides the last open request on a ticket that was waiting for approval, `approve_request` / `reject_request` mark the ticket **resolved**, and the dashboard celebrates.

## 10. Full run results (Problem 9)

The board was reset (`POST /api/reset`, 2026-10-15 01:21:37 UTC) and the team worked 101 → 102 → 103. Quinn approved every request on the dashboard. All three tickets ended **resolved**.

| | Checking |
|---|---|
| Starting balance after the reset | **$3,400.00** |
| #101: approval #1, invoice 501 to Bulldog Print Co (−$840.00), and approval #2, purchase order for 1 × CC-TEE-WHITE size S (−$8.00) | −$848.00 |
| #102: approval #3, rent on lease 1 (−$2,400.00); `leases.next_due` → 2026-10-02 | −$2,400.00 |
| #103: approval #4, 10% price override ($52.20 a hoodie), no cash. The 12-hoodie restock ($264.00) was refused because only $152.00 was available | $0.00 |
| **Ending balance**, matching `cash_accounts.balance` = 152.0 and $3,400 − SUM(`payments.amount`) 3,248 | **$152.00** |

**How the team did against the plan (`output/desk_tickets.html`):**
- **101:** Boss → Inventory first, then Accounting, then Customer Service, exactly as planned. Facilities wasn't called.
- **102:** Boss → Facilities first, then **Facilities → Accounting** (the specialist-to-specialist hand-off the plan predicted), plus one extra Boss → Customer Service note to the landlord.
- **103:** took five runs. The first stalled because the ticket names no discount. The second filed the 10% override for approval. The third raced Quinn's approval. The fourth confirmed the restock can't be funded, and the cash refusal fired. The fifth resolved the ticket.

**Changes made during the run, each one recorded in the audit trail:**
1. Accounting prompt: when a customer asks for a discount without naming a number, propose one for human approval instead of waiting.
2. Boss prompt: never hold a ticket open for a customer's reply once the decision is made, every approval is decided, and the reply is drafted. A customer's answer arrives as a new ticket.
3. MCP `set_ticket_status`: a resolved ticket can't be moved, and `waiting_approval` needs something actually waiting.
4. Dashboard: "Run team" is disabled while requests wait on a person.

**Cost:** 7 team runs, 97 model requests, 411,842 input and 15,972 output tokens, no retries or refused hand-offs, and every response from gpt-6-luna.

**Evidence:** the Actual sections and Cash tab of `output/desk_tickets.html`, `output/resolved_tickets.json`, `output/resolved_board.html` (a board screenshot per ticket), and `output/audit_trail.json`. The full run starts at entry 601, and earlier entries are kept from the test runs.
