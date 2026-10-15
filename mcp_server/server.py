"""Campus Customs MCP server: the shared toolbox for every agent on the team.

Every tool reads and writes data/campus_customs_new.db (the working copy). The
original data/campus_customs.db is never opened here, so it stays a clean reset
point. Tests can point the CAMPUS_CUSTOMS_DB environment variable at a scratch
copy instead.

Shop facts come only from the database. Anything a tool works out (shortfall,
margin, days overdue, cash left) is plain arithmetic on database values, and
dates are measured against desk.date_today, never the real clock.

Agents never move money. The request_* tools only put a request on the board
(the approvals table) for a human to approve, and they refuse anything the cash
can't cover. Customer messages are saved as drafts and never sent. The two
human-only tools at the bottom (approve_request, reject_request) are called by
the dashboard backend after a person clicks a button. No agent is given them,
and approve_request is the only tool that spends cash.

Run (stdio):  python mcp_server/server.py
"""

from __future__ import annotations

import calendar
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, get_args

from fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", ROOT / "data" / "campus_customs_new.db"))

mcp = FastMCP("campus-customs")

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
TicketStatus = Literal["open", "in_progress", "waiting_approval", "resolved"]

# Requests that still hold cash: waiting for a human, or approved but not yet paid.
COMMITTED = ("pending", "approved")

# The board: what agents leave for humans. Created in the working copy on first
# use, so a reset (copying the original back) simply starts with an empty board.
BOARD_TABLES = """
CREATE TABLE IF NOT EXISTS approvals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     INTEGER NOT NULL REFERENCES tickets(id),
    kind          TEXT NOT NULL,      -- invoice_payment | rent_payment | purchase_order | price_override
    ref_id        INTEGER,            -- invoices.id, leases.id or vendors.id, depending on kind
    sku           TEXT,
    size          TEXT,
    qty           INTEGER,
    unit_price    REAL,
    amount        REAL NOT NULL,
    cash_out      INTEGER NOT NULL,   -- 1 if approving it spends cash
    account       TEXT,
    requested_by  TEXT NOT NULL,
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | paid
    shop_date     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT
);
CREATE TABLE IF NOT EXISTS drafts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id),
    recipient   TEXT NOT NULL,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    written_by  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    shop_date   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id     INTEGER NOT NULL REFERENCES tickets(id),
    agent         TEXT NOT NULL,
    status_before TEXT,
    status_after  TEXT,
    note          TEXT NOT NULL,
    shop_date     TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open the working copy and always close it. mode=rw fails if the file is
    missing instead of quietly creating an empty database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found. Copy data/campus_customs.db to "
            "data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(BOARD_TABLES)
        yield conn
    finally:
        conn.close()


def _today(conn: sqlite3.Connection) -> date:
    """The shop's "today" from desk.date_today."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()[0])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _money(x: float) -> float:
    return round(float(x), 2)


def _refuse(error: str, **detail: object) -> dict:
    return {"ok": False, "error": error, **detail}


def _ticket(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def _log_update(
    conn: sqlite3.Connection, ticket_id: int, agent: str, note: str, new_status: str | None = None
) -> tuple[str, str]:
    """Write one ticket_updates row and optionally move the ticket's status."""
    before = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()[0]
    after = new_status or before
    if after != before:
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (after, ticket_id))
    conn.execute(
        "INSERT INTO ticket_updates (ticket_id, agent, status_before, status_after, note, shop_date, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ticket_id, agent, before, after, note, _today(conn).isoformat(), _now()),
    )
    return before, after


def _resolve_account(conn: sqlite3.Connection, account: str | None) -> sqlite3.Row | dict:
    """The cash account to pay from: the one named, or the only one there is."""
    rows = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()
    if account is None:
        if len(rows) == 1:
            return rows[0]
        return _refuse("More than one cash account; name one.", accounts=[r["name"] for r in rows])
    match = next((r for r in rows if r["name"] == account), None)
    return match or _refuse(f"No cash account named {account!r}.", accounts=[r["name"] for r in rows])


def _committed(conn: sqlite3.Connection, account: str) -> float:
    """Cash already promised to requests that are pending or approved but unpaid."""
    return conn.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM approvals WHERE cash_out = 1 AND account = ? "
        f"AND status IN ({','.join('?' * len(COMMITTED))})",
        (account, *COMMITTED),
    ).fetchone()[0]


