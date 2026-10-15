"""Campus Customs Multi-Agent Operations: the agent team and the dashboard's backend.

Start the backend from the backend/ folder, with the HW5 virtual environment active:

    uvicorn main:app --reload --port 8000

The React dashboard then calls http://localhost:8000/api/... (CORS allows the Vite
dev server on port 5173). Interactive docs: http://localhost:8000/docs

Or run the team from the command line, without the web server:

    python backend/main.py ticket 101                 Boss works one ticket with the team
    python backend/main.py board                      Boss works every open ticket, one at a time
    python backend/main.py ask Inventory "question"   ask any one agent directly

This file has six parts:
  1. Setup: paths, the Portkey key from .env, the one model (gpt-6-luna), token limits
  2. Audit trail: append-only output/audit_trail.json, one entry per agent-loop step
  3. The agent team: Boss, Inventory, Accounting, Facilities, Customer Service
     (their prompts are in prompts/<role>.md, their data types in models.py)
  4. Team entry points: work one ticket, work the board, ask one agent
  5. FastAPI routes for the dashboard
  6. Command line

Every shop fact and every change goes through the Campus Customs MCP server
(mcp_server/server.py over data/campus_customs_new.db). There is no second
shop-tools layer. The one route that spends money is
POST /api/approvals/{id}/approve, which a person triggers by clicking Approve. It
calls the human-only approve_request MCP tool, which no agent can see.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

import argparse  # noqa: E402
import asyncio  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from collections.abc import Coroutine  # noqa: E402
from concurrent.futures import Future  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from dataclasses import asdict, dataclass  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, TypeVar, get_args  # noqa: E402
from uuid import uuid4  # noqa: E402

from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai import Agent, ModelRetry, RunContext, RunUsage, ToolOutput, UsageLimitExceeded, UsageLimits  # noqa: E402
from pydantic_ai.mcp import MCPToolset, StdioTransport  # noqa: E402
from pydantic_ai.messages import ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402

from models import (  # noqa: E402
    AGENT_NAMES,
    AgentName,
    AgentOutput,
    AuditEntry,
    BossDecision,
    DelegationRefused,
    TeamDeps,
    TeamReport,
)

T = TypeVar("T")


# =====================================================================================
# 1. Setup
# =====================================================================================

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROMPTS = HERE / "prompts"
MCP_SERVER = ROOT / "mcp_server" / "server.py"

# HW5/.env first if it exists, then the course-wide .env one level up (where PORTKEY_API_KEY lives).
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

# The original database is the reset point and is never written. The working copy is
# what the MCP server reads and writes. CAMPUS_CUSTOMS_DB can point it at a scratch
# copy for tests.
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = Path(os.getenv("CAMPUS_CUSTOMS_DB") or ROOT / "data" / "campus_customs_new.db")

# The only model this homework may use, for every agent. Deliberately not read from
# the environment, so no other model can slip in through a .env setting.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Limits that keep loops and token use in check. One top-level task (e.g. Boss working
# one ticket) shares a single usage counter across every teammate it asks, so these caps
# cover the whole delegation tree.
USAGE_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=80, total_tokens_limit=400_000)
# Per model response: a cap on output (reasoning + answer) and low reasoning effort, which is
# plenty for lookups and hand-offs and keeps each step short.
# A normal step uses ~130 output tokens (90% under 500); the cap cuts off the rare looping answer.
MODEL_SETTINGS = OpenAIResponsesModelSettings(max_tokens=3000, openai_reasoning_effort="low")
MAX_DEPTH = 2  # Boss -> teammate -> teammate, no deeper
MAX_DELEGATIONS = 8  # hand-offs per top-level task


# =====================================================================================
# 2. Audit trail: output/audit_trail.json
# =====================================================================================
# Every agent run (Boss on a ticket, or a teammate Boss asked) writes:
#   run_start       who is running, the task, and who asked them
#   model_request   what went into this step: the results of the previous step's tool calls
#   tool_result     each tool's result (shortened), including a teammate's whole report
#   retry           a tool error or an output check that sent the model back
#   model_response  what the model did at this step: its text, which tools it called, tokens used
#   tool_call       each tool call with its arguments
#   run_end         the final output, total usage and duration (or run_error)
#
# Entries are written one at a time while the run is still going, so a run that crashes
# still leaves its history. The file is never wiped: existing entries are always read back
# and kept, and if the file is ever unreadable it is moved aside
# (audit_trail.corrupt-<time>.json) rather than overwritten. root_run_id ties a whole
# delegation tree together; parent_run_id shows who asked whom. CAMPUS_CUSTOMS_AUDIT can
# point tests at a scratch file.

AUDIT_PATH = Path(os.getenv("CAMPUS_CUSTOMS_AUDIT") or ROOT / "output" / "audit_trail.json")
ARGS_CHARS = 400
RESULT_CHARS = 600
TEXT_CHARS = 600

_LOCK = asyncio.Lock()
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LONG_NUMBER = re.compile(r"\b(?:\d[ -]?){12,19}\b")


def new_run_id(agent: str) -> str:
    slug = agent.lower().replace(" ", "-")
    return f"{slug}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:6]}"


def short(value: Any, limit: int) -> str:
    """A one-line, length-capped version of any value, with emails and card-like numbers masked."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text = LONG_NUMBER.sub("[number]", EMAIL.sub("[email]", " ".join(text.split())))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _usage(u: Any) -> dict[str, Any]:
    return {
        k: getattr(u, k)
        for k in ("requests", "input_tokens", "output_tokens", "tool_calls")
        if getattr(u, k, None) is not None
    }


