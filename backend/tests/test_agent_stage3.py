import asyncio

import pytest
from sqlalchemy import func, select

from factory_hub.agent.demo import DemoAnalyzer
from factory_hub.agent.rules import RuleEngine
from factory_hub.agent.safety import sanitize_text
from factory_hub.agent.schemas import AgentInput, AgentOutput
from factory_hub.agent.service import analyze_incident
from factory_hub.config import get_settings
from factory_hub.domain.enums import ApprovalStatus, IncidentStatus, Severity
from factory_hub.domain.models import Approval, IncidentAnalysisRun


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete_json(self, messages):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def make_agent_input(**overrides) -> AgentInput:
    data = {
        "incident_id": 1,
        "incident_no": "INC-TEST",
        "equipment_code": "CNC-01",
        "equipment_name": "Main spindle CNC",
        "incident_type": "vibration",
        "title": "Spindle vibration high",
        "description": "vibration=9.8 mm/s",
        "severity": Severity.P2,
        "occurrence_count": 1,
        "recent_maintenance": [],
        "production_batch_no": "BATCH-1",
    }
    data.update(overrides)
    return AgentInput.model_validate(data)


def valid_output(**overrides) -> dict:
    data = {
        "summary": "The spindle vibration is above the danger threshold.",
        "probable_causes": [{"cause": "Bearing wear", "evidence": "vibration=9.8 mm/s"}],
        "recommended_actions": ["Stop machine and inspect spindle bearings"],
        "missing_information": [],
        "risk_level": "P2",
        "confidence": 0.82,
        "requires_human_approval": False,
    }
    data.update(overrides)
    return data


def test_agent_schema_validation_rejects_bad_confidence():
    with pytest.raises(ValueError):
        AgentOutput.model_validate(valid_output(confidence=1.5))


def test_demo_analyzer_is_deterministic():
    analyzer = DemoAnalyzer()
    payload = make_agent_input()
    first = analyzer.analyze(payload)
    second = analyzer.analyze(payload)
    assert first == second
    assert first.risk_level == Severity.P1
    assert first.requires_human_approval is True


def test_sensitive_text_is_redacted():
    text = "token=abc123 password=hunter2 resume_url=http://n8n/resume/secret sk-live-secret"
    cleaned = sanitize_text(text)
    assert "abc123" not in cleaned
    assert "hunter2" not in cleaned
    assert "resume/secret" not in cleaned
    assert "sk-live-secret" not in cleaned
    assert "[REDACTED]" in cleaned


def test_rule_engine_p1_threshold_cannot_be_downgraded():
    settings = get_settings()
    decision = RuleEngine(settings).evaluate(
        make_agent_input(description="vibration=10.1 mm/s"),
        AgentOutput.model_validate(valid_output(risk_level="P4", confidence=0.9)),
    )
    assert decision.final_severity == Severity.P1
    assert decision.requires_human_approval is True
    assert any("vibration" in reason for reason in decision.rule_reasons)


def test_rule_engine_temperature_defect_repeat_and_low_confidence():
    settings = get_settings()
    engine = RuleEngine(settings)
    temp = engine.evaluate(
        make_agent_input(incident_type="temperature", title="temperature high", description="temperature=96 C"),
        AgentOutput.model_validate(valid_output(risk_level="P3", confidence=0.9)),
    )
    defect = engine.evaluate(
        make_agent_input(incident_type="defect_rate", title="vision defects", description="defect_rate=7.2%"),
        AgentOutput.model_validate(valid_output(risk_level="P3", confidence=0.9)),
    )
    repeated = engine.evaluate(
        make_agent_input(occurrence_count=3, description="general equipment alarm"),
        AgentOutput.model_validate(valid_output(risk_level="P3", confidence=0.9)),
    )
    low_confidence = engine.evaluate(
        make_agent_input(description="unknown intermittent alarm"),
        AgentOutput.model_validate(valid_output(risk_level="P4", confidence=0.4)),
    )
    assert temp.final_severity == Severity.P1
    assert temp.requires_human_approval is True
    assert defect.final_severity == Severity.P2
    assert repeated.final_severity == Severity.P2
    assert low_confidence.requires_human_approval is True


