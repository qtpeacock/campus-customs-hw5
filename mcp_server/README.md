# Campus Customs MCP server

This is the shared toolbox for the Campus Customs agent team. Boss, Inventory, Accounting, Facilities and Customer Service all look things up and put work on the board through these tools. It is the only way the agents touch shop data: there is no second shop-tools layer. It's built with [FastMCP](https://gofastmcp.com) and lives in `server.py`.

## Database

The server reads and writes **`data/campus_customs_new.db`**, which is the working copy. It never opens the original `data/campus_customs.db`, so the original stays a clean reset point. To start over, copy the original onto the working copy. Tests can set `CAMPUS_CUSTOMS_DB` to point at a scratch copy instead.

The tools only return what's in the database. When a result includes a worked-out value (shortfall, margin, days overdue, cash available), it's simple arithmetic on database values, and dates are measured against `desk.date_today`, not the real clock. A missing ticket, SKU, invoice or lease comes back as `found: false` (or `ok: false`) with an error message. The tools never guess.

On first use the server adds three **board tables** to the working copy: `approvals` (requests waiting for a human), `drafts` (customer messages, never sent) and `ticket_updates` (every note and status change).

## Tools (19)

### Reading the board and the shop

| Tool | Reads | Returns |
|---|---|---|
| `get_shop_date()` | `desk` | The shop's "today" and desk notes. |
| `list_tickets(status="open")` | `tickets` | Tickets with that status (or `"all"`), oldest first. |
| `get_ticket(ticket_id)` | `tickets`, `ticket_updates`, `approvals`, `drafts` | One ticket plus everything already on the board for it. |
| `check_stock(sku, size, qty_needed?)` | `inventory` | Units on hand for that SKU and size, the shortfall and `can_fill_from_stock` when `qty_needed` is given, and the other sizes on hand. |
| `get_pricing(sku, qty?, discount_pct? or unit_price?)` | `pricing`, `inventory` | Unit cost, list price, and margin at list and at a proposed price, with totals for a qty. `below_cost` flags a losing price. |
| `list_vendors()` | `vendors`, `invoices`, `desk` | Every vendor's specialty, lead days, open invoices, `will_ship`, and earliest arrival if ordered today. |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | One invoice: amount, due date, status, days overdue, its vendor, the vendor's open invoices and `vendor_will_ship`. |
| `list_unpaid_invoices()` | `invoices`, `vendors`, `desk` | Every open invoice with days overdue, and the total owed. |
| `get_lease(lease_id)` | `leases`, `desk` | Space, landlord, monthly rent, next due date and days until due. |
| `get_cash_position()` | `cash_accounts`, `approvals` | Balance, cash already committed to pending or approved requests, and what is still available. |
| `list_approvals(status="pending", ticket_id?)` | `approvals` | Approval requests by status (or `"all"`), optionally for one ticket. |

### Putting work on the board (never moves money, never sends anything)

| Tool | Reads → writes | What it does |
|---|---|---|
| `request_payment(ticket_id, kind="invoice"\|"rent", ref_id, requested_by, reason)` | `invoices`/`leases`, `cash_accounts` → `approvals`, `ticket_updates` | Files a **pending** request to pay an open invoice or rent. The amount comes from the database. It refuses if the invoice isn't open, the request is a duplicate, or available cash can't cover it. |
| `request_purchase_order(ticket_id, vendor_id, sku, size, qty, requested_by, reason)` | `vendors`, `inventory`, `pricing`, `invoices`, `cash_accounts` → `approvals`, `ticket_updates` | Files a **pending** restock request costed at qty × unit cost. It's marked blocked if the vendor has open invoices, and refused if cash can't cover it. |
| `request_price_override(ticket_id, sku, size, qty, requested_by, reason, discount_pct? or unit_price?)` | `pricing`, `inventory` → `approvals`, `ticket_updates` | Files a **pending** discount request with its margin. It refuses a price below cost or at or above list. No cash moves. |
| `draft_customer_message(ticket_id, recipient, subject, body, written_by)` | → `drafts`, `ticket_updates` | Saves a message as a **draft**. Nothing is sent. |
| `add_ticket_note(ticket_id, agent, note)` | → `ticket_updates`, `tickets.status` | Records a finding. The first note moves an open ticket to `in_progress`. |
| `set_ticket_status(ticket_id, status, agent, note)` | `approvals` → `tickets.status`, `ticket_updates` | Moves a ticket to `open`, `in_progress`, `waiting_approval` or `resolved`. A ticket can't be resolved while its approvals are still open, can't be set to `waiting_approval` when nothing is waiting, and can't be changed once it's resolved. |

### Human-only (the dashboard calls these after a person clicks a button. No agent sees them.)

| Tool | Reads → writes | What it does |
|---|---|---|
| `approve_request(approval_id, approved_by, note?)` | `approvals`, `invoices`, `vendors` → `cash_accounts`, `payments`, `invoices`/`leases`, `approvals`, `ticket_updates` | **The only tool that spends cash.** For a payment or purchase order it takes the amount out of checking, adds a `payments` row with the approver's name, and updates the relevant table: the invoice becomes `paid`, the lease's `next_due` moves forward a month, or the order is placed. It refuses if the balance would go negative, if a purchase order's vendor still has an open invoice, if the request isn't pending, or if the approver is an agent. A price override is just marked approved. |
| `reject_request(approval_id, decided_by, note)` | → `approvals`, `ticket_updates` | Marks a pending request rejected, which frees the cash it was holding. |

The backend gives each agent only the tools its role needs (see `ROLES` in `backend/main.py`). Only Accounting can file requests, only Customer Service can write drafts, only Boss can set a ticket's status, and no agent gets the human-only tools. `backend/main.py` calls them from `POST /api/approvals/{id}/approve` and `/reject`.

## Run

It needs Python 3.10+ and the packages in `requirements.txt`. From the `HW5/` folder:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe mcp_server/server.py
```

This starts the server over stdio. On macOS or Linux, use `.venv/bin/python` instead. The FastAPI backend (`backend/main.py`) starts its own copy of the server the same way, so for the app you don't need to start it separately.

## Connect to Claude Code

`.mcp.json` at the `HW5/` root registers the server as `campus-customs`. Claude Code starts it automatically when a session opens in `HW5/`, and the tools show up as `mcp__campus-customs__<tool>`. The Problem 4 smoke test is in `output/mcp_smoke.json`.
