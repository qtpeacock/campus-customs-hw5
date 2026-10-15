# AI Prompts — HW5

This file logs what I typed to my vibe coder for each HW5 problem.

Each section includes the problem number and title, at least one prompt I typed in my own words, a follow-up prompt if one was needed, and a sentence on what the first prompt was missing.

## Problem 1 — Vibe Coder Prompts

### Prompts

- "Okay now we will start problem 1. this will be the same set up as problem one in all the other homeoworks. Create AI_prompts.md at the start of the assignment and keep it updated as I work. this file will log what i typed to you my vibe coder. put one section for each problem (11 problems for this HW) including the problem number and title, at least one prompt i typed in my own words, one follow-up prompt if it was needed (and a sentence on what was lacking after the first)"

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt gave the number of problems, the parts every section needs, and how Problem 1 should be set up, so no follow-up was needed.

### Evidence

- Created `HW5/AI_prompts.md` with 11 problem sections. Each section has the problem number and title, prompts, follow-up prompt, what the first prompt was missing, and evidence.
- Filled in Problem 1. Problems 2–11 hold placeholders until each problem is given.

## Problem 2 — Study the Campus Customs Database

### Prompts

- "problem 2: Study the Campus Customs Database : open data/campus_customs.db and look through every table and its fields. copy the original file to data/campus_customs_new.db - later problems with update that working copy. study the three open tickets so you see how they link to other tables. start output/harness.md , for each table, list the fields and one short line on why that table matters for the agents. you will keep growing this harness file in later problems."

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt named the database, the working copy to make, the tickets to trace, the output file, and the fields-plus-one-line format, so no follow-up was needed.

### Evidence

- Opened `data/campus_customs.db` read-only and went through all 9 tables (desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, invoices), including every field and row. The integrity check passed.
- Copied the original to `data/campus_customs_new.db`. Both files have the same SHA-256 hash (`23686a90…f360a`), and the original is untouched.
- Traced the three open tickets. **101** (tee size S) has 0 in stock and links to invoice 501, $840 owed to Bulldog Print Co and 3 days overdue, which blocks new shipments. **102** links to lease 1: $2,400 rent due 2026-09-02. **103** (20 hoodies size M, bulk discount) has only 8 in stock, so 12 short, and needs the same blocked vendor. Cash is $3,400, and invoice plus rent leaves only $160.
- Started `output/harness.md` with the original vs. working copy, every table's fields, a "why it matters" line per table, how the tables link, and the three tickets.

## Problem 3 — Build the MCP Server

### Prompts

- "problem 3: build the MCP server. write and MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db . you do not need to connect or run it in this problem. every agent in this homework uses the tools in this mcp server. we will add more tools to it later, for now write three tools we will need for the tickets in the database. keep the names clear. never invent any data, only use information in the database. In, output/harness.md , list each of your three MCP tools. for every tool include: which table it reads, which ticket it helps unlock (101, 102, 1013) and one sentence on why that tool is the right one for that ticket. vague lines like \"reads inventory\" score low - tie the tool to the ticket. also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has. that is the end of problem 3."

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt named the folder, the framework, the database file, the number of tools, the no-invented-data rule, and exactly what the harness and README must say, so no follow-up was needed.

### Evidence

- Wrote `mcp_server/server.py`, a FastMCP server named `campus-customs` that opens only `data/campus_customs_new.db`. If the file is missing it fails instead of creating an empty database. It has three read-only tools:
  - `check_stock(sku, size, qty_needed?)` reads `inventory`.
  - `get_invoice(invoice_id)` reads `invoices` + `vendors`.
  - `get_lease(lease_id)` reads `leases`.
