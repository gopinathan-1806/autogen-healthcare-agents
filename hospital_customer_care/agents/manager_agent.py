"""
Manager Agent

Central orchestrator responsible for:
  1. Validating whether the request is appropriate for the hospital care system.
  2. Identifying emergency / red-flag situations.
  3. Determining the correct medical department.
  4. Returning a structured ManagerDecision.

CRITICAL RULES:
  - Never diagnoses the patient.
  - Never prescribes medications.
  - Never orders tests.
  - LLM chooses the department; application validates against the allowlist.
  - Raw manager output is NEVER exposed to the patient.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from ..models.schemas import (
    Department,
    IntakeData,
    ManagerDecision,
    Priority,
    Status,
)
from ..services.model_client import get_model_client

logger = logging.getLogger(__name__)

_VALID_DEPARTMENTS = {d.value for d in Department}
_VALID_STATUSES = {s.value for s in Status}
_VALID_PRIORITIES = {p.value for p in Priority}

_MANAGER_SYSTEM_PROMPT = """You are the Manager Agent for CityMed Hospital's AI Customer Care System.

You receive:
1. A structured patient summary (intake data)
2. The patient's question / concern

YOUR RESPONSIBILITIES:
1. Determine if the request is appropriate for this hospital customer-care system.
2. Check for emergency or red-flag symptoms.
3. Identify the correct medical department.
4. Return a structured routing decision.

DEPARTMENT CODES:
- ORTHO:  Bones, joints, muscles, fractures, arthritis, sports injuries, musculoskeletal complaints
- NEURO:  Headaches, dizziness, neurological symptoms, nerve complaints, seizures, brain concerns
- NEPHRO: Kidney complaints, renal function, dialysis, kidney-related symptoms
- DENTAL: Teeth, gums, oral health, dental pain, dental procedures
- CARDIO: Heart concerns, blood pressure, cardiovascular symptoms, chest-related concerns

STATUS CODES:
- VALID:        Request is appropriate for this customer-care system.
- OUT_OF_SCOPE: Request is not related to medical / hospital care (e.g. booking a hotel, legal advice).
- EMERGENCY:    Patient describes potentially life-threatening symptoms.

PRIORITY CODES:
- NORMAL:    Routine consultation.
- URGENT:    Symptoms suggest early specialist review within days.
- EMERGENCY: Potentially life-threatening — must seek emergency care NOW.

EMERGENCY RED FLAGS (classify as EMERGENCY immediately):
- Sudden severe headache (worst of life)
- Loss of consciousness / unresponsive
- Severe chest pain or pressure
- Difficulty breathing / shortness of breath
- Signs of stroke: face drooping, arm weakness, speech difficulty
- Sudden severe weakness or paralysis
- Uncontrolled bleeding
- Seizure (no known history)
- Severe allergic reaction
- Suicidal thoughts or self-harm crisis
- Any other potentially life-threatening presentation

CRITICAL RULES:
- NEVER diagnose the patient.
- NEVER prescribe medications.
- NEVER order tests.
- If in any doubt about safety, classify as EMERGENCY.

REQUIRED OUTPUT FORMAT:
You MUST respond with a JSON block wrapped in <MANAGER_DECISION>...</MANAGER_DECISION> tags and nothing else outside those tags.

<MANAGER_DECISION>
{
  "department": "NEURO",
  "status": "VALID",
  "priority": "NORMAL",
  "reason": "Patient reports a one-sided headache for two days — appropriate for neurology."
}
</MANAGER_DECISION>

- department must be one of: ORTHO, NEURO, NEPHRO, DENTAL, CARDIO — or null if OUT_OF_SCOPE.
- status must be one of: VALID, OUT_OF_SCOPE, EMERGENCY.
- priority must be one of: NORMAL, URGENT, EMERGENCY.
- reason is a one-sentence explanation (internal use only, not shown to patient).
"""


class ManagerAgent:
    """
    Routes the patient request to the correct department.

    LLM selects the department; this class validates against the allowlist.
    """

    def __init__(self) -> None:
        self._model_client = get_model_client()
        self._agent = AssistantAgent(
            name="ManagerAgent",
            model_client=self._model_client,
            system_message=_MANAGER_SYSTEM_PROMPT,
            description="Routes patient complaints to the appropriate medical department.",
        )

    async def route(
        self,
        intake_data: IntakeData,
        user_question: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ManagerDecision:
        """
        Determine the correct department for the patient's concern.

        Returns a validated ManagerDecision. On failure, defaults to NEURO
        with URGENT priority so a safe fallback path is taken.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        task = (
            f"=== Patient Summary ===\n{intake_data.to_summary()}\n\n"
            f"=== Patient Question ===\n{user_question}\n\n"
            f"Analyse the above and return your routing decision."
        )

        logger.debug("[MANAGER] Routing request for complaint: %s", intake_data.complaint.symptom)

        try:
            result = await self._agent.run(task=task, cancellation_token=cancellation_token)
        except Exception as exc:
            logger.error("[MANAGER] Agent run failed: %s", exc)
            return ManagerDecision(
                status=Status.VALID,
                priority=Priority.NORMAL,
                reason="Routing agent error — defaulting to general review",
            )

        # Collect last assistant message
        response_text = ""
        for msg in reversed(result.messages):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                response_text = msg.content
                break

        decision = _parse_manager_decision(response_text)
        logger.info(
            "[MANAGER] Decision: dept=%s status=%s priority=%s",
            decision.department,
            decision.status,
            decision.priority,
        )
        return decision


def _parse_manager_decision(text: str) -> ManagerDecision:
    """Extract and validate the ManagerDecision JSON from agent output."""
    match = re.search(r"<MANAGER_DECISION>(.*?)</MANAGER_DECISION>", text, re.DOTALL)
    if not match:
        # Try extracting bare JSON block
        json_match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if json_match:
            raw = json_match.group(0)
        else:
            logger.warning("[MANAGER] No structured output found in: %.200s", text)
            return ManagerDecision(
                status=Status.VALID,
                priority=Priority.NORMAL,
                reason="Could not parse manager decision",
            )
    else:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("[MANAGER] JSON decode error: %s | raw: %.200s", exc, raw)
        return ManagerDecision(
            status=Status.VALID,
            priority=Priority.NORMAL,
            reason="JSON parsing error in manager output",
        )

    # Validate and sanitise fields against allowlists
    raw_dept = (data.get("department") or "").upper().strip()
    raw_status = (data.get("status") or "VALID").upper().strip()
    raw_priority = (data.get("priority") or "NORMAL").upper().strip()
    reason = str(data.get("reason", ""))[:500]  # Limit reason length

    department = Department(raw_dept) if raw_dept in _VALID_DEPARTMENTS else None
    status = Status(raw_status) if raw_status in _VALID_STATUSES else Status.VALID
    priority = Priority(raw_priority) if raw_priority in _VALID_PRIORITIES else Priority.NORMAL

    return ManagerDecision(
        department=department,
        status=status,
        priority=priority,
        reason=reason,
    )
