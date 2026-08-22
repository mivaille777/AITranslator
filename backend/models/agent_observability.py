from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRunMetric(BaseModel):
    run_id: str
    trace_id: str
    session_id: str
    created_at: str
    status: str
    intent: str
    ui_mode: str
    tool_name: str
    provider: str
    model: str
    total_duration_ms: int = Field(ge=0)
    planning_duration_ms: int = Field(ge=0)
    tool_duration_ms: int = Field(ge=0)
    synthesis_duration_ms: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    timeout_count: int = Field(ge=0)
    fallback_reason: str
    event_count: int = Field(ge=0)


class AgentRecentRunsResponse(BaseModel):
    runs: list[AgentRunMetric] = Field(default_factory=list)


class AgentObservabilitySummaryResponse(BaseModel):
    sample_size: int = Field(ge=0)
    completed_runs: int = Field(ge=0)
    failed_runs: int = Field(ge=0)
    cancelled_runs: int = Field(ge=0)
    confirmation_required_runs: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    retry_rate: float = Field(ge=0.0, le=1.0)
    failure_rate: float = Field(ge=0.0, le=1.0)
    timeout_rate: float = Field(ge=0.0, le=1.0)
    fallback_rate: float = Field(ge=0.0, le=1.0)
    average_total_duration_ms: float = Field(ge=0.0)
    p95_total_duration_ms: int = Field(ge=0)
    average_planning_duration_ms: float = Field(ge=0.0)
    average_tool_duration_ms: float = Field(ge=0.0)
    average_synthesis_duration_ms: float = Field(ge=0.0)


class AgentEvaluationRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=128)
    expected_intent: str = Field(default="", max_length=128)
    expected_tool_name: str = Field(default="", max_length=128)
    expected_status: str = Field(default="completed", max_length=64)
    max_total_duration_ms: int = Field(default=0, ge=0)
    max_retry_count: int = Field(default=0, ge=0, le=10)
    require_zero_failures: bool = True


class AgentEvaluationResponse(BaseModel):
    case_id: str
    run_id: str
    trace_id: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    intent_match: bool
    tool_match: bool
    status_match: bool
    latency_pass: bool
    retry_pass: bool
    failure_pass: bool
    failures: list[str] = Field(default_factory=list)
