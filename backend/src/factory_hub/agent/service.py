from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factory_hub.agent.adapter import OpenAICompatibleAdapter
from factory_hub.agent.demo import DemoAnalyzer
from factory_hub.agent.prompts import PROMPT_VERSION, build_messages
from factory_hub.agent.rules import RuleEngine
from factory_hub.agent.safety import sanitize_payload, sanitize_text
from factory_hub.agent.schemas import AgentInput, AgentOutput, IncidentAnalysisRead
from factory_hub.config import Settings
from factory_hub.domain.enums import ApprovalStatus, IncidentStatus
from factory_hub.domain.models import Approval, Equipment, Incident, IncidentAnalysisRun, MaintenanceRecord, ProductionBatch
from factory_hub.services.core import add_event, calculate_sla_due


async def build_agent_input(session: AsyncSession, incident: Incident) -> AgentInput:
    equipment = await session.get(Equipment, incident.equipment_id)
    if equipment is None:
        raise HTTPException(status_code=404, detail="equipment_not_found")
    batch_no: str | None = None
    if incident.production_batch_id:
        batch = await session.get(ProductionBatch, incident.production_batch_id)
        batch_no = batch.batch_no if batch else None
    maintenance = (
        await session.execute(
            select(MaintenanceRecord)
            .where(MaintenanceRecord.equipment_id == incident.equipment_id)
            .order_by(MaintenanceRecord.performed_at.desc())
            .limit(3)
        )
    ).scalars().all()
    return AgentInput(
        incident_id=incident.id,
        incident_no=incident.incident_no,
        equipment_code=equipment.code,
        equipment_name=equipment.name,
        incident_type=sanitize_text(incident.incident_type, 120),
        title=sanitize_text(incident.title, 240),
        description=sanitize_text(incident.description, 2000),
        severity=incident.severity,
        occurrence_count=incident.occurrence_count,
        recent_maintenance=[sanitize_text(item.summary, 300) for item in maintenance],
        production_batch_no=batch_no,
    )


def analysis_read_from_run(run: IncidentAnalysisRun) -> IncidentAnalysisRead:
    output = run.output_payload
    decision = output["rule_decision"]
    return IncidentAnalysisRead(
        incident_id=run.incident_id,
        analysis_run_id=run.id,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        fallback_used=run.fallback_used,
        final_severity=decision["final_severity"],
        requires_human_approval=decision["requires_human_approval"],
        agent_output=AgentOutput.model_validate(output["agent_output"]),
        rule_reasons=decision["rule_reasons"],
    )


async def _call_model_with_retry(settings: Settings, agent_input: AgentInput, llm_client: Any | None) -> tuple[AgentOutput, bool, str, int]:
    if settings.llm_demo_mode or not settings.llm_api_key:
        return DemoAnalyzer().analyze(agent_input), False, "demo", 0

    client = llm_client or OpenAICompatibleAdapter(settings)
    messages = build_messages(sanitize_payload(agent_input.model_dump(mode="json")))
    attempts = 0
    fallback_reason = ""
    for _ in range(2):
        attempts += 1
        try:
            raw = await client.complete_json(messages)
            return AgentOutput.model_validate(raw), False, "openai-compatible", attempts
        except (ValidationError, KeyError, ValueError, TypeError) as exc:
            fallback_reason = exc.__class__.__name__
            continue
        except TimeoutError as exc:
            fallback_reason = exc.__class__.__name__
            break
    output = DemoAnalyzer().analyze(agent_input)
    output.missing_information.append(f"fallback_reason:{fallback_reason or 'model_error'}")
    return output, True, "demo-fallback", attempts


async def ensure_pending_approval(session: AsyncSession, incident_id: int) -> None:
    existing = (
        await session.execute(select(Approval).where(Approval.incident_id == incident_id, Approval.status == ApprovalStatus.PENDING.value))
    ).scalar_one_or_none()
    if existing:
        return
    session.add(Approval(incident_id=incident_id, status=ApprovalStatus.PENDING.value, resume_url=None))
    await add_event(session, "APPROVAL_REQUIRED", incident_id=incident_id)


async def analyze_incident(
    session: AsyncSession,
    settings: Settings,
    incident_id: int,
    *,
    force: bool = False,
    llm_client: Any | None = None,
) -> IncidentAnalysisRead:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident_not_found")

    if not force:
        existing = (
            await session.execute(
                select(IncidentAnalysisRun)
                .where(IncidentAnalysisRun.incident_id == incident_id)
                .order_by(IncidentAnalysisRun.created_at.desc(), IncidentAnalysisRun.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing:
            return analysis_read_from_run(existing)

    started = perf_counter()
    agent_input = await build_agent_input(session, incident)
    agent_output, fallback_used, provider, attempts = await _call_model_with_retry(settings, agent_input, llm_client)
    decision = RuleEngine(settings).evaluate(agent_input, agent_output)

    incident.severity = decision.final_severity.value
    incident.sla_due_at = calculate_sla_due(settings, decision.final_severity, incident.first_seen_at)
    if decision.requires_human_approval:
        incident.status = IncidentStatus.AWAITING_APPROVAL.value
        await ensure_pending_approval(session, incident.id)
    elif incident.status == IncidentStatus.RECEIVED.value:
        incident.status = IncidentStatus.ANALYZING.value

    elapsed_ms = int((perf_counter() - started) * 1000)
    run = IncidentAnalysisRun(
        incident_id=incident.id,
        provider=provider,
        model=settings.llm_model if provider != "demo" else "demo-analyzer",
        prompt_version=PROMPT_VERSION,
        input_payload=sanitize_payload(agent_input.model_dump(mode="json")),
        output_payload={
            "agent_output": agent_output.model_dump(mode="json"),
            "rule_decision": decision.model_dump(mode="json"),
            "attempts": attempts,
        },
        fallback_used=fallback_used,
        elapsed_ms=elapsed_ms,
    )
    session.add(run)
    await session.flush()
    await add_event(
        session,
        "INCIDENT_ANALYZED",
        incident_id=incident.id,
        payload={"analysis_run_id": run.id, "final_severity": decision.final_severity.value, "fallback_used": fallback_used},
    )
    await session.commit()
    await session.refresh(run)
    return analysis_read_from_run(run)