- Each tool returns only database values and simple arithmetic on them, measured against `desk.date_today`. Unknown ids come back as `found: false` and nothing is guessed.
- Tested all three tools through an in-memory FastMCP client, with no server process started:
  - `check_stock("CC-TEE-WHITE", "S", 1)` returned 0 on hand, shortfall 1 (ticket 101).
  - `get_invoice(501)` returned $840, 3 days overdue, Bulldog Print Co, `vendor_will_ship: false` (ticket 101).
  - `get_lease(1)` returned $2,400 due 2026-09-02, 2 days out (ticket 102).
  - `check_stock("cc-hood-navy", "m", 20)` returned 8 on hand, shortfall 12 (ticket 103).
  - A bad SKU, a bad size, a missing invoice and a missing lease each returned a clear `found: false`.
  - The database hash was the same before and after.
- Added `mcp_server/README.md` covering what the server is for, the database file it uses, the three tools, and how to run it.
- Added section 4 "MCP tools" to `output/harness.md`. For each tool it gives the table(s) read, the ticket(s) it unlocks, and a sentence for each ticket tying the tool's actual result to that ticket.

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Prompts

- "problem 4: add the MCP server to vibe coder and test each tool : add the MCP server to this project so that the vibe coder (you) can call the tools. save the connection JSON text in .mcp.json at the project root (or however your vibe coder saves local MCP server lists). once you are connected, test each of your three MCP tools. Save the evidence in output/mcp_smoke.json. for every tool include: the prompt asked to the vibe coder (you), the tool name, the tool output (must match values in data/campus_customs_new.db). end of problem 4."

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt said where to save the connection, what to test, the evidence file, and the three things each test must include, so no follow-up was needed.

### Evidence

- Saved the connection in `HW5/.mcp.json`. It registers the server `campus-customs` (stdio, `.venv/Scripts/python.exe mcp_server/server.py`).
- Set up the server's environment: `HW5/.venv` with `fastmcp` 4.1.0, which is pinned in `requirements.txt`. `HW5/.claude/settings.local.json` approves the server for this project.
- Moved the Claude Code session into `HW5/`. The connector status then showed `campus-customs` as **connected with 3 tools**.
- Called each tool through MCP, one call per ticket question:
  - `check_stock` for 101: 0 tees in size S, shortfall 1.
  - `get_invoice(501)` for 101: $840 owed to Bulldog Print Co, 3 days overdue, `vendor_will_ship: false`.
  - `get_lease(1)` for 102: $2,400 due 2026-09-02, 2 days away.
  - `check_stock` for 103: 8 hoodies in size M, shortfall 12.
- Saved `output/mcp_smoke.json`. Each test lists the prompt, the tool name, its arguments, the exact MCP output, and a `database_check` that re-reads the same rows from `data/campus_customs_new.db` with plain SQL.
- All 26 field checks match the database, and the working copy is still unchanged (same SHA-256 as the original).
- Added a "Connect to Claude Code" section and venv setup to `mcp_server/README.md`.
- **Recheck after the full run (2026-10-15):** Problem 9 changed the working database (invoice 501 paid, rent paid through 2026-10-02), so I ran the same four MCP calls again and added them to `output/mcp_smoke.json` as `recheck_after_full_run`. All 26 field checks match the database as it is now, and the original Problem 4 results are kept above it.

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompts

- "problem 5: build the agent team and grow the MCP tools - build the agentic team from campus customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backent/prompts/ - one file per agent. put data types in backend/models.py and the agent files under backend/ (the layout can vary as long as the five roles are clear). use the portkey_api_key and ONLY gpt-6-luna for every agent. write each prompt with the shop rules that agent needs. more detailed prompts that cover all aspects of an agents work and scopre score higher than a short generic prompt. add any tools the agents need to the MCP server so they can work on the open tickets. shop facts come from the MCP server over data/campus_customs_new.db - do not invent a second shop-tools layer that bypasses MCP. wire the agents so they append to output/audit_trial.json as they run: for each agent-loop step, record enough to audit later. append to this file - do not wipe it each run. in output/harness.md, list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. update mcp_server/README.md so the tool list matches what you have now"

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt named the five agents, where the prompts, data types and agent files go, the one allowed model, the MCP-only rule for shop facts, the append-only audit trail, and what the harness and README must add, so no follow-up was needed.

