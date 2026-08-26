from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


AgentReActDecisionKind = Literal["tool", "final"]
AgentReActStatus = Literal[
    "idle",
    "running",
    "completed",
    "confirmation_required",
    "limit_reached",
    "failed",
]


def _observation_id() -> str:
    return f"observation-{uuid4().hex}"


class AgentReActContractModel(BaseModel):
    """Base model for stable ReAct orchestration contracts.

    These contracts intentionally expose structured decisions and compact
    observations only. They must never contain private chain-of-thought.
    """

    model_config = ConfigDict(extra="forbid")


class AgentReActDecision(AgentReActContractModel):
    """One bounded ReAct decision: call one tool or finish the task."""

    iteration: int = Field(ge=1)
    kind: AgentReActDecisionKind
    tool_name: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    action_summary: str = ""
    final_answer: str = ""

    @model_validator(mode="after")
    def validate_decision_shape(self) -> "AgentReActDecision":
        self.tool_name = self.tool_name.strip()
        self.action_summary = self.action_summary.strip()
        self.final_answer = self.final_answer.strip()
        if self.kind == "tool":
            if not self.tool_name:
                raise ValueError("tool decisions require tool_name")
            if self.final_answer:
                raise ValueError("tool decisions cannot include final_answer")
        else:
            if self.tool_name:
                raise ValueError("final decisions cannot include tool_name")
            if self.arguments:
                raise ValueError("final decisions cannot include tool arguments")
        return self


class AgentObservation(AgentReActContractModel):
    """Compact, model-safe result of one executed Agent action."""

    observation_id: str = Field(default_factory=_observation_id)
    iteration: int = Field(ge=1)
    tool_name: str
    success: bool
    summary: str = ""
    error_code: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_observation(self) -> "AgentObservation":
        self.observation_id = self.observation_id.strip()
        self.tool_name = self.tool_name.strip()
        self.summary = self.summary.strip()
        self.error_code = self.error_code.strip()
        self.evidence_ids = [item.strip() for item in self.evidence_ids if item.strip()]
        self.citation_ids = [item.strip() for item in self.citation_ids if item.strip()]
        if not self.observation_id:
            raise ValueError("observation_id must not be empty")
        if not self.tool_name:
            raise ValueError("observations require tool_name")
        return self


class AgentReActContext(AgentReActContractModel):
    """ReAct orchestration state stored alongside the existing plan contract."""

    status: AgentReActStatus = "idle"
    iteration: int = Field(default=0, ge=0)
    decisions: list[AgentReActDecision] = Field(default_factory=list)
    observations: list[AgentObservation] = Field(default_factory=list)
    last_decision: AgentReActDecision | None = None

    @model_validator(mode="after")
    def validate_context(self) -> "AgentReActContext":
        max_iteration = max(
            [0]
            + [item.iteration for item in self.decisions]
            + [item.iteration for item in self.observations]
        )
        if self.iteration < max_iteration:
            raise ValueError("iteration cannot be behind recorded ReAct history")
        if self.last_decision is not None:
            if not self.decisions:
                raise ValueError("last_decision requires at least one recorded decision")
            if self.last_decision != self.decisions[-1]:
                raise ValueError("last_decision must match the latest recorded decision")
        return self


__all__ = [
    "AgentObservation",
    "AgentReActContext",
    "AgentReActDecision",
    "AgentReActDecisionKind",
    "AgentReActStatus",
]