def _open_invoices(conn: sqlite3.Connection, vendor_id: int, today: date) -> list[dict]:
    rows = conn.execute(
        "SELECT id, amount, due_date, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()
    return [
        {**dict(r), "days_overdue": max(0, (today - date.fromisoformat(r["due_date"])).days)}
        for r in rows
    ]


def _cash_check(conn: sqlite3.Connection, account: str | None, amount: float) -> dict:
    """Refuse a cash-out request the account can't cover after what is already committed."""
    acct = _resolve_account(conn, account)
    if isinstance(acct, dict):
        return acct
    committed = _committed(conn, acct["name"])
    available = acct["balance"] - committed
    detail = {
        "account": acct["name"],
        "balance": _money(acct["balance"]),
        "already_committed": _money(committed),
        "available": _money(available),
        "amount": _money(amount),
    }
    if amount > available + 1e-9:
        return _refuse(
            "Not enough cash. Approving this would push the balance below zero once the "
            "requests already waiting are paid. Nothing was requested.",
            **detail,
        )
    return {"ok": True, **detail, "available_after_this_request": _money(available - amount)}


def _insert_approval(conn: sqlite3.Connection, **row: object) -> int:
    row = {**row, "shop_date": _today(conn).isoformat(), "created_at": _now(), "status": "pending"}
    cols = ", ".join(row)
    cur = conn.execute(f"INSERT INTO approvals ({cols}) VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    return cur.lastrowid


# ---------- Reading the board and the shop ----------


@mcp.tool
def get_shop_date() -> dict:
    """The shop's "today" (desk.date_today) and any desk notes.

    Use this date for everything time-related: what is overdue, how many days
    until something is due, when a restock could arrive. Never use the real clock.
    """
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    return {"date_today": row["date_today"], "notes": row["notes"]}


@mcp.tool
def list_tickets(status: str = "open") -> dict:
    """Tickets on the board from the tickets table, oldest first.

    status: "open", "in_progress", "waiting_approval", "resolved", or "all".
    Each ticket shows its type, requester, what they asked for (sku, size, qty,
    notes) and any linked lease_id or invoice_id.
    """
    with _connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM tickets ORDER BY created_at").fetchall()
        else:
            rows = conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY created_at", (status,)).fetchall()
    return {"status_filter": status, "count": len(rows), "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with everything already on the board for it.

    Reads tickets plus the board tables: the ticket's update history
    (ticket_updates), its approval requests (approvals) and its customer
    message drafts (drafts). Check this before acting so work is not repeated.
    """
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id)
        if ticket is None:
            return {"found": False, "error": f"No ticket with id {ticket_id}."}
        updates = conn.execute(
            "SELECT agent, status_before, status_after, note, created_at FROM ticket_updates "
            "WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
        approvals = conn.execute(
            "SELECT id, kind, ref_id, sku, size, qty, unit_price, amount, cash_out, status, requested_by, reason "
            "FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()
        drafts = conn.execute(
            "SELECT id, recipient, subject, body, written_by, status FROM drafts WHERE ticket_id = ? ORDER BY id",
            (ticket_id,)).fetchall()
    return {
        "found": True,
        "ticket": dict(ticket),
        "updates": [dict(r) for r in updates],
        "approval_requests": [dict(r) for r in approvals],
        "drafts": [dict(r) for r in drafts],
    }


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int | None = None) -> dict:
    """Units on hand for one SKU in one size, from the inventory table.

    Use for any ticket that asks for a product (customer orders, bulk or
    discount requests) to see whether the shop can fill it from stock.
    Pass qty_needed (the ticket's qty) to also get the shortfall.
    Also lists the other sizes of the same SKU and how many of each are on hand.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?",
            (sku,),
        ).fetchall()
    if not rows:
        return {"found": False, "error": f"No inventory rows for SKU {sku!r}."}

    match = next((r for r in rows if r["size"] == size), None)
    if match is None:
        return {
            "found": False,
            "error": f"SKU {sku!r} has no size {size!r} in inventory.",
            "sizes_in_inventory": [r["size"] for r in rows],
        }

    result = {
        "found": True,
        "sku": match["sku"],
        "name": match["name"],
        "size": match["size"],
        "qty_on_hand": match["qty"],
        "location": match["location"],
        "other_sizes": [
            {"size": r["size"], "qty_on_hand": r["qty"]} for r in rows if r is not match
        ],
    }
    if qty_needed is not None:
        result["qty_needed"] = qty_needed
        result["shortfall"] = max(0, qty_needed - match["qty"])
        result["can_fill_from_stock"] = match["qty"] >= qty_needed
    return result


@mcp.tool
def get_pricing(
    sku: str,
    qty: int | None = None,
    discount_pct: float | None = None,
    unit_price: float | None = None,
) -> dict:
    """Unit cost, list price and margin for one SKU, from the pricing table.

    Use to check margins before any discount or price override, and to cost a
    restock. Optionally pass a proposed discount_pct (e.g. 10 for 10% off list)
    OR a proposed unit_price to see the margin at that price, and qty to get
    totals. below_cost is true if the proposed price would lose money per unit.
    """
    sku = sku.strip().upper()
    if discount_pct is not None and unit_price is not None:
        return {"found": False, "error": "Pass discount_pct or unit_price, not both."}
    with _connect() as conn:
        row = conn.execute("SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        name = conn.execute("SELECT name FROM inventory WHERE sku = ? LIMIT 1", (sku,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No pricing row for SKU {sku!r}."}

    cost, list_price = row["unit_cost"], row["list_price"]
    result = {
        "found": True,
        "sku": sku,
        "name": name["name"] if name else None,
        "unit_cost": _money(cost),
        "list_price": _money(list_price),
        "margin_at_list": {
            "per_unit": _money(list_price - cost),
            "pct_of_price": round((list_price - cost) / list_price * 100, 1),
        },
    }
    price = None
    if discount_pct is not None:
        price = _money(list_price * (1 - discount_pct / 100))
    elif unit_price is not None:
        price = _money(unit_price)
    if price is not None:
        result["proposed"] = {
            "unit_price": price,
            "discount_pct_off_list": round((list_price - price) / list_price * 100, 1),
            "margin_per_unit": _money(price - cost),
            "margin_pct_of_price": round((price - cost) / price * 100, 1) if price else None,
            "below_cost": price < cost,
        }
    if qty is not None:
        result["totals"] = {
            "qty": qty,
            "cost": _money(cost * qty),
            "revenue_at_list": _money(list_price * qty),
            "margin_at_list": _money((list_price - cost) * qty),
        }
        if price is not None:
            result["totals"].update(
                revenue_at_proposed=_money(price * qty),
                margin_at_proposed=_money((price - cost) * qty),
                discount_given=_money((list_price - price) * qty),
            )
    return result


@mcp.tool
def list_vendors() -> dict:
    """Every vendor from the vendors table, with its open invoices from the invoices table.

    Use to pick who can restock (match the product to the vendor's specialty)
    and when it could arrive (lead_days from desk.date_today). will_ship is
    false while the vendor has any open (unpaid) invoice: a vendor will not ship
    new product until those are paid.
    """
    with _connect() as conn:
        today = _today(conn)
        vendors = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
        result = []
        for v in vendors:
            open_inv = _open_invoices(conn, v["id"], today)
            result.append({
                **dict(v),
                "open_invoices": open_inv,
                "open_total": _money(sum(i["amount"] for i in open_inv)),
                "will_ship": not open_inv,
                "earliest_arrival_if_ordered_today": (today + timedelta(days=v["lead_days"])).isoformat(),
            })
    return {"date_today": today.isoformat(), "vendors": result}


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """One vendor invoice from the invoices table, with its vendor from the
    vendors table.

    Use when a ticket has an invoice_id, or before ordering from a vendor:
    a vendor will not ship new product while it has any open (unpaid) invoice.
    Returns the amount, due date, status, days overdue as of desk.date_today,
    the vendor's specialty and lead_days, and every open invoice that vendor has.
    """
    with _connect() as conn:
        inv = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                      v.id AS vendor_id, v.name AS vendor_name,
                      v.specialty, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return {"found": False, "error": f"No invoice with id {invoice_id}."}
        today = _today(conn)
        open_rows = conn.execute(
            "SELECT id, amount, due_date FROM invoices "
            "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (inv["vendor_id"],),
        ).fetchall()

    is_open = inv["status"] == "open"
    days_past_due = (today - date.fromisoformat(inv["due_date"])).days
    return {
        "found": True,
        "invoice_id": inv["id"],
        "amount": inv["amount"],
        "due_date": inv["due_date"],
        "status": inv["status"],
        "description": inv["description"],
        "date_today": today.isoformat(),
        "is_overdue": is_open and days_past_due > 0,
        "days_overdue": max(0, days_past_due) if is_open else 0,
        "vendor": {
            "id": inv["vendor_id"],
            "name": inv["vendor_name"],
            "specialty": inv["specialty"],
            "lead_days": inv["lead_days"],
        },
        "vendor_open_invoices": [dict(r) for r in open_rows],
        "vendor_will_ship": not open_rows,
    }


@mcp.tool
def list_unpaid_invoices() -> dict:
    """Every open (unpaid) invoice from the invoices table, with its vendor, oldest due first.

    Use for the accounts-payable picture: what is owed, to whom, and how many
    days overdue each bill is as of desk.date_today.
    """
    with _connect() as conn:
        today = _today(conn)
        rows = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.description, v.id AS vendor_id, v.name AS vendor_name
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status = 'open' ORDER BY i.due_date"""
        ).fetchall()
    invoices = [
        {**dict(r), "days_overdue": max(0, (today - date.fromisoformat(r["due_date"])).days)} for r in rows
    ]
    return {"date_today": today.isoformat(), "count": len(invoices),
            "total_owed": _money(sum(i["amount"] for i in invoices)), "invoices": invoices}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """One lease from the leases table: the space, landlord, monthly rent and
    next due date.

    Use for rent notices and anything about the shop space. Also returns how
    many days until rent is due (negative means overdue) as of desk.date_today.
    """
    with _connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "error": f"No lease with id {lease_id}."}
        today = _today(conn)

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "notes": lease["notes"],
        "date_today": today.isoformat(),
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
    }


@mcp.tool
def get_cash_position() -> dict:
    """Cash on hand from cash_accounts, minus what approval requests already hold.

    already_committed adds up cash-out requests in the approvals table that are
    pending or approved but not yet paid. available is what is left for new
    requests. No money ever comes in: sales are not modeled, so never count
    future sales as cash.
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = []
        for a in conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall():
            committed = _committed(conn, a["name"])
            accounts.append({
                "name": a["name"],
                "balance": _money(a["balance"]),
                "balance_date": a["date"],
                "already_committed": _money(committed),
                "available": _money(a["balance"] - committed),
            })
        waiting = conn.execute(
            f"SELECT id, ticket_id, kind, amount, status FROM approvals WHERE cash_out = 1 "
            f"AND status IN ({','.join('?' * len(COMMITTED))}) ORDER BY id", COMMITTED).fetchall()
    return {
        "date_today": today.isoformat(),
        "accounts": accounts,
        "total_balance": _money(sum(a["balance"] for a in accounts)),
        "total_available": _money(sum(a["available"] for a in accounts)),
        "committed_requests": [dict(r) for r in waiting],
    }


@mcp.tool
def list_approvals(status: str = "pending", ticket_id: int | None = None) -> dict:
    """Approval requests on the board (approvals table) waiting for, or decided by, a human.

    status: "pending", "approved", "rejected", "paid", or "all". Optionally
    filter to one ticket_id. Check this before requesting anything so the same
    request is not filed twice.
    """
    sql, args = "SELECT * FROM approvals WHERE 1 = 1", []
    if status != "all":
        sql, args = sql + " AND status = ?", [status]
    if ticket_id is not None:
        sql, args = sql + " AND ticket_id = ?", [*args, ticket_id]
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY id", args).fetchall()
    return {"status_filter": status, "count": len(rows), "approvals": [dict(r) for r in rows]}


# ---------- Putting work on the board (never moves money, never sends anything) ----------


@mcp.tool
def request_payment(
    ticket_id: int,
    kind: Literal["invoice", "rent"],
    ref_id: int,
    requested_by: AgentName,
    reason: str,
    account: str | None = None,
) -> dict:
    """Ask a human to approve paying an open vendor invoice or a lease's rent.

    This does NOT pay anything. It adds a pending row to the approvals table.
    The amount always comes from the database (invoices.amount or
    leases.monthly_rent), never from the caller. It refuses if the invoice is not
    open, if the same payment is already waiting, or if cash on hand minus what
    is already committed can't cover it, because balances can never go negative.
    """
    with _connect() as conn:
        if _ticket(conn, ticket_id) is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        if kind == "invoice":
            inv = conn.execute("SELECT id, amount, status, vendor_id, description FROM invoices WHERE id = ?",
                               (ref_id,)).fetchone()
            if inv is None:
                return _refuse(f"No invoice with id {ref_id}.")
            if inv["status"] != "open":
                return _refuse(f"Invoice {ref_id} is {inv['status']!r}, not open; nothing to pay.")
            approval_kind, amount, what = "invoice_payment", inv["amount"], f"invoice {ref_id} ({inv['description']})"
        else:
            lease = conn.execute("SELECT id, monthly_rent, next_due, space_name FROM leases WHERE id = ?",
                                 (ref_id,)).fetchone()
            if lease is None:
                return _refuse(f"No lease with id {ref_id}.")
            approval_kind, amount = "rent_payment", lease["monthly_rent"]
            what = f"rent for {lease['space_name']} due {lease['next_due']}"

        dup = conn.execute(
            f"SELECT id, status FROM approvals WHERE kind = ? AND ref_id = ? "
            f"AND status IN ({','.join('?' * len(COMMITTED))})", (approval_kind, ref_id, *COMMITTED)).fetchone()
        if dup:
            return _refuse(f"Already requested: approval #{dup['id']} is {dup['status']}.", approval_id=dup["id"])

        cash = _cash_check(conn, account, amount)
        if not cash["ok"]:
            return cash
        approval_id = _insert_approval(
            conn, ticket_id=ticket_id, kind=approval_kind, ref_id=ref_id, amount=_money(amount), cash_out=1,
            account=cash["account"], requested_by=requested_by, reason=reason,
        )
        _log_update(conn, ticket_id, requested_by,
                    f"Requested human approval #{approval_id}: pay ${amount:,.2f} for {what}.")
        conn.commit()
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "pending",
        "kind": approval_kind,
        "pays": what,
        **{k: v for k, v in cash.items() if k != "ok"},
        "message": "Waiting for human approval. No money has moved.",
    }


@mcp.tool
def request_purchase_order(
    ticket_id: int,
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    requested_by: AgentName,
    reason: str,
    account: str | None = None,
) -> dict:
    """Ask a human to approve a restock order from a vendor.

    This does NOT place the order or pay. It adds a pending row to the approvals
    table. The cost is qty x pricing.unit_cost, taken from the database. It
    refuses an unknown SKU or size, a non-positive qty, a duplicate request, or
    one the available cash can't cover. If the vendor still has open invoices,
    the request is saved but marked blocked: the vendor won't ship until those
    invoices are paid. Also returns the earliest arrival (desk.date_today +
    lead_days) if it were ordered today.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return _refuse("qty must be at least 1.")
    with _connect() as conn:
        if _ticket(conn, ticket_id) is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        vendor = conn.execute("SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
                              (vendor_id,)).fetchone()
        if vendor is None:
            return _refuse(f"No vendor with id {vendor_id}.")
        item = conn.execute("SELECT name, qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            return _refuse(f"No inventory row for {sku} size {size}.")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return _refuse(f"No pricing row for {sku}; can't cost the order.")
        dup = conn.execute(
            f"SELECT id, status FROM approvals WHERE kind = 'purchase_order' AND ticket_id = ? AND ref_id = ? "
            f"AND sku = ? AND size = ? AND status IN ({','.join('?' * len(COMMITTED))})",
            (ticket_id, vendor_id, sku, size, *COMMITTED)).fetchone()
        if dup:
            return _refuse(f"Already requested: approval #{dup['id']} is {dup['status']}.", approval_id=dup["id"])

        amount = price["unit_cost"] * qty
        cash = _cash_check(conn, account, amount)
        if not cash["ok"]:
            return cash
        today = _today(conn)
        blocked_by = _open_invoices(conn, vendor_id, today)
        approval_id = _insert_approval(
            conn, ticket_id=ticket_id, kind="purchase_order", ref_id=vendor_id, sku=sku, size=size, qty=qty,
            unit_price=_money(price["unit_cost"]), amount=_money(amount), cash_out=1, account=cash["account"],
            requested_by=requested_by, reason=reason,
        )
        note = (f"Requested human approval #{approval_id}: order {qty} x {sku} size {size} from "
                f"{vendor['name']} for ${amount:,.2f}.")
        if blocked_by:
            note += f" Blocked until invoice(s) {', '.join(str(i['id']) for i in blocked_by)} are paid."
        _log_update(conn, ticket_id, requested_by, note)
        conn.commit()
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "pending",
        "kind": "purchase_order",
        "vendor": dict(vendor),
        "item": {"sku": sku, "size": size, "name": item["name"], "qty_on_hand": item["qty"], "qty_ordered": qty},
        "unit_cost": _money(price["unit_cost"]),
        **{k: v for k, v in cash.items() if k != "ok"},
        "vendor_will_ship": not blocked_by,
        "blocked_by_open_invoices": blocked_by,
        "earliest_arrival_if_ordered_today": (today + timedelta(days=vendor["lead_days"])).isoformat(),
        "message": "Waiting for human approval. Nothing has been ordered or paid.",
    }


@mcp.tool
def request_price_override(
    ticket_id: int,
    sku: str,
    size: str,
    qty: int,
    requested_by: AgentName,
    reason: str,
    discount_pct: float | None = None,
    unit_price: float | None = None,
) -> dict:
    """Ask a human to approve selling below list price (a discount or bulk price).

    Pass discount_pct (e.g. 10 for 10% off list) OR unit_price. This does NOT
    change any price. It adds a pending row to the approvals table with the
    margin worked out from pricing.unit_cost and list_price. It refuses a price
    below unit cost (a loss on every unit), a price at or above list (not a
    discount), an unknown SKU or size, and duplicates. No cash moves.
    """
    sku, size = sku.strip().upper(), size.strip().upper()
    if (discount_pct is None) == (unit_price is None):
        return _refuse("Pass exactly one of discount_pct or unit_price.")
    if qty <= 0:
        return _refuse("qty must be at least 1.")
    with _connect() as conn:
        if _ticket(conn, ticket_id) is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        item = conn.execute("SELECT name, qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if p is None or item is None:
            return _refuse(f"No pricing or inventory row for {sku} size {size}.")
        cost, list_price = p["unit_cost"], p["list_price"]
        price = _money(list_price * (1 - discount_pct / 100)) if discount_pct is not None else _money(unit_price)
        if price < cost:
            return _refuse(f"${price:.2f} is below unit cost ${cost:.2f}; every unit would lose money.",
                           unit_cost=cost, list_price=list_price)
        if price >= list_price:
            return _refuse(f"${price:.2f} is not below list price ${list_price:.2f}; no override needed.")
        dup = conn.execute(
            f"SELECT id, status FROM approvals WHERE kind = 'price_override' AND ticket_id = ? AND sku = ? "
            f"AND size = ? AND status IN ({','.join('?' * len(COMMITTED))})",
            (ticket_id, sku, size, *COMMITTED)).fetchone()
        if dup:
            return _refuse(f"Already requested: approval #{dup['id']} is {dup['status']}.", approval_id=dup["id"])

        approval_id = _insert_approval(
            conn, ticket_id=ticket_id, kind="price_override", ref_id=None, sku=sku, size=size, qty=qty,
            unit_price=price, amount=_money(price * qty), cash_out=0, account=None,
            requested_by=requested_by, reason=reason,
        )
        _log_update(conn, ticket_id, requested_by,
                    f"Requested human approval #{approval_id}: sell {qty} x {sku} size {size} at "
                    f"${price:.2f} (list ${list_price:.2f}).")
        conn.commit()
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "pending",
        "kind": "price_override",
        "sku": sku, "size": size, "name": item["name"], "qty": qty,
        "qty_on_hand": item["qty"], "shortfall": max(0, qty - item["qty"]),
        "unit_cost": _money(cost), "list_price": _money(list_price), "unit_price": price,
        "discount_pct_off_list": round((list_price - price) / list_price * 100, 1),
        "margin_per_unit": _money(price - cost),
        "margin_pct_of_price": round((price - cost) / price * 100, 1),
        "order_total_at_override": _money(price * qty),
        "discount_given": _money((list_price - price) * qty),
        "message": "Waiting for human approval. No price has changed.",
    }


@mcp.tool
def draft_customer_message(
    ticket_id: int,
    recipient: str,
    subject: str,
    body: str,
    written_by: AgentName,
) -> dict:
    """Save a message for a customer or other requester as a DRAFT on the board (drafts table).

    Nothing is ever emailed or sent; a human reviews drafts and sends them
    outside this system. Write only facts the team confirmed from the database.
    """
    if not body.strip() or not subject.strip():
        return _refuse("subject and body can't be empty.")
    if len(body) > 4000:
        return _refuse("body is over 4000 characters; keep drafts short.")
    with _connect() as conn:
        if _ticket(conn, ticket_id) is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, written_by, status, shop_date, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)",
            (ticket_id, recipient, subject, body, written_by, _today(conn).isoformat(), _now()),
        )
        _log_update(conn, ticket_id, written_by, f"Saved draft #{cur.lastrowid} to {recipient}: {subject!r}.")
        conn.commit()
    return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "sent": False,
            "message": "Saved on the board as a draft. Nothing was sent."}


@mcp.tool
def add_ticket_note(ticket_id: int, agent: AgentName, note: str) -> dict:
    """Record a finding or progress note on a ticket (ticket_updates table).

    The first note on an open ticket moves it to in_progress. Notes should
    state facts from tools and what happens next, so a human can follow along.
    """
    if not note.strip():
        return _refuse("note can't be empty.")
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id)
        if ticket is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        new_status = "in_progress" if ticket["status"] == "open" else None
        before, after = _log_update(conn, ticket_id, agent, note, new_status)
        conn.commit()
    return {"ok": True, "ticket_id": ticket_id, "status_before": before, "status_after": after}


@mcp.tool
def set_ticket_status(ticket_id: int, status: TicketStatus, agent: AgentName, note: str) -> dict:
    """Move a ticket to a new status (tickets table) and record why (ticket_updates).

    Statuses: open -> in_progress -> waiting_approval -> resolved. A ticket
    can't be marked resolved while it still has approval requests waiting on a
    person, and can't be waiting_approval when nothing is waiting. When a person
    decides the last request, the ticket resolves by itself. A resolved ticket is
    closed, and an agent can't move it again.
    """
    if not note.strip():
        return _refuse("note can't be empty; say why the status changed.")
    with _connect() as conn:
        ticket = _ticket(conn, ticket_id)
        if ticket is None:
            return _refuse(f"No ticket with id {ticket_id}.")
        if ticket["status"] == "resolved":
            return _refuse("This ticket is already resolved (a person's decision closed it). Nothing to change; "
                           "report the outcome instead.")
        waiting = _open_approvals(conn, ticket_id)
        if status == "resolved" and waiting:
            return _refuse("Can't resolve: approval requests are still open.", open_approvals=waiting)
        if status == "waiting_approval" and not waiting:
            return _refuse("Nothing is waiting for approval on this ticket. Every request has been decided, so "
                           "if the work is done, set it to resolved.",
                           decided=[dict(r) for r in conn.execute(
                               "SELECT id, kind, status FROM approvals WHERE ticket_id = ?", (ticket_id,))])
        before, after = _log_update(conn, ticket_id, agent, note, status)
        conn.commit()
    return {"ok": True, "ticket_id": ticket_id, "status_before": before, "status_after": after}


# ---------- Human-only: a person's decision on the dashboard (never given to agents) ----------

AGENT_NAMES = frozenset(get_args(AgentName))


def _open_approvals(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    """Requests on a ticket still waiting on a person (or approved cash not yet paid)."""
    rows = conn.execute(
        "SELECT id, kind, status FROM approvals WHERE ticket_id = ? "
        "AND (status = 'pending' OR (status = 'approved' AND cash_out = 1))", (ticket_id,)).fetchall()
    return [dict(r) for r in rows]


def _resolve_if_decided(conn: sqlite3.Connection, ticket_id: int, who: str) -> str:
    """After a person's decision: if the ticket was only waiting on approvals and none
    are left open, it is resolved. Returns the ticket's status."""
    status = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()[0]
    if status == "waiting_approval" and not _open_approvals(conn, ticket_id):
        _log_update(conn, ticket_id, who, "Every approval request on this ticket has been decided by a person; "
                    "ticket resolved.", "resolved")
        return "resolved"
    return status


def _add_month(d: date) -> date:
    """Same day next month, clamped to the month's last day (Jan 31 -> Feb 28)."""
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))


