# Ops Desk design (frontend/)

The Ops Desk is the React + Vite + TypeScript dashboard where a person watches the Campus Customs agents work a ticket and approves anything that spends money. It runs at http://localhost:5173 (`npm run dev` in `frontend/`) and calls the FastAPI backend at http://localhost:8000.

**Look: a bright, modern board game in Yale black, blue and white.** Everything on screen is a chunky "game piece":
- white tiles with thick black outlines and a hard shadow underneath, so they look slightly 3D and seem to sit on top of the board;
- a soft blue background with a dotted grid, like a game board;
- buttons that press down when you click them.

The palette stays in the black, blue and white family, but uses brighter blues (cobalt, sky, ice). Every text and background pair is at accessible contrast. Black means "decided" or "in charge", blue means "needs attention or can be clicked", and white is calm space.

## Layout

```
┌──────────────── bright blue top bar ──────────────────────────────────────────────┐
│ [CC] Campus Customs Ops Desk   shop date · backend ●   ┌ CHECKING $3,400.00 ──────┐ [↺ Reset] │
│                                                        │ ███████████▒▒▒░░░░  bar  │           │
│                                                        └──────────────────────────┘           │
├──────────────── the team: five Handsome Dans (stays on screen when you scroll) ─────┤
│  The team    [👑 Boss]   [Inventory]   [Accounting]   [Facilities]   [Customer Service] │
├──────────┬─────────────────────────────────────────────────────────────────────────┤
│ TICKETS  │  🏠 ticket header + progress track             [status] [▶ Run agent team]  │
│ (game    │  🙋 Your call: approvals (only when something is waiting)                    │
│  cards)  │  ┌── Live feed / agent activity ──┐  ┌── Boss's call ────────────┐          │
│  #101    │  │ filter chips                    │  │ What each agent did (Dans) │          │
│  #102    │  │ who did what, indented by who   │  │ Draft messages             │          │
│  #103    │  │ asked whom                      │  │ On the board (notes)       │          │
└──────────┴──┴────────────────────────────────┴──┴────────────────────────────┴──────────┘
```

- **Left rail: the three tickets.** They're game cards and always visible, so you see the whole board at a glance and switch with one click.
- **Main area: one ticket at a time.** It reads top to bottom in the order a person cares about: what the ticket is → what needs *me* → what the agents did → what they decided.
- **Approvals sit above the agent feed** and only appear when something is waiting, with a blue 3D glow. Anything waiting on a human is the most important thing on the screen, so it should never be below the fold.
- **Feed on the left, conclusions on the right.** The feed is the step-by-step story. The right column is the short version for someone who doesn't want to read every step.

## How the agents read differently

**On the team strip and the summary cards, every agent is a little Handsome Dan,** the Yale bulldog, drawn in SVG. Each Dan wears its own gear and collar colour, so you can tell them apart at a glance, even in black and white:

| Agent | Handsome Dan wears | Why |
|---|---|---|
| Boss | a **crown** and a black collar | The lead. Black is the "final call" colour across the desk. |
| Inventory | a **warehouse beanie** with a pompom | Out on the stockroom floor. |
| Accounting | a navy **accountant's visor and round glasses** | Counting the money. |
| Facilities | a **hard hat** | Looks after the shop space. |
| Customer Service | a **headset** with a mic | Talks to customers. It only writes drafts, and nothing it writes is sent. |

**In the live feed,** each agent has a small badge with its own shape: black square = Boss, blue circle = Inventory, navy coin = Accounting, blue house = Facilities, speech bubble = Customer Service. That keeps rows compact and readable, and the shapes still work for colour-blind users.

The feed also uses these conventions:
- **Indentation shows delegation.** A teammate's steps sit indented under the agent that asked them, with a sky-blue rail, so "Boss → Facilities → Accounting" reads as a nested conversation.
- **Asks** ("Boss asks Facilities…") get a light-blue quote bubble with the full task.
- **Lookups use plain English,** e.g. "Read the lease", "Checked the shelves", with the details in small grey text beside them.
- **Board actions are solid blue pills with a ★** (e.g. "★ Asked you to approve a payment"), so the steps that change something stand out from the ones that only read.
- **Reports** ("Facilities reported back…") are white bubbles with an outlined 3D edge: that agent's answer.
- **Guardrails** (a refused hand-off, a retry) are dashed bubbles, so you can see the safety rules working.

## How resolved tickets show up

- **Every ticket has a little board-game track: Open → Agents → Your call → Done.** The current space is a raised sky-blue token, and spaces already passed are filled in blue. It appears on each ticket card and in the ticket header.
- Status pills follow one rule: outlined = not decided, blue = waiting on you, black = done.
  - **Agents working…** pulses while the run is live. The Run button shows a spinner, and other tickets can't start, since only one run happens at a time.
  - **Needs your approval** is a sky-blue pill with the number of waiting requests.
  - **Resolved** is a black pill with a ✓. The card's top band turns black, and the Run button reads "✓ Resolved" and is disabled.
- **When does a ticket resolve?** When a run finishes, Boss sets the status. If Boss's plan needs money approved, the ticket waits on you. As soon as a person decides the last open request, the backend marks the ticket resolved by itself.
- **Celebration:** confetti, a wiggle dance and a banner (see Creative choices).

