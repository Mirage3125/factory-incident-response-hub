from __future__ import annotations

import re

from factory_hub.agent.schemas import AgentInput, AgentOutput, RuleDecision
from factory_hub.config import Settings
from factory_hub.domain.enums import Severity


SEVERITY_RANK = {Severity.P1: 1, Severity.P2: 2, Severity.P3: 3, Severity.P4: 4}
RANK_SEVERITY = {rank: severity for severity, rank in SEVERITY_RANK.items()}


def more_severe(left: Severity, right: Severity) -> Severity:
    return left if SEVERITY_RANK[left] <= SEVERITY_RANK[right] else right


def escalate(severity: Severity, steps: int = 1) -> Severity:
    return RANK_SEVERITY[max(1, SEVERITY_RANK[severity] - steps)]


def extract_metric(text: str, names: tuple[str, ...]) -> float | None:
    for name in names:
        pattern = re.compile(rf"(?i)\b{re.escape(name)}\b\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)")
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


class RuleEngine:
    def __init__(self, settings: Settings):
        self.settings = settings

    def evaluate(self, payload: AgentInput, agent_output: AgentOutput) -> RuleDecision:
        text = f"{payload.incident_type} {payload.title} {payload.description}".lower()
        final = agent_output.risk_level
        reasons: list[str] = []

        vibration = extract_metric(text, ("vibration", "vibration_mm_s"))
        if ("vibration" in text or "spindle" in text) and vibration is not None and vibration >= self.settings.vibration_p1_threshold:
            final = Severity.P1
            reasons.append(f"vibration_threshold_p1:{vibration:g}>={self.settings.vibration_p1_threshold:g}")

        temperature = extract_metric(text, ("temperature", "temp"))
        if ("temperature" in text or "temp" in text) and temperature is not None and temperature >= self.settings.temperature_p1_threshold:
            final = Severity.P1
            reasons.append(f"temperature_threshold_p1:{temperature:g}>={self.settings.temperature_p1_threshold:g}")

        defect_rate = extract_metric(text, ("defect_rate", "defect rate", "defects"))
        if ("defect" in text or "vision" in text) and defect_rate is not None and defect_rate >= self.settings.defect_rate_p2_threshold:
            final = more_severe(final, Severity.P2)
            reasons.append(f"defect_rate_threshold_p2:{defect_rate:g}>={self.settings.defect_rate_p2_threshold:g}")

        if payload.occurrence_count >= self.settings.repeat_escalation_count:
            escalated = escalate(final)
            if escalated != final:
                final = escalated
                reasons.append(f"repeat_escalation:occurrence_count={payload.occurrence_count}")

        requires_review = agent_output.requires_human_approval
        if agent_output.confidence < self.settings.low_confidence_threshold:
            requires_review = True
            reasons.append(f"low_confidence:{agent_output.confidence:.2f}<{self.settings.low_confidence_threshold:.2f}")

        if final == Severity.P1:
            requires_review = True
            reasons.append("p1_requires_human_approval")

        return RuleDecision(final_severity=final, requires_human_approval=requires_review, rule_reasons=reasons)