def _human(name: str) -> str | None:
    """The approver's name, or None if it's empty or one of the agents."""
    name = name.strip()
    return None if not name or name in AGENT_NAMES else name


@mcp.tool
def approve_request(approval_id: int, approved_by: str, note: str | None = None) -> dict:
    """HUMAN-ONLY: a person approved a pending request on the dashboard.

    For an invoice payment, rent payment or purchase order this is the step that
    actually spends cash. In one transaction it takes the amount out of
    cash_accounts, adds a payments row (approved_by = the person), updates the
    relevant table, and marks the approval paid:
      - invoice_payment: invoices.status open -> paid
      - rent_payment: leases.next_due moves forward one month
      - purchase_order: the order is placed with the vendor. Inventory changes
        only when the goods arrive, which is not modeled here.
    It refuses (and changes nothing) if cash can't cover the amount, because
    balances never go negative; if the invoice is no longer open; if a purchase
    order's vendor still has an open invoice (it won't ship); or if the approval
    isn't pending. A price override has no cash and is simply marked approved.
    If that was the last open request on a ticket waiting for approval, the
    ticket is marked resolved.
    """
    approver = _human(approved_by)
    if approver is None:
        return _refuse("approved_by must be a person's name, not empty and not an agent.")
    with _connect() as conn:
        a = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if a is None:
            return _refuse(f"No approval with id {approval_id}.")
        if a["status"] != "pending":
            return _refuse(f"Approval #{approval_id} is already {a['status']}.")
        today, now, who = _today(conn), _now(), f"{approver} (human)"

        if not a["cash_out"]:
            conn.execute(
                "UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
                (approver, now, note, approval_id))
            _log_update(conn, a["ticket_id"], who,
                        f"Approved #{approval_id}: sell {a['qty']} x {a['sku']} size {a['size']} at ${a['unit_price']:.2f}.")
            ticket_status = _resolve_if_decided(conn, a["ticket_id"], who)
            conn.commit()
            return {"ok": True, "approval_id": approval_id, "kind": a["kind"], "status": "approved",
                    "cash_moved": 0.0, "ticket_id": a["ticket_id"], "ticket_status": ticket_status,
                    "message": "Price override approved. No cash moved."}

        acct = conn.execute("SELECT name, balance FROM cash_accounts WHERE name = ?", (a["account"],)).fetchone()
        if acct is None:
            return _refuse(f"Cash account {a['account']!r} not found.")
        if a["amount"] > acct["balance"] + 1e-9:
            return _refuse("Not enough cash: paying this would make the balance negative. Nothing was paid.",
                           account=acct["name"], balance=_money(acct["balance"]), amount=_money(a["amount"]))

        if a["kind"] == "invoice_payment":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (a["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return _refuse(f"Invoice {a['ref_id']} is not open; nothing to pay.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (a["ref_id"],))
            pay_kind, pay_ref = "invoice", a["ref_id"]
            changed = f"invoice {a['ref_id']} open -> paid"
        elif a["kind"] == "rent_payment":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (a["ref_id"],)).fetchone()
            if lease is None:
                return _refuse(f"Lease {a['ref_id']} not found.")
            new_due = _add_month(date.fromisoformat(lease["next_due"]))
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due.isoformat(), a["ref_id"]))
            pay_kind, pay_ref = "rent", a["ref_id"]
            changed = f"lease {a['ref_id']} next_due {lease['next_due']} -> {new_due.isoformat()}"
        elif a["kind"] == "purchase_order":
            blocking = _open_invoices(conn, a["ref_id"], today)
            if blocking:
                ids = ", ".join(str(i["id"]) for i in blocking)
                return _refuse(f"The vendor won't ship while invoice(s) {ids} are open. Approve that payment first.",
                               blocked_by_open_invoices=blocking)
            vendor = conn.execute("SELECT name, lead_days FROM vendors WHERE id = ?", (a["ref_id"],)).fetchone()
            arrival = (today + timedelta(days=vendor["lead_days"])).isoformat()
            pay_kind, pay_ref = "purchase_order", approval_id
            changed = (f"ordered {a['qty']} x {a['sku']} size {a['size']} from {vendor['name']}, "
                       f"earliest arrival {arrival} (inventory updates when goods arrive)")
        else:
            return _refuse(f"Unknown approval kind {a['kind']!r}.")

        new_balance = acct["balance"] - a["amount"]
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today.isoformat(), acct["name"]))
        payment_id = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (pay_kind, pay_ref, a["amount"], acct["name"], today.isoformat(), approver)).lastrowid
        conn.execute(
            "UPDATE approvals SET status = 'paid', decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (approver, now, note or changed, approval_id))
        _log_update(conn, a["ticket_id"], who,
                    f"Approved and paid #{approval_id}: ${a['amount']:,.2f} from {acct['name']} "
                    f"(payment {payment_id}); {changed}.")
        ticket_status = _resolve_if_decided(conn, a["ticket_id"], who)
        conn.commit()
    return {
        "ok": True,
        "approval_id": approval_id,
        "kind": a["kind"],
        "status": "paid",
        "ticket_id": a["ticket_id"],
        "ticket_status": ticket_status,
        "payment_id": payment_id,
        "amount": _money(a["amount"]),
        "account": acct["name"],
        "balance_before": _money(acct["balance"]),
        "balance_after": _money(new_balance),
        "changed": changed,
        "approved_by": approver,
    }


@mcp.tool
def reject_request(approval_id: int, decided_by: str, note: str) -> dict:
    """HUMAN-ONLY: a person rejected a pending request on the dashboard.

    Marks it rejected, which frees the cash it was holding, and records why on
    the ticket. If that was the last open request on a ticket waiting for
    approval, the ticket is marked resolved (the person has made the final call).
    """
    person = _human(decided_by)
    if person is None:
        return _refuse("decided_by must be a person's name, not empty and not an agent.")
    with _connect() as conn:
        a = conn.execute("SELECT id, ticket_id, kind, amount, status FROM approvals WHERE id = ?",
                         (approval_id,)).fetchone()
        if a is None:
            return _refuse(f"No approval with id {approval_id}.")
        if a["status"] != "pending":
            return _refuse(f"Approval #{approval_id} is already {a['status']}.")
        conn.execute(
            "UPDATE approvals SET status = 'rejected', decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (person, _now(), note, approval_id))
        _log_update(conn, a["ticket_id"], f"{person} (human)",
                    f"Rejected #{approval_id} ({a['kind']}, ${a['amount']:,.2f}): {note}")
        ticket_status = _resolve_if_decided(conn, a["ticket_id"], f"{person} (human)")
        conn.commit()
    return {"ok": True, "approval_id": approval_id, "kind": a["kind"], "status": "rejected", "decided_by": person,
            "ticket_id": a["ticket_id"], "ticket_status": ticket_status}


if __name__ == "__main__":
    mcp.run(show_banner=False)