## How cash shows up

- **The scorecard:** the checking balance is the biggest number on the screen, in a white 3D tile in the top bar.
- **The balance bar:** under the balance, a bar that **shrinks as money goes out**. Solid blue = **free** to spend, striped = **held** for approvals waiting on you, empty hatching = already **spent**. The full bar is the opening balance at the last reset, with a legend underneath.
- **After a payment:** "Approve & pay" is the only button that moves money. After it, the bar animates down and a chip pops in, e.g. "−$2,400.00 · Pay rent #1".
- **Preview before you pay:** hovering (or tabbing to) **Approve & pay** drops a black marker on the bar labelled "after: $X", so you see the effect *before* you click.
- Price overrides are tagged "no cash moves". If the backend refuses (not enough cash, or the vendor still has an unpaid invoice), a message explains why and nothing changes.

## Creative choices

Quinn's ideas, plus the extras that go with each.

### 1. A balance bar that grows and shrinks (Quinn)
- **What:** the 3D "tube" bar in the scorecard, split into free / held / spent, that animates whenever the balance changes.
- **Why:** a number tells you *what* the balance is, and a bar tells you *how much is left* without reading. Since cash only goes out, the shrinking bar makes every approval feel real.
- **Extra (usability):** the **"after: $X" marker when you hover Approve & pay**, so you can check a payment's effect before committing.
- **Extra (readability):** a legend with exact amounts, and a full spoken description for screen readers.

### 2. The agents as little Handsome Dans at the top, lit up when they're working (Quinn)
- **What:** a team strip under the top bar, with five SVG Handsome Dans, each in its own gear. It stays on screen when you scroll.
  - **Working:** the Dan bounces on a glowing game-piece base, with a speech bubble saying what it's doing right now ("Read the lease", "Asking Accounting").
  - **Waiting on a teammate:** it sways, and the line under it says who it's waiting on ("Waiting on Inventory").
  - **Done:** it smiles, with a step count.
  - **Not called:** it's grayed out and snoozing ("zz"). It says "Standing by" during a run and "Not needed" after it.
- **Why:** you can see who's on the job at a glance, without reading the feed, and the mascot makes the team feel like Yale's own.
- **Extra (usability):** **click a Dan to follow just that agent.** The feed filters to their steps, a pill shows "Only Accounting ✕", and the Dan stays highlighted.
- **Extra (readability):** a blue **step-count badge** on each Dan, and Dans (not letter badges) on the "What each agent did" cards and Boss's call.

### 3. Brighter, more fun, like a modern board game, with slightly 3D tiles (Quinn)
- **What:**
  - outlined tiles with a hard drop shadow, buttons that press down, and game-card tickets with a coloured top band and a type icon (👕 order, 🏠 rent, 🏷️ price);
  - cards that tilt up slightly in 3D when you hover them, and a bright blue gradient top bar;
  - a "CC" game-box logo and a dotted board background.
- **Why:** it makes the desk feel like a game you play rather than a log you read, while staying calm enough for real money decisions.
- **Extra (usability):** the **Open → Agents → Your call → Done track** on every ticket, so you can see where each one stands on its way to done.
- **Extra (readability):** the feed's **plain-English tool names** and **view chips** ("Everything", "Conversation" = who asked whom and what they reported, "Board actions" = only steps that changed something), so a long run is easy to skim.
- **Extra:** clear keyboard focus rings and accessible contrast throughout.

### 4. Confetti and a wiggle dance when a ticket is resolved (Quinn)
- **What:** when a ticket turns resolved, a burst of blue and black confetti falls across the screen. The Handsome Dan who closed it does a little wiggle dance on the team strip, and a banner drops in, e.g. "Ticket #102 resolved! Accounting closed it out. 🎉", with the same Dan dancing. The credit goes to whoever asked for the last request a person decided, since that decision closed the ticket. If Boss closed it directly, Boss dances.
- **Why:** finishing a ticket should feel good. It's the reward moment of the game, and it also makes it obvious *that* a ticket closed and *who* did the work.
- **Extra (usability):** the banner names the agent, so the celebration also gives information. Click it to dismiss.
- **Extra (accessibility):** people who set **"reduce motion"** in their system get no confetti, bouncing or wiggling. The board stays still, and the banner still tells them the ticket resolved.

## Other choices

- **Approving as \_\_\_.** The approver's name is required, remembered in the browser, and written to `payments.approved_by`, so every payment has a person attached.
- **Rejecting needs a reason,** which goes on the ticket's board notes.
- **"Waiting on your call."** While a ticket has requests waiting on a person, its Run button is disabled and says so. Re-running the team mid-decision could race the approval, which happened once in the Problem 9 full run.
- **Link to a ticket:** the URL remembers the selected ticket (`#ticket-103`), so a ticket can be bookmarked or shared.
- **Reset board** asks for confirmation. After a reset, runs from before it are labelled as old in the feed.
- **Live updates** come from polling `/api/events` every 1.5 s during a run (only new events, using `since`), and refreshing tickets and cash every 10 s when idle.