### Evidence

- **Agent team (PydanticAI 2.56):** Boss, Inventory, Accounting, Facilities and Customer Service live in `backend/agents.py`, with one prompt file each in `backend/prompts/`. Each prompt covers the agent's job, its teammates, its tools, the shop rules it needs, what it must never do, and its answer format.
- **Data types:** `backend/models.py` holds `TeamReport`, `BossDecision`, `Fact`, `TeamDeps`, `AuditEntry` and the rest.
- **Entry points:** `backend/team.py` runs `ticket N`, `board` or `ask <agent> "…"`.
- **Full connectivity:** every agent has `ask_teammate`. Guards stop self-delegation and cycles, cap depth at 2 and allow 8 hand-offs per task.
- **Agent loop:** `run_agent()` steps through each run with `agent.iter()`.
- **Model:** only `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). It's a constant in code, never read from `.env`. It runs on the Responses API because chat completions rejected tools for this model.
- **MCP tools grew from 3 to 17:** `get_shop_date`, `list_tickets`, `get_ticket`, `get_pricing`, `list_vendors`, `list_unpaid_invoices`, `get_cash_position`, `list_approvals`, `request_payment`, `request_purchase_order`, `request_price_override`, `draft_customer_message`, `add_ticket_note` and `set_ticket_status`, on top of the original three.
- **How the request tools work:** they only file *pending* human approvals, using amounts from the database, and they refuse anything cash can't cover. Drafts are never sent. Each agent sees only its role's tools, and shop facts come only through MCP.
- **Tool tests:** ran all 17 tools on a scratch copy of the database. Requests were filed correctly. These were refused as expected:
  - a duplicate payment request;
  - a $264 hoodie restock when only $160 was left;
  - a below-cost price and an above-list price;
  - resolving a ticket with open approvals.
  The working copy was untouched.
- **Team tests on scratch copies:**
  - Inventory alone on ticket 101: 4 requests.
  - Facilities → Accounting on ticket 102 (rent approval #1): 10 requests.
  - Boss on ticket 101, end to end: asked Inventory, Accounting and Customer Service, filed approvals for the $840 invoice and the $8 tee restock (blocked until the invoice is paid), saved an honest customer draft, set `waiting_approval`, and moved no money. That took 18 requests, about 70k input and 3.3k output tokens.
- **Problems found during testing and fixed:** answering in free text ran into the token cap, so agents now must finish with the output tool, and reasoning effort is set to low.
- **Audit trail:** `output/audit_trail.json` grew to 210 entries across those runs and kept every earlier entry, including two early failed runs. The only model it records is gpt-6-luna.
- **harness.md:** added section 5 (agent team), section 6 (all 17 MCP tools with the tables each uses) and section 7 (safety guardrails and token limits).
- **Other updates:** rewrote the tool list in `mcp_server/README.md` and pinned the packages in `requirements.txt`.

## Problem 6 — Plan the Three Tickets

### Prompts

- "problem 6: plan the three tickets : before you wire the backend, write down what you expect the team to do on each open ticket. build output/desk_tickets.html - a page you can double-click with one tab per ticket (101, 102, 103). also add empty Cash and Reflection tabs for later problems (leave them blank or with a short \"coming later\" note for now). on each ticket tab, fill an Expected section only (leave room for an Actual section you will fill in after you run the agents). for each ticket's expected section, write in your own words: who the Boss should call first and why, All the agent delegations you expect - not \"Boss calls everyone\", which MCP tools you expect that run to use. plans that send every specialist on every ticket score low. you will compare this plan to what actually happens when you agents resolve the three tickets."

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt named the file, the five tabs, what goes in each Expected section (first call and why, every delegation, the MCP tools), that Actual stays empty for now, and the warning against sending every specialist on every ticket, so no follow-up was needed.

### Evidence

- Built `output/desk_tickets.html`, a single self-contained file (no internet or server needed, opens with a double-click) in black, blue and white. It has five accessible tabs (101, 102, 103, Cash, Reflection) that switch by click or arrow keys and can be linked with `#101`, `#cash` and so on.
- Each ticket tab has a ticket card with the facts from the database, an **Expected** section, and an empty **Actual** box to fill after the run. Each Expected section covers:
  - who Boss calls first and why;
  - every delegation we expect, in order, with the result we expect;
  - a table of the MCP tools each agent should use;
  - who is **not** called and why;
  - the expected end state.
