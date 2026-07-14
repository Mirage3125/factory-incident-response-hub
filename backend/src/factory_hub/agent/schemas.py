from pydantic import BaseModel, ConfigDict, Field, field_validator

from factory_hub.domain.enums import Severity


class AgentModel(BaseModel):
    model_config = ConfigDict(use_enum_values=False)


class AgentCause(AgentModel):
    cause: str = Field(min_length=1, max_length=240)
    evidence: str = Field(min_length=1, max_length=500)


class AgentInput(AgentModel):
    incident_id: int
    incident_no: str
    equipment_code: str
    equipment_name: str
    incident_type: str
    title: str
    description: str
    severity: Severity
    occurrence_count: int = Field(ge=1)
    recent_maintenance: list[str] = Field(default_factory=list)
    production_batch_no: str | None = None


class AgentOutput(AgentModel):
    summary: str = Field(min_length=1, max_length=1200)
    probable_causes: list[AgentCause] = Field(default_factory=list, max_length=8)
    recommended_actions: list[str] = Field(default_factory=list, max_length=10)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    risk_level: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_approval: bool

    @field_validator("recommended_actions", "missing_information")
    @classmethod
    def reject_blank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("items must not be blank")
        return value


class RuleDecision(AgentModel):
    final_severity: Severity
    requires_human_approval: bool
    rule_reasons: list[str]


class AnalysisRequest(BaseModel):
    force: bool = False


class InternalAnalysisRequest(AnalysisRequest):
    incident_id: int


class IncidentAnalysisRead(AgentModel):
    incident_id: int
    analysis_run_id: int
    provider: str
    model: str
    prompt_version: str
    fallback_used: bool
    final_severity: Severity
    requires_human_approval: bool
    agent_output: AgentOutput
    rule_reasons: list[str]
