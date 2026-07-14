from factory_hub.agent.schemas import AgentInput, AgentOutput
from factory_hub.domain.enums import Severity


class DemoAnalyzer:
    def analyze(self, payload: AgentInput) -> AgentOutput:
        text = f"{payload.incident_type} {payload.title} {payload.description}".lower()
        if "vibration" in text or "spindle" in text:
            return AgentOutput(
                summary="Spindle vibration exceeds the safe operating envelope and may indicate bearing or balance degradation.",
                probable_causes=[{"cause": "Spindle bearing wear", "evidence": "Vibration signal is above the configured danger threshold."}],
                recommended_actions=["Stop the affected machine", "Inspect spindle bearings and tool holder balance"],
                missing_information=["Latest vibration spectrum"],
                risk_level=Severity.P1,
                confidence=0.86,
                requires_human_approval=True,
            )
        if "temperature" in text or "temp" in text or "overheat" in text:
            return AgentOutput(
                summary="Temperature readings indicate a high-risk thermal abnormality.",
                probable_causes=[{"cause": "Cooling or lubrication degradation", "evidence": "Reported temperature is above the configured danger threshold."}],
                recommended_actions=["Reduce load", "Inspect cooling circuit and lubricant flow"],
                missing_information=["Ambient temperature and coolant flow rate"],
                risk_level=Severity.P1,
                confidence=0.84,
                requires_human_approval=True,
            )
        if "defect" in text or "vision" in text:
            return AgentOutput(
                summary="Vision inspection defect rate is elevated and may affect batch quality.",
                probable_causes=[{"cause": "Process drift or camera calibration issue", "evidence": "Defect rate exceeds the configured quality threshold."}],
                recommended_actions=["Hold suspect batch", "Check camera calibration and upstream process settings"],
                missing_information=["Sample images from recent rejects"],
                risk_level=Severity.P2,
                confidence=0.78,
                requires_human_approval=False,
            )
        if "alarm" in text:
            return AgentOutput(
                summary="General equipment alarm requires maintenance triage.",
                probable_causes=[{"cause": "Equipment subsystem warning", "evidence": "Alarm text does not match a high-risk deterministic threshold."}],
                recommended_actions=["Review machine alarm history", "Assign maintenance technician for inspection"],
                missing_information=["Machine alarm code"],
                risk_level=Severity.P3,
                confidence=0.72,
                requires_human_approval=False,
            )
        return AgentOutput(
            summary="Unknown incident type; manual review is recommended before automated action.",
            probable_causes=[{"cause": "Insufficient structured signal", "evidence": "No configured demo pattern matched the incident text."}],
            recommended_actions=["Collect additional operating context", "Route to production supervisor"],
            missing_information=["Sensor values and operator notes"],
            risk_level=Severity.P4,
            confidence=0.55,
            requires_human_approval=True,
        )