- **101:** Boss → Inventory first (stock and the invoice block), then Accounting (approvals for the $840 invoice and the $8 tee PO), then Customer Service (draft to Tauhid). Facilities is not called.
- **102:** Boss → Facilities first (check the notice against lease 1), then Facilities → Accounting directly (approval for $2,400 rent). Inventory and Customer Service are not called.
- **103:** Boss → Inventory first (8 on hand vs 20), then Accounting (margin check, $264 restock refused because only $152 is left, price override pending), then Customer Service (draft to the Yale AI Club). Facilities is not called.
- Cash and Reflection tabs show a short "Coming later" note.
- Checked it in the browser preview: all five tabs switch by click and keyboard, there are no console errors, and the mobile layout was fixed so the ticket cards stack on narrow screens.

## Problem 7 — Backend Routes

### Prompts

- "problem 7: backend routes : your react frontend dashboard (the enxt problem) needs a backend it can call. in backend/main.py, use FastAPI and add routes that do the following: return the three tickets and whether each is open or resolves, take a ticked id and run your agent team on that ticket, return recent agent events - what each agent said and which tools they used - so the board can refresh, approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash), return the current checking balance from cash_accounts, reset the database to the original values when you want to try a fresh run. from the backend/ folder, start the server with: uvicorn main:app --reload --port 8000  . this should turn on the backend at http://localhost:8000 so the frontend dashboard can call those routes. in output/harness.md, list each route in one line (what URL/ what it does)"

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt listed every route the dashboard needs, which route is the only one that changes cash, the exact start command and port, and the one-line-per-route harness format, so no follow-up was needed.

### Evidence

- **Routes:** wrote `backend/main.py` (FastAPI) with these routes:
  - `GET /api/tickets`: each ticket, open or resolved, with its approvals, drafts and updates.
  - `POST /api/tickets/{id}/run`: starts the team in the background, one run at a time.
  - `GET /api/runs` and `/api/runs/{id}`: run status and Boss's decision.
  - `GET /api/events`: what each agent said and which tools it used, from the audit trail, with incremental `since`.
  - `POST /api/approvals/{id}/approve`: the only route that changes cash.
  - `POST /api/approvals/{id}/reject`.
  - `GET /api/cash`: the checking balance.
  - `POST /api/reset`: copies the original DB over the working copy.
  - `GET /api/health`.
