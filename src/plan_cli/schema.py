from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Pydantic models define the plan contract and response envelope.

class ExitCode(IntEnum):
    OK = 0
    VALIDATION_FAILED = 1
    EXECUTION_ERROR = 2
    APPROVAL_REQUIRED = 3
    DRIFT_DETECTED = 4
    UNKNOWN = 5


class AgentHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_command: str
    context: str
    requires_human: bool = False


class TaskEffort(BaseModel):
    model_config = ConfigDict(extra="allow")

    pessimistic: str
    realistic: str
    optimistic: str


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    description: str
    effort: TaskEffort
    dependencies: list[str] = Field(default_factory=list)
    validation: str
    owner: str | None = None
    status: str = "not-started"


class Phase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    priority: str = "medium"
    tasks: list[Task] = Field(default_factory=list)


class Outcome(BaseModel):
    model_config = ConfigDict(extra="allow")

    objective: str
    key_results: list[dict[str, Any]] = Field(default_factory=list)


class CurrentState(BaseModel):
    model_config = ConfigDict(extra="allow")

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    model_config = ConfigDict(extra="allow")

    decision: str
    rationale: str
    alternatives: list[str] = Field(default_factory=list)
    owner: str | None = None
    date: str | None = None


class Assumption(BaseModel):
    model_config = ConfigDict(extra="allow")

    assumption: str
    confidence: float
    validation: str


class DependencyEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_: str = Field(alias="from")
    to: str
    type: str = "hard"


class DependencyGraph(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    nodes: list[str] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    critical_path: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    description: str
    likelihood: float
    impact: float
    score: float
    mitigation: str | None = None
    owner: str | None = None
    status: str = "identified"


class RollbackPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    trigger: str
    action: str
    max_loss: str


class DoneCriterion(BaseModel):
    model_config = ConfigDict(extra="allow")

    criterion: str
    status: str


class Approval(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    status: str = "pending"
    date: str | None = None


class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")

    planned_duration_hours: float = 0.0
    confidence_50: str = "0h"
    confidence_85: str = "0h"
    confidence_95: str = "0h"
    scope_creep_count: int = 0
    replan_count: int = 0


class Learning(BaseModel):
    model_config = ConfigDict(extra="allow")

    planned_vs_actual: dict[str, Any] | None = None
    accuracy_score: float | None = None
    retrospective: str | None = None


class PlanDocument(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_: str | None = Field(default=None, alias="$schema")
    version: str = "2.1.0"
    id: str | None = None
    title: str | None = None
    mode: str
    created: str | None = None
    updated: str | None = None
    version_number: int | None = None
    status: str = "draft"
    approval_gate: bool | None = None
    compliance: list[str] = Field(default_factory=list)
    outcomes: Outcome | None = None
    current_state: CurrentState | None = None
    decisions: list[Decision] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    phases: list[Phase] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    dependency_graph: DependencyGraph | None = None
    risks: list[Risk] = Field(default_factory=list)
    overall_risk_score: float | None = None
    plan_quality_score: float | None = None
    rollback_plan: RollbackPlan | None = None
    rollback_policy: str | None = None
    done_criteria: list[DoneCriterion] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    learning: Learning = Field(default_factory=Learning)


class PlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    exit_code: ExitCode
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)
    agent_hint: AgentHint
    plan_hash: str | None = None
    summary: str | None = None


def schema_for(target: str) -> dict[str, Any]:
    if target == "response":
        return PlanResponse.model_json_schema()
    return PlanDocument.model_json_schema()
