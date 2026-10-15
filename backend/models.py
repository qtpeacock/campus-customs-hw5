"""Data types for the Campus Customs agent team: names, what each agent hands
back, the state shared down a delegation chain, and audit-trail entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]
AGENT_NAMES: tuple[AgentName, ...] = ("Boss", "Inventory", "Accounting", "Facilities", "Customer Service")

TicketStatus = Literal["open", "in_progress", "waiting_approval", "resolved"]


# ---------- What agents hand back ----------


class Fact(BaseModel):
    """One confirmed fact and where it came from, so every claim can be traced."""

    fact: str = Field(description="The fact, with exact numbers, ids and dates.")
    source: str = Field(description="The MCP tool (e.g. check_stock) or teammate that confirmed it.")


class TeamReport(BaseModel):
    """What Inventory, Accounting, Facilities and Customer Service return to whoever asked them."""

    agent: AgentName
    ticket_id: int | None = Field(default=None, description="The ticket this work was for, if any.")
    answer: str = Field(description="Direct answer to the task, with the key numbers.")
    facts: list[Fact] = Field(default_factory=list, max_length=10, description="Up to 10 facts the answer relies on, each with its source.")
    actions: list[str] = Field(default_factory=list, max_length=8, description="What this agent put on the board (notes, requests, drafts).")
    approval_ids: list[int] = Field(default_factory=list, description="Approval request ids filed or confirmed.")
    draft_ids: list[int] = Field(default_factory=list, description="Draft message ids saved.")
    blockers: list[str] = Field(default_factory=list, max_length=6, description="What stops progress (unpaid invoice, cash, missing facts).")
    recommendation: str = Field(default="", description="What should happen next and who should do it.")


class BossDecision(BaseModel):
    """Boss's final call on one ticket."""

    ticket_id: int | None
    final_status: TicketStatus = Field(description="The status Boss set on the board.")
    decision: str = Field(description="The call Boss made, in one or two sentences.")
    summary: str = Field(description="Key facts with numbers, and who confirmed them.")
    teammates_consulted: list[AgentName] = Field(default_factory=list)
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests on the board for this ticket.")
    draft_ids: list[int] = Field(default_factory=list, description="Draft messages on the board for this ticket.")
    needs_human: list[str] = Field(default_factory=list, max_length=6, description="Each thing a person must approve or decide.")
    next_steps: list[str] = Field(default_factory=list, max_length=6)


AgentOutput = TeamReport | BossDecision


class DelegationRefused(BaseModel):
    """Returned by ask_teammate instead of a report when a guardrail stops the hand-off."""

    ok: Literal[False] = False
    error: str


# ---------- State shared down one delegation chain ----------


@dataclass
class TeamBudget:
    """Counters shared by every agent working on the same top-level task."""

    delegations: int = 0


@dataclass
class TeamDeps:
    """Passed to every agent run. A teammate's run gets a copy with itself added to the chain."""

    root_run_id: str  # the whole top-level task
    run_id: str  # this agent's run
    chain: tuple[AgentName, ...]  # who asked whom, top-level agent first; the last one is "me"
    ticket_id: int | None = None
    parent_run_id: str | None = None  # the run that asked this one
    budget: TeamBudget = field(default_factory=TeamBudget)

    @property
    def me(self) -> AgentName:
        return self.chain[-1]

    @property
    def depth(self) -> int:
        return len(self.chain) - 1


# ---------- Audit trail ----------


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json: one event in one agent's loop."""

    timestamp: str
    root_run_id: str  # the whole top-level task (e.g. Boss working ticket 101)
    run_id: str  # this agent's run
    parent_run_id: str | None = None  # the run that delegated to this one
    agent: AgentName
    depth: int  # 0 = top-level agent, 1 = asked by it, ...
    ticket_id: int | None = None
    step: int  # model round-trip number within this run
    event: str  # run_start | model_request | model_response | tool_call | tool_result | retry | delegation_refused | run_end | run_error
    model: str | None = None
    tool_name: str | None = None
    tool_args: str | None = None
    tool_result: str | None = None
    text: str | None = None
    usage: dict[str, Any] | None = None
    detail: dict[str, Any] | None = None