- **All shop data goes through MCP:** the backend calls the same MCP server the agents use. Two **human-only** MCP tools were added, `approve_request` (spends cash and updates `cash_accounts`, `payments`, and `invoices` or `leases`) and `reject_request`. `agents.py` asserts that no agent can see them.
- **Windows fix:** uvicorn's `--reload` mode on Windows serves requests on an event loop that can't start subprocesses, so the agents and their stdio MCP server run on their own background loop (`TeamLoop`).
- **Tested every route on a scratch copy of the database**, with the server running in a real terminal:
  - Ran ticket 101 through the API in about 130 seconds and got 80 events across Boss, Inventory, Accounting and Customer Service.
  - A second run and a reset during the run both got 409, and an unknown ticket got 404.
  - Approving the purchase order before the invoice was refused (the vendor won't ship), as were an agent name as approver and an 840 payment against a 500 balance.
  - Approving the invoice took cash from 3,400 to 2,560 and marked invoice 501 paid. Then the PO took it to 2,552, and the rent to 152 with the lease moving to 2026-10-02. Each created a `payments` row approved by "Quinn".
  - Approving a price override moved no cash. A reject freed $22 that was being held, and approving an already-decided request was refused.
  - The `--reload` restart shut down and restarted cleanly.
  - Reset returned the scratch DB byte-for-byte to the original and kept all 308 audit entries.
- **Real backend:** started it with the exact command (`uvicorn main:app --reload --port 8000` from `backend/`, venv active). `/api/health`, `/api/tickets`, `/api/cash`, `/docs`, and the CORS check for `localhost:5173` all answered on http://localhost:8000 against `data/campus_customs_new.db`.
- **Cleanup:** the test server's whole process tree, including the MCP child, was stopped, with nothing left over.
- **Docs:** added section 8 "Backend routes" (one line per route) to `output/harness.md`, plus the two human-only tools to section 6 and the README. Added fastapi and uvicorn to `requirements.txt`.

## Problem 8 — Agent Dashboard

### Prompts

- "problem 8: agent dashboard : build the frontend dashboard in frontend/ with React + Vite + TypeScript. the page should call the routes we build in problem 7. at minimum the board should: list all three tickets, let you pick one ticket and start the agent team on it, show each agents and what they are saying/doing while the ticket runs, mark a ticket resolved when the run finishes, show a short summary of what each agent did on that ticket, let a human approve a pay or purchase when asked, show the checking balance (it should drop after an approved pay). show me what the dashboard looks like so i can adjust the layout and feel."

### Follow-up prompt

- "also, tell the front end to talk to your backend at http://localhost:8000  on the backend, allow the Vite page origin (usually, http://localhost:5173) so the browser is allowed to call those routes. start the board with terminal command: npm run dev . this should open the react desk in the browser so i can pick tickets and watch agents. write output/design.md with what i chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why - including the creative choice that make it feel special and something humans would actually enjoy using. i havent added the creative choices yet, i want to see the dashboard first before i come back with suggestions"
- "okay so im thinking it needs more visuals, show me my balance using some type of bar that grows or shrinks with the balance. also, id like to see the agents on team, can you make them little handsome dans and at the top of the screen show them when they are being utilized and active. also make this whole thing a little brighter and more fun, kind of like a modern board game, have the tickets and different things like that show up Slightly 3D. also, when a ticket is resolved, do a quick confetti across the screen and have the handsome dan agent who completed it do a little wiggle dance
also, can you add a few additional things to each of those sections to tie in my ideas with general improvements like usability and readability, also on the visuals perspective, if you have any ideas that work with mine try those out"

### What the first prompt was missing

The first prompt didn't say which backend address the frontend should call, that the backend must allow the Vite origin, how to start the board, or that the design choices had to be written up in output/design.md.

### Evidence

- **The app:** built `frontend/` with React 19 + Vite 8 + TypeScript 6 (`src/App.tsx`, `api.ts`, `types.ts`, `agents.ts`, and the components `Header`, `TicketList`, `TicketHeader`, `Approvals`, `AgentFeed`, `AgentSummary`, `SidePanels`).
- **Backend address:** it calls the backend directly at `http://localhost:8000` (`API_BASE` in `src/api.ts`). The backend's CORS allows `http://localhost:5173`, and the Vite port is fixed with `strictPort` to match.
- **Starting it:** `npm run dev` starts Vite on 5173 and opens the desk in the browser.
- **What the board does:**
  - lists all three tickets with status pills;
  - picks a ticket and starts the team (`POST /api/tickets/{id}/run`);
  - streams each agent's steps live (polls `/api/events` every 1.5 s, new events only), indented by who asked whom;
  - shows "What each agent did" cards (answer, who asked them, tools used, who wasn't called) and Boss's call;
  - lets a person Approve & pay or Reject (name required, reject needs a reason);
  - shows the checking balance with a "−$X · what" chip after each payment;
  - shows draft messages and board notes, and resets the board.
- **Backend additions for the board:**
  - When a person decides a ticket's last open request, the ticket now resolves by itself, which is how "mark resolved when the run finishes" works when Boss's plan needs approval.
  - `/api/events` now returns each agent's final answer, the teammate asked, and tool arguments.
  - `/api/health` reports the last reset time, so older runs are labelled.
- **Live test on the working copy:** ran ticket 102 from the dashboard.
  - The feed showed Boss → Facilities → Accounting, which is exactly the Problem 6 plan, and the $2,400 rent request appeared mid-run.
  - Approve & pay (as "Dashboard test") dropped the balance from $3,400 to $1,000, showed "−$2,400.00 · Pay rent #1", marked the approval PAID, and flipped ticket 102 to ✓ Resolved.
- **Runaway answers:** during the test, Facilities' final answer looped to the 6,000-token cap. Across all runs, 4 of 70 model responses had done this. I lowered the per-response cap to 3,000 and capped report list lengths (noted in harness section 7).
- **Checks:**
  - `npm run build` (type check + build) passes.
  - After a clean reload the page renders with no error overlay.
  - The layout was checked at 1440 px and on a phone, and the phone header overlap was fixed.
- **Design notes:** wrote `output/design.md` covering the layout, how the five agents read differently (each badge has its own shape, not just a colour), how resolved tickets and cash show up, and why. The "Creative choices" section is left for Quinn's suggestions after seeing the dashboard.
- **Creative choices (second follow-up), built:**
  - **Balance bar:** a 3D bar that shrinks with the balance (free / held / spent). Hovering Approve & pay previews "after this payment: $X".
  - **Handsome Dan team strip:** five SVG Handsome Dans, each with its own gear (crown, beanie, visor and glasses, hard hat, headset). A Dan bounces with a "what I'm doing" bubble when active, sways and says "Waiting on X" when waiting, smiles with a step count when done, and greys out and snoozes when not needed. Clicking a Dan filters the feed to that agent.
  - **Board-game look:** outlined 3D tiles, press-down buttons, game-card tickets with type icons, hover tilt, and an Open → Agents → Your call → Done track. The look is brighter while staying in black, blue and white.
  - **Celebration:** on resolve, confetti plus a wiggle dance by the Dan who closed the ticket, and a banner naming them. All of it is off when the system asks for reduced motion.
  - **Readability extras:** plain-English tool names in the feed and view chips (Everything / Conversation / Board actions).
- **Creative choices, tested live:**
  - Reset the board, then ran ticket 101. The strip showed Boss "Waiting on Inventory", then Inventory, Accounting and Customer Service taking turns.
  - Approvals for $840 and $8 appeared, and the bar showed $2,552 free and $848 held. The hover preview read "after this payment: $2,560.00".
  - Approving both dropped cash to $2,552 and resolved ticket 101 automatically. The banner read "Ticket #101 resolved! Accounting closed it out. 🎉" with Accounting's Dan dancing.
  - `npm run build` passes. All five creative choices are written up in design.md, each with why and the extras.

## Problem 9 — Resolve the Tickets

### Prompts

- "problem 9: resolve the tickets ; before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so you start clean. note the starting checking balance. then run all three tickets on the board (101, 102, 103) until each is resolved. open output/desk_tickets.html from problem 6. on each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools they used. keep you expected section so you can compare the two. on the cash tab of the same output/desk_tickets.html, itemize the money: starting checking balance (after the reset), for each ticket: how cash changed when the ticket resolved, and why (which pay/purchase, dollar amount), ending checking balance - it must match cash_accounts in the working database. wrong cash math loses points even if the board shows every ticket resolved. also save: output/resolved_tickets.json - for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals, output/resolved_board.html - a page you can double-click with a screenshot of your react board for each resolved ticket (101, 102, 103). append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard and safety rules."

### Follow-up prompt

- "i approved all the requests on the dashboard"
- "i tried the approvals again, check now"

### What the first prompt was missing

The first prompt didn't say who would click the human approvals, so the run paused until Quinn approved the payments on the dashboard. The follow-ups were Quinn reporting those approvals: the first attempt never reached the backend, and the second one did.

### Evidence

- **Reset and starting balance:** reset the working database with `POST /api/reset` (01:21:37 UTC). The starting checking balance was **$3,400.00** (`/api/cash` and `cash_accounts`), with invoice 501 open, rent due 2026-09-02, and no payments.
- **Full run:** ran the team on 101 → 102 → 103 through the backend (the same route as the dashboard's Run button).
  - 101 filed approval #1 ($840, invoice 501) and #2 ($8 tee order) plus draft #1.
  - 102 filed #3 ($2,400 rent) plus draft #2, via Boss → Facilities → Accounting.
  - 103 stalled at first: no discount was named, so nothing was filed.
- **Fixes for ticket 103:**
  - Added a prompt rule (Accounting proposes a discount for human approval) and re-ran. That filed #4, a 10% override at $52.20 a hoodie.
  - A dashboard "Run team again" overlapped Quinn's approval of #4 and reopened the ticket. I added MCP guards (a resolved ticket can't be moved, and `waiting_approval` needs something waiting) and disabled the Run button while approvals are pending.
  - A Boss rule (don't hold a ticket open for a customer's reply) let run 5 resolve it.
  - In run 4, the restock order ($264 against $152) was **refused by the cash rule**.
- **Human approvals:** Quinn approved all four requests on the dashboard (01:34–01:35 UTC). Tickets 101 and 102 resolved themselves when their last request was decided, and Boss resolved 103. **Final: all three tickets resolved.**
- **Cash:** $3,400.00 − $2,400.00 (rent) − $840.00 (invoice 501) − $8.00 (tee order) = **$152.00**. This matches `cash_accounts.balance` = 152.0 and `SUM(payments.amount)` = 3,248.0. The invoice is paid, the lease is due 2026-10-02, and nothing went negative.
- **`output/desk_tickets.html`:** filled the Actual section on each ticket tab (who Boss called first, every delegation, the MCP tools each agent used with counts, who wasn't called, and how it ended), with "same as plan" or "differs" badges next to the untouched Expected sections. Filled the **Cash tab**: starting balance, each ticket's cash change and why, the payments in order with a running balance, and the database check.
- **`output/resolved_tickets.json`:** for each ticket, the id, final status (resolved), short outcome, each agent's contribution and tools, delegations, human approvals (who and when), drafts, cash change, and runs. It also has the cash ledger with `matches_database: true`.
- **`output/resolved_board.html`:** a self-contained, double-clickable page with a full-page headless-Chrome screenshot of the React board for each resolved ticket (101, 102, 103) and the cash summary.
- **`output/audit_trail.json`:** the real runs were appended, growing from 601 to 1,078 entries, with nothing wiped. 7 team runs, 97 model requests, 411,842 input and 15,972 output tokens, and every response from gpt-6-luna.
- **`output/harness.md` finished:**
  - an overview diagram and contents, plus "How to run";
  - tables, links and tickets, MCP tools (first three and all 19), and the five agents;
  - safety: a shop-rules-to-enforcement table, guardrails and token limits;
  - API routes, the dashboard (section 9), and full run results (section 10).
- **Small dashboard improvements:** link to a ticket by URL (`#ticket-103`), and cut-off tool arguments now read as key-value pairs.

## Problem 10 — Reflection

### Prompts

- "problem 10: reflection. open output/desk_tickets.html and fill the reflection tab. answer in my vibe and be detailed and thorough. i will give you a little hand written blurb to base my 'vibe' off of after the directions, so dont do anythign until i share that. directions: in the reflections tab, answer these questions: how would you eveluate the performance of the agents on each ticket and why? for each ticket, how did actual compare to the expected plan you wrote earlier? what would have been simpler as one agent with tools and why? describe three new problems campus customs might face that this agent team could solve with the tools you built. descrive three new problems campus customs might face that this agent team could not solve with the tools you build and explain the tools and agents you would need to solve them. Tie every answer to This app and the three tickets we ran - use the tickets tabs and cash tab on the same page as your evidence. generic ai essays without campus customs details will score low. before doing all this - give me a few prompts for a short blurb i can type so you can get my vibe"

### Follow-up prompt

- "this sounds like a lot, also see if you can reference things in here ive hand written. to answer your questions: 1. it was weird to watch the dans work, but it was also cool that everything could basically work on its own. I feel like there were a lot of ways to continue to improve this to make it feel like a properly functioning, professional website. 3. I would tell my friend that the app is basically a platform to track major items for a business and different to dos, and that it includes a team of agents that can help me track more at once and get more done more effectively and more efficiently."

### What the first prompt was missing

The first prompt held back the blurb on purpose, so the follow-up was needed to give my voice (casual, first person) and the lines I wanted the reflection to reference.

### Evidence

- Before writing anything, gave Quinn short blurb prompts, then waited for the blurb as asked.
- Filled the **Reflection** tab of `output/desk_tickets.html` in Quinn's voice (first person, casual, no emojis). It quotes their own lines: "it was weird to watch the dans work…", "basically a platform to track major items for a business and different to dos…", and "a lot of ways to continue to improve this…".
- **1. Evaluation:** a grade per ticket with the evidence for it.
  - 101 A−: right plan and money, but it re-checked a lot (`get_ticket` 5×, `get_invoice` 3×), and it may have ordered a duplicate $8 tee.
  - 102 A: exactly the plan.
  - 103 C+: 60% of the requests and 64% of the tokens over 5 runs. It went 20 hoodies instead of 8 and used the wrong vendor id, but the cash refusal worked.
- **2. Actual vs. plan:** a table per ticket comparing first call, hand-offs and ending. Boss's first call matched the plan 3 for 3, and the idle agents were never called, but the run counts were off.
- **3. One agent vs. the team:** honest take. 102 would be about 6 tool calls instead of 20, 101 had repeated lookups, and 103 suffered from stale hand-offs. The team is worth it for permissions and auditing.
- **4. Could solve with the existing tools:** 10 Crest Mugs from Elm City Gifts ($35, fits the $152), the Yale AI Club accepting 8 hoodies at the approved $52.20, and a 30-cap bulk discount.
- **5. Could not solve, and what to add:**
  - October rent of $2,400 with $152 and no revenue: `record_sale`, `forecast_cash`, and a Sales agent.
  - A tee order that never "arrives": `purchase_orders`, `receive_shipment`, `advance_shop_date`, `create_ticket`, and a Receiving agent.
  - Drafts never sent and bills never received: approval-gated `send_email`, an inbound inbox, PDF invoice intake (like HW1), and a Comms agent.
- **Ties to evidence:** every answer cites numbers from the 101/102/103 tabs and the Cash tab, and the in-page links (#101, #cash, …) now switch tabs when clicked.

## Problem 11 — Submit to GitHub

### Prompts

- "okay, problem 11: submit to github : push the code to a public github repository so graders can cline it. give me the repo URL so i can submit it to canvas and also put it in output/github_url.txt. do not push the real .env to github repo. do include both database filies under data/ (original and working copy) so graders can run the app easily. Expected file layout is in the two attached photos. README should explain: copy original DB to the working copy when you need a clean run, start mcp server, start fastapi backend, start the react board, reset the db before a full three ticket run." (with two screenshots of the expected `hw5/` file tree)

### Follow-up prompt

- None needed.

### What the first prompt was missing

Nothing. The prompt and the file-tree screenshots gave the repo visibility, where the URL goes, what must stay out (the real `.env`), what must go in (both databases), the exact layout, and every step the README has to explain, so no follow-up was needed.

### Evidence

- To be added.