@pytest.mark.asyncio
async def test_service_retries_invalid_model_response_then_uses_valid_response(api_client, db_session):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-01",
            "incident_type": "agent-retry",
            "title": "Retry validation",
            "description": "general equipment alarm",
            "severity": "P3",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = created.json()["incident"]["id"]
    result = await analyze_incident(
        db_session,
        get_settings().model_copy(update={"llm_demo_mode": False, "llm_api_key": "test-key"}),
        incident_id,
        llm_client=FakeLLMClient([{"not": "valid"}, valid_output(risk_level="P3", confidence=0.9)]),
    )
    assert result.fallback_used is False
    assert result.agent_output.risk_level == Severity.P3


@pytest.mark.asyncio
async def test_service_falls_back_after_second_invalid_response(api_client, db_session):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-01",
            "incident_type": "agent-fallback",
            "title": "Fallback vibration",
            "description": "vibration=10.0 mm/s",
            "severity": "P2",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = created.json()["incident"]["id"]
    result = await analyze_incident(
        db_session,
        get_settings().model_copy(update={"llm_demo_mode": False, "llm_api_key": "test-key"}),
        incident_id,
        llm_client=FakeLLMClient([{"bad": "shape"}, {"still": "bad"}]),
    )
    assert result.fallback_used is True
    assert result.final_severity == Severity.P1


@pytest.mark.asyncio
async def test_service_falls_back_on_timeout(api_client, db_session):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-02",
            "incident_type": "agent-timeout",
            "title": "Timeout alarm",
            "description": "unknown intermittent alarm",
            "severity": "P4",
        },
    )
    incident_id = created.json()["incident"]["id"]
    result = await analyze_incident(
        db_session,
        get_settings().model_copy(update={"llm_demo_mode": False, "llm_api_key": "test-key"}),
        incident_id,
        llm_client=FakeLLMClient([asyncio.TimeoutError()]),
    )
    assert result.fallback_used is True


@pytest.mark.asyncio
async def test_public_analyze_api_updates_incident_and_creates_audit_without_duplicate(api_client, db_session):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "CNC-01",
            "incident_type": "stage3-vibration",
            "title": "Spindle vibration high",
            "description": "vibration=9.8 mm/s token=secret-value",
            "severity": "P2",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = created.json()["incident"]["id"]
    analyzed = await api_client.post(f"/api/incidents/{incident_id}/analyze")
    body = analyzed.json()
    assert analyzed.status_code == 200
    assert body["final_severity"] == "P1"
    assert body["requires_human_approval"] is True
    assert body["fallback_used"] is False

    detail = await api_client.get(f"/api/incidents/{incident_id}")
    assert detail.json()["severity"] == "P1"
    assert detail.json()["status"] == IncidentStatus.AWAITING_APPROVAL.value

    repeated = await api_client.post(f"/api/incidents/{incident_id}/analyze")
    assert repeated.json()["analysis_run_id"] == body["analysis_run_id"]

    run_count = (await db_session.execute(select(func.count()).select_from(IncidentAnalysisRun).where(IncidentAnalysisRun.incident_id == incident_id))).scalar_one()
    assert run_count == 1

    approval = (await db_session.execute(select(Approval).where(Approval.incident_id == incident_id))).scalar_one()
    assert approval.status == ApprovalStatus.PENDING.value
    assert approval.resume_url is None

    run = (await db_session.execute(select(IncidentAnalysisRun).where(IncidentAnalysisRun.incident_id == incident_id))).scalar_one()
    assert "secret-value" not in str(run.input_payload)


@pytest.mark.asyncio
async def test_internal_agent_analyze_requires_token_and_visual_defect_is_p2(api_client, internal_token):
    created = await api_client.post(
        "/api/incidents",
        json={
            "equipment_code": "VISION-01",
            "incident_type": "defect_rate",
            "title": "Vision defect rate increased",
            "description": "defect_rate=6.5%",
            "severity": "P3",
            "production_batch_no": "BATCH-20260714-001",
        },
    )
    incident_id = created.json()["incident"]["id"]
    denied = await api_client.post("/api/internal/agent/analyze", json={"incident_id": incident_id})
    assert denied.status_code == 401
    allowed = await api_client.post(
        "/api/internal/agent/analyze",
        headers={"X-Internal-Token": internal_token},
        json={"incident_id": incident_id},
    )
    assert allowed.status_code == 200
    assert allowed.json()["final_severity"] == "P2"