class AuditTrail:
    """Writes the entries for one agent run."""

    def __init__(self, deps: TeamDeps, path: Path = AUDIT_PATH) -> None:
        self.deps = deps
        self.path = path
        self.step = 0
        self.started = time.perf_counter()
        self.baseline: dict[str, Any] = {}

    async def append(self, event: str, **fields: Any) -> None:
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            root_run_id=self.deps.root_run_id,
            run_id=self.deps.run_id,
            parent_run_id=self.deps.parent_run_id,
            agent=self.deps.me,
            depth=self.deps.depth,
            ticket_id=self.deps.ticket_id,
            step=self.step,
            event=event,
            **fields,
        )
        async with _LOCK:
            entries = self._read()
            entries.append(entry.model_dump(exclude_none=True))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(temp, self.path)  # atomic, so a crash mid-write can't truncate the trail

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            entries = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                return entries
        except json.JSONDecodeError:
            pass
        # Never wipe history: keep the unreadable file and start a fresh list beside it.
        self.path.rename(self.path.with_name(f"audit_trail.corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
        return []

    async def start(self, task: str, usage: Any) -> None:
        # Teammates share the top-level run's usage counter, so remember where this run started.
        self.baseline = _usage(usage)
        await self.append("run_start", text=short(task, TEXT_CHARS),
                          detail={"chain": list(self.deps.chain)})

    async def record_node(self, node: Any) -> None:
        """Log what one step of the agent loop did."""
        if Agent.is_model_request_node(node):
            # Results of the previous step's tool calls (and any retries) go in with this request.
            for part in node.request.parts:
                if isinstance(part, ToolReturnPart):
                    await self.append("tool_result", tool_name=part.tool_name,
                                      tool_result=short(part.content, RESULT_CHARS))
                elif isinstance(part, RetryPromptPart):
                    await self.append("retry", tool_name=part.tool_name,
                                      tool_result=short(part.content, RESULT_CHARS))
            self.step += 1
            await self.append("model_request")
        elif Agent.is_call_tools_node(node):
            response = node.model_response
            calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
            text = " ".join(p.content for p in response.parts if isinstance(p, TextPart)).strip()
            await self.append(
                "model_response",
                model=response.model_name,
                text=short(text, TEXT_CHARS) if text else None,
                usage=_usage(response.usage),
                detail={"tool_calls": [c.tool_name for c in calls]},
            )
            for call in calls:
                await self.append("tool_call", tool_name=call.tool_name,
                                  tool_args=short(call.args_as_dict(), ARGS_CHARS))

    async def refused(self, teammate: str, reason: str) -> None:
        await self.append("delegation_refused", tool_name="ask_teammate",
                          detail={"teammate": teammate, "reason": reason})

    def _usage_detail(self, usage: Any) -> dict[str, Any]:
        total = _usage(usage)
        this_run = {k: v - self.baseline.get(k, 0) for k, v in total.items()}
        return {"this_run_and_its_teammates": this_run, "whole_task_so_far": total}

    async def end(self, output: Any, usage: Any) -> None:
        detail: dict[str, Any] = {"duration_ms": round((time.perf_counter() - self.started) * 1000)}
        # The one-line answer (a teammate's answer, or Boss's decision and final status), kept whole
        # so the dashboard can summarize each agent's work without parsing the shortened output.
        if answer := getattr(output, "answer", None) or getattr(output, "decision", None):
            detail["answer"] = short(answer, 800)
        for key in ("final_status", "approval_ids", "draft_ids"):
            if (value := getattr(output, key, None)) not in (None, []):
                detail[key] = value
        await self.append("run_end", text=short(output, TEXT_CHARS), usage=self._usage_detail(usage), detail=detail)

    async def error(self, exc: BaseException, usage: Any) -> None:
        await self.append(
            "run_error",
            text=short(f"{type(exc).__name__}: {exc}", TEXT_CHARS),
            usage=self._usage_detail(usage),
            detail={"duration_ms": round((time.perf_counter() - self.started) * 1000)},
        )


# =====================================================================================
# 3. The agent team
# =====================================================================================
# Boss, Inventory, Accounting, Facilities and Customer Service each get:
#   - instructions from prompts/<role>.md, plus a short "right now" note
#     (who asked them, which ticket, which teammates they can still ask);
#   - only the MCP tools their role needs;
#   - ask_teammate, so any agent can hand work to any other (full connectivity);
#   - the same model: gpt-6-luna through Portkey.
# run_agent() is the agent loop: it steps through a run node by node with agent.iter()
# and writes every step to the audit trail.

COMMON_TOOLS = frozenset({"get_shop_date", "list_tickets", "get_ticket", "add_ticket_note"})


@dataclass(frozen=True)
class Role:
    prompt: str  # file in prompts/
    mcp_tools: frozenset[str]  # the only MCP tools this agent can see
    output_type: type[TeamReport] | type[BossDecision]


ROLES: dict[AgentName, Role] = {
    "Boss": Role(
        "boss.md",
        COMMON_TOOLS | {"set_ticket_status", "check_stock", "get_pricing", "list_vendors", "get_invoice",
                        "list_unpaid_invoices", "get_lease", "get_cash_position", "list_approvals"},
        BossDecision,
    ),
    "Inventory": Role(
        "inventory.md",
        COMMON_TOOLS | {"check_stock", "list_vendors", "get_invoice", "get_pricing"},
        TeamReport,
    ),
    "Accounting": Role(
        "accounting.md",
        COMMON_TOOLS | {"get_cash_position", "list_unpaid_invoices", "get_invoice", "list_vendors", "get_pricing",
                        "get_lease", "list_approvals", "request_payment", "request_purchase_order",
                        "request_price_override"},
        TeamReport,
    ),
    "Facilities": Role(
        "facilities.md",
        COMMON_TOOLS | {"get_lease", "get_cash_position", "list_approvals"},
        TeamReport,
    ),
    "Customer Service": Role(
        "customer_service.md",
        COMMON_TOOLS | {"draft_customer_message", "check_stock", "get_pricing", "list_approvals"},
        TeamReport,
    ),
}

# MCP tools only a person may trigger (from the dashboard, via the approve/reject routes below).
# approve_request is the only tool that spends cash. No agent may ever see these.
HUMAN_ONLY_TOOLS = frozenset({"approve_request", "reject_request"})
assert not any(role.mcp_tools & HUMAN_ONLY_TOOLS for role in ROLES.values()), "agents must not get human-only tools"


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna, reached through Portkey's OpenAI-compatible endpoint with PORTKEY_API_KEY.

    Uses the Responses API: gpt-6-luna doesn't accept function tools on
    /v1/chat/completions while it is reasoning, but does on /v1/responses.
    """
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (put it in HW5/.env; see .env.example).")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=os.getenv("PORTKEY_BASE_URL", PORTKEY_BASE_URL),
        default_headers={"x-portkey-api-key": api_key},
        timeout=90,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def shop_mcp() -> MCPToolset:
    """One stdio connection to the Campus Customs MCP server, shared by all five agents.

    The server is started with this same Python and HW5/ as its folder, and is
    told exactly which database to open (WORKING_DB), so the backend's reset
    and the server always agree on the file.
    """
    env = {
        "CAMPUS_CUSTOMS_DB": str(WORKING_DB),
        "FASTMCP_LOG_LEVEL": "WARNING",  # keep the server's startup logs out of the console
    }
    transport = StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], cwd=str(ROOT), env=env)
    return MCPToolset(transport, max_retries=1)


_ACTIVE_TRAILS: dict[str, AuditTrail] = {}  # run_id -> trail, so refusals log under the asking run


async def ask_teammate(ctx: RunContext[TeamDeps], teammate: AgentName, task: str) -> dict[str, Any]:
    """Hand a task to another agent on the team and wait for their report.

    teammate: "Boss", "Inventory", "Accounting", "Facilities" or "Customer Service".
    task: a complete, self-contained request. Include the ticket id, SKU, size,
    qty, invoice/lease/vendor ids, amounts and any facts already confirmed, since
    the teammate can't see your conversation.
    Returns their report: answer, facts with sources, approval/draft ids, blockers
    and recommendation. If a guardrail stops the hand-off you get ok=false and the
    reason; then finish with what you have.
    """
    deps = ctx.deps
    reason = None
    if teammate == deps.me:
        reason = "You can't delegate to yourself."
    elif teammate in deps.chain:
        reason = (f"{teammate} is already working on this above you (chain: {' -> '.join(deps.chain)}). "
                  "Put your question or finding in your answer instead; they will read it.")
    elif deps.depth >= MAX_DEPTH:
        reason = f"Delegation depth limit ({MAX_DEPTH}) reached. Answer with what you have."
    elif deps.budget.delegations >= MAX_DELEGATIONS:
        reason = f"This task has used all {MAX_DELEGATIONS} hand-offs. Finish with what you have."
    if reason:
        trail = _ACTIVE_TRAILS.get(deps.run_id)
        if trail:
            await trail.refused(teammate, reason)
        return DelegationRefused(error=reason).model_dump()

    deps.budget.delegations += 1
    child = TeamDeps(
        root_run_id=deps.root_run_id,
        run_id=new_run_id(teammate),
        chain=(*deps.chain, teammate),
        ticket_id=deps.ticket_id,
        parent_run_id=deps.run_id,
        budget=deps.budget,
    )
    try:
        report = await run_agent(teammate, task, child, usage=ctx.usage)
    except UsageLimitExceeded:
        raise  # a token/request cap stops the whole task, not just this hand-off
    except Exception as exc:  # the teammate failed; let the asker decide what to do
        return DelegationRefused(error=f"{teammate} could not finish: {type(exc).__name__}: {exc}").model_dump()
    return report.model_dump()


def _tools_called(ctx: RunContext[TeamDeps]) -> set[str]:
    return {
        part.tool_name
        for message in ctx.messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart)
    }


@lru_cache(maxsize=None)
def get_agent(name: AgentName) -> Agent[TeamDeps, AgentOutput]:
    """Build one agent (once) from its role."""
    role = ROLES[name]
    agent = Agent(
        build_model(),
        name=name,
        deps_type=TeamDeps,
        # Tool output only: the agent must finish by calling final_result with the typed report,
        # never by writing free text, which also stops runaway prose from burning tokens.
        output_type=ToolOutput(role.output_type),
        toolsets=[shop_mcp().filtered(lambda ctx, tool_def: tool_def.name in role.mcp_tools)],
        tools=[ask_teammate],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )

    @agent.instructions
    def role_prompt() -> str:
        # Read on every run, so prompt edits apply without a restart.
        return (PROMPTS / role.prompt).read_text(encoding="utf-8")

    @agent.instructions
    def right_now(ctx: RunContext[TeamDeps]) -> str:
        d = ctx.deps
        lines = [
            f"## Right now\nYou are {d.me}. You were asked by "
            f"{d.chain[-2] if d.depth else 'the human operator (top-level task)'}.",
            f"Delegation chain: {' -> '.join(d.chain)}.",
        ]
        if d.ticket_id is not None:
            lines.append(f"This work is for ticket {d.ticket_id}.")
        others = [n for n in AGENT_NAMES if n not in d.chain]
        left = MAX_DELEGATIONS - d.budget.delegations
        if d.depth >= MAX_DEPTH or left <= 0 or not others:
            lines.append("You can't hand work off any further. Finish with your own tools and report back.")
        else:
            lines.append(f"Teammates you can ask with ask_teammate: {', '.join(others)}. "
                         f"Hand-offs left for this whole task: {left}.")
        return "\n".join(lines)

    @agent.output_validator
    def grounded(ctx: RunContext[TeamDeps], output: AgentOutput) -> AgentOutput:
        # Every answer must rest on at least one MCP lookup made in this run, not on memory.
        if not _tools_called(ctx) & role.mcp_tools:
            raise ModelRetry(
                "You answered without calling any of your MCP tools. Look the facts up first "
                "(for a ticket, start with get_ticket) and use exactly what the tools return."
            )
        if isinstance(output, TeamReport) and output.agent != name:
            output.agent = name
        return output

    return agent


async def run_agent(
    name: AgentName, task: str, deps: TeamDeps, *, usage: RunUsage | None = None
) -> AgentOutput:
    """The agent loop: run one agent step by step, auditing every node.

    Each step is a model request (with the previous step's tool results), then
    the model's response (text and tool calls), then the tool calls themselves,
    and so on until the agent returns its typed output. ask_teammate calls inside
    the loop run a teammate's own loop with the same usage counter.
    """
    agent = get_agent(name)
    usage = usage if usage is not None else RunUsage()
    trail = AuditTrail(deps)
    _ACTIVE_TRAILS[deps.run_id] = trail
    await trail.start(task, usage)
    try:
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=USAGE_LIMITS) as run:
            async for node in run:
                await trail.record_node(node)
        output = run.result.output
    except BaseException as exc:
        await trail.error(exc, usage)
        raise
    finally:
        _ACTIVE_TRAILS.pop(deps.run_id, None)
    await trail.end(output, usage)
    return output


# =====================================================================================
# 4. Team entry points
# =====================================================================================


def _top_level(
    agent: AgentName, label: str, ticket_id: int | None = None, root_run_id: str | None = None
) -> TeamDeps:
    return TeamDeps(root_run_id=root_run_id or new_run_id(label), run_id=new_run_id(agent),
                    chain=(agent,), ticket_id=ticket_id)


async def work_ticket(ticket_id: int, root_run_id: str | None = None) -> BossDecision:
    """Boss works one ticket, asking teammates as needed, and makes the final call.

    root_run_id lets a caller (the dashboard routes) know the run's id up front,
    so it can follow the run's events in the audit trail while it is going.
    """
    task = (
        f"Work ticket {ticket_id} from start to finish. Start with get_ticket({ticket_id}), route the work to "
        "the right teammates, make the final call, make sure everything a human must approve is on the board "
        "and any customer-facing reply is drafted, then set the ticket status with a note."
    )
    async with shop_mcp():  # one MCP server process for the whole task
        return await run_agent("Boss", task, _top_level("Boss", f"ticket-{ticket_id}", ticket_id, root_run_id))


async def work_board() -> list[BossDecision]:
    """The board loop: Boss works each open ticket in turn, oldest first."""
    decisions = []
    async with shop_mcp():
        board = await shop_mcp().direct_call_tool("list_tickets", {"status": "open"})
        for ticket in board["tickets"]:
            decisions.append(await work_ticket(ticket["id"]))
    return decisions


async def ask(agent: AgentName, question: str) -> AgentOutput:
    """Ask one agent directly (it can still ask its teammates)."""
    async with shop_mcp():
        return await run_agent(agent, question, _top_level(agent, f"ask-{agent}"))


# =====================================================================================
# 5. FastAPI routes for the dashboard
# =====================================================================================
# The agents and their MCP connection (a stdio subprocess) run on a dedicated event loop
# in a background thread. uvicorn --reload on Windows serves requests on a loop that
# can't start subprocesses, so the team gets a loop that can. Routes hand work to it and
# await the result.


class TeamLoop:
    def __init__(self) -> None:
        self.loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._serve, name="team-loop", daemon=True)

    def _serve(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self) -> None:
        self.thread.start()

    def submit(self, coro: Coroutine[Any, Any, T]) -> Future[T]:
        """Start a coroutine on the team loop without waiting for it."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run a coroutine on the team loop and wait for its result."""
        return await asyncio.wrap_future(self.submit(coro))

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)


team_loop = TeamLoop()


async def mcp(tool: str, **args: Any) -> dict[str, Any]:
    """Call one Campus Customs MCP tool (on the team loop) and return its result."""
    try:
        return await team_loop.run(shop_mcp().direct_call_tool(tool, args))
    except Exception as exc:  # the MCP server is down or the database is missing
        raise HTTPException(503, f"MCP tool {tool} failed: {type(exc).__name__}: {exc}") from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    team_loop.start()
    await team_loop.run(shop_mcp().__aenter__())  # one MCP server process for the app's lifetime
    try:
        yield
    finally:
        await team_loop.run(shop_mcp().__aexit__(None, None, None))
        team_loop.stop()


app = FastAPI(title="Campus Customs Multi-Agent Operations", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class TicketRun:
    root_run_id: str
    ticket_id: int
    status: str  # running | done | failed
    started_at: str
    finished_at: str | None = None
    decision: dict[str, Any] | None = None
    error: str | None = None


RUNS: dict[str, TicketRun] = {}
_RUNS_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _running() -> TicketRun | None:
    return next((r for r in RUNS.values() if r.status == "running"), None)


def _finish(run: TicketRun, fut: Future) -> None:
    with _RUNS_LOCK:
        run.finished_at = _now()
        if fut.cancelled():
            run.status, run.error = "failed", "cancelled"
        elif (exc := fut.exception()) is not None:
            run.status, run.error = "failed", f"{type(exc).__name__}: {exc}"
        else:
            run.status, run.decision = "done", fut.result().model_dump()


# When the board was last reset (kept beside the database, so it survives a backend
# restart). The dashboard uses it to mark agent runs from before the reset as old.
LAST_RESET = WORKING_DB.with_name("last_reset.txt")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Is the backend up, and what is it pointed at."""
    running = _running()
    return {
        "ok": True,
        "model": MODEL_NAME,
        "mcp_server": MCP_SERVER.relative_to(ROOT).as_posix(),
        "database": WORKING_DB.name,
        "run_in_progress": running.root_run_id if running else None,
        "last_reset_at": LAST_RESET.read_text(encoding="utf-8").strip() if LAST_RESET.exists() else None,
    }


@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    """Every ticket, whether it is open or resolved, plus what is on the board for it."""
    board = await mcp("list_tickets", status="all")
    tickets = []
    for t in board["tickets"]:
        detail = await mcp("get_ticket", ticket_id=t["id"])
        tickets.append({
            **t,
            "state": "resolved" if t["status"] == "resolved" else "open",
            "approvals": detail["approval_requests"],
            "drafts": detail["drafts"],
            "updates": detail["updates"],
        })
    shop = await mcp("get_shop_date")
    return {"date_today": shop["date_today"], "count": len(tickets), "tickets": tickets}


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Start the agent team (Boss first) on one ticket. Returns at once; follow it with
    /api/events?root_run_id=… and /api/runs/{root_run_id}."""
    if not (await mcp("get_ticket", ticket_id=ticket_id)).get("found"):
        raise HTTPException(404, f"No ticket with id {ticket_id}.")
    with _RUNS_LOCK:
        if running := _running():
            raise HTTPException(409, f"Ticket {running.ticket_id} is still running ({running.root_run_id}). "
                                     "One run at a time.")
        run = TicketRun(new_run_id(f"ticket-{ticket_id}"), ticket_id, "running", _now())
        RUNS[run.root_run_id] = run
    fut = team_loop.submit(work_ticket(ticket_id, root_run_id=run.root_run_id))
    fut.add_done_callback(lambda f: _finish(run, f))
    return {
        "root_run_id": run.root_run_id,
        "ticket_id": ticket_id,
        "status": "running",
        "events_url": f"/api/events?root_run_id={run.root_run_id}",
        "status_url": f"/api/runs/{run.root_run_id}",
    }


@app.get("/api/runs")
async def list_runs() -> dict[str, Any]:
    """Ticket runs started since the backend came up, newest first."""
    with _RUNS_LOCK:
        runs = [asdict(r) for r in sorted(RUNS.values(), key=lambda r: r.started_at, reverse=True)]
    return {"runs": runs}


@app.get("/api/runs/{root_run_id}")
async def get_run(root_run_id: str) -> dict[str, Any]:
    """One ticket run: running, done (with Boss's decision) or failed (with the error)."""
    with _RUNS_LOCK:
        run = RUNS.get(root_run_id)
        if run is None:
            raise HTTPException(404, f"No run {root_run_id} since the backend started.")
        return asdict(run)


EVENT_KINDS = {"run_start", "model_response", "tool_call", "tool_result", "retry",
               "delegation_refused", "run_end", "run_error"}
ASK_ARGS = re.compile(r'"teammate":\s*"(?P<teammate>[^"]+)",\s*"task":\s*"(?P<task>.*)', re.S)


def _teammate(e: dict[str, Any]) -> str | None:
    """Who an ask_teammate call (or a refused hand-off) went to."""
    if e.get("event") == "delegation_refused":
        return (e.get("detail") or {}).get("teammate")
    if e.get("event") == "tool_call" and e.get("tool_name") == "ask_teammate":
        m = ASK_ARGS.search(e.get("tool_args") or "")
        return m["teammate"] if m else None
    return None


def _describe(e: dict[str, Any]) -> str:
    """One readable line for the board: what the agent said or which tool it used."""
    agent, kind = e["agent"], e["event"]
    text, tool = e.get("text") or "", e.get("tool_name") or ""
    if kind == "run_start":
        return f"{agent} {'was asked' if e.get('depth') else 'started'}: {text}"
    if kind == "model_response":
        calls = (e.get("detail") or {}).get("tool_calls") or []
        said = f"{agent} said: {text}" if text else f"{agent} is thinking"
        return f"{said} → calls {', '.join(calls)}" if calls else said
    if kind == "tool_call":
        # The trail shortens long arguments, so read the teammate and task without needing valid JSON.
        if tool == "ask_teammate" and (m := ASK_ARGS.search(e.get("tool_args") or "")):
            return f"{agent} asked {m['teammate']}: {m['task'].rstrip('\"}')}"
        return f"{agent} called {tool}({e.get('tool_args') or ''})"
    if kind == "tool_result":
        return f"{tool} → {e.get('tool_result') or ''}"
    if kind == "retry":
        return f"{agent} was sent back to fix something: {e.get('tool_result') or ''}"
    if kind == "delegation_refused":
        d = e.get("detail") or {}
        return f"{agent} couldn't hand off to {d.get('teammate')}: {d.get('reason')}"
    if kind == "run_end":
        return f"{agent} finished: {(e.get('detail') or {}).get('answer') or text}"
    return f"{agent} failed: {text}"


@app.get("/api/events")
async def events(
    since: int = Query(0, ge=0, description="Only events at or after this index (use next_since from the last call)."),
    limit: int = Query(100, ge=1, le=500),
    ticket_id: int | None = None,
    root_run_id: str | None = None,
) -> dict[str, Any]:
    """Recent agent events from output/audit_trail.json: what each agent said and which tools it used."""
    entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
    picked = [
        (i, e) for i, e in enumerate(entries)
        if i >= since and e.get("event") in EVENT_KINDS
        and (ticket_id is None or e.get("ticket_id") == ticket_id)
        and (root_run_id is None or e.get("root_run_id") == root_run_id)
    ][-limit:]
    return {
        "events": [
            {
                "index": i,
                "timestamp": e["timestamp"],
                "agent": e["agent"],
                "depth": e.get("depth", 0),
                "ticket_id": e.get("ticket_id"),
                "root_run_id": e["root_run_id"],
                "run_id": e["run_id"],
                "parent_run_id": e.get("parent_run_id"),
                "event": e["event"],
                "tool_name": e.get("tool_name"),
                "tool_args": e.get("tool_args"),
                "teammate": _teammate(e),
                "text": e.get("text"),
                "answer": (e.get("detail") or {}).get("answer"),
                "summary": _describe(e),
                "usage": e.get("usage"),
            }
            for i, e in picked
        ],
        "next_since": len(entries),
        "total": len(entries),
    }


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="The person who clicked Approve.")
    note: str | None = None


class RejectBody(BaseModel):
    decided_by: str = Field(min_length=1, description="The person who clicked Reject.")
    note: str = Field(min_length=1, description="Why it was rejected.")


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApproveBody) -> dict[str, Any]:
    """A person approved a pending request. For a payment or purchase order this is
    what actually spends cash (refused if the balance would go negative)."""
    result = await mcp("approve_request", approval_id=approval_id, approved_by=body.approved_by, note=body.note)
    if not result.get("ok"):
        raise HTTPException(409, result)
    return result


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: RejectBody) -> dict[str, Any]:
    """A person rejected a pending request, which frees the cash it was holding."""
    result = await mcp("reject_request", approval_id=approval_id, decided_by=body.decided_by, note=body.note)
    if not result.get("ok"):
        raise HTTPException(409, result)
    return result


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """The checking balance from cash_accounts, plus what pending requests already hold."""
    position = await mcp("get_cash_position")
    checking = next((a for a in position["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "balance_date": checking["balance_date"],
        "already_committed": checking["already_committed"],
        "available": checking["available"],
        "committed_requests": position["committed_requests"],
        "date_today": position["date_today"],
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Copy the original database over the working copy for a fresh run. The audit trail is kept."""
    with _RUNS_LOCK:
        if running := _running():
            raise HTTPException(409, f"Can't reset while ticket {running.ticket_id} is running.")
        shutil.copyfile(ORIGINAL_DB, WORKING_DB)
        LAST_RESET.write_text(_now(), encoding="utf-8")
    return {
        "ok": True,
        "copied_from": ORIGINAL_DB.relative_to(ROOT).as_posix(),
        "working_copy": WORKING_DB.name,
        "identical_to_original": _sha256(WORKING_DB) == _sha256(ORIGINAL_DB),
        "note": "Tickets, cash, invoices and leases are back to their original values and the board is empty. "
                "output/audit_trail.json is append-only and was not touched.",
    }


# =====================================================================================
# 6. Command line
# =====================================================================================


def cli() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs agent team")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ticket", help="Boss works one ticket").add_argument("ticket_id", type=int)
    sub.add_parser("board", help="Boss works every open ticket")
    p_ask = sub.add_parser("ask", help="ask one agent directly")
    p_ask.add_argument("agent", choices=get_args(AgentName))
    p_ask.add_argument("question")
    args = parser.parse_args()

    if args.command == "ticket":
        result = asyncio.run(work_ticket(args.ticket_id))
    elif args.command == "board":
        result = asyncio.run(work_board())
    else:
        result = asyncio.run(ask(args.agent, args.question))
    items = result if isinstance(result, list) else [result]
    print(json.dumps([r.model_dump() for r in items], indent=2))


if __name__ == "__main__":
    cli()
