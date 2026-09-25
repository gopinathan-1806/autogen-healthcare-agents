"""
Clinical Support Agent

Converts the specialist assessment into a clinician-reviewable next-step plan.

CRITICAL RULES:
  - Does NOT independently order tests.
  - May only identify investigations that the patient CAN DISCUSS with the doctor.
  - Never fabricates reasons for investigations.
  - Never recommends all tests blindly.
  - Urgency classification is based only on presented information.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken

from ..models.schemas import (
    ClinicalRecommendation,
    IntakeData,
    SpecialistAssessment,
    Urgency,
)
from ..services.model_client import get_model_client

logger = logging.getLogger(__name__)

_CLINICAL_SUPPORT_SYSTEM_PROMPT = """You are the Clinical Support Agent for CityMed Hospital's AI Customer Care system.

Your role is to convert the specialist's assessment into a structured, clinician-reviewable next-step plan for the patient.

You receive:
1. Patient intake summary
2. Specialist assessment
3. Red flags and key points identified by the specialist

YOUR RESPONSIBILITIES:
1. Summarise what kind of consultation is being recommended.
2. List information / documents the patient should bring to the appointment.
3. Identify POSSIBLE investigations that the patient may DISCUSS with their doctor — but only when clinically relevant.
4. Classify urgency of the consultation.
5. Add a brief safety note if relevant.

CRITICAL RULES:
1. NEVER independently prescribe or order investigations.
2. NEVER say "You need an X-ray" or "Get a CT scan" — always frame as "Your doctor may consider..."
3. NEVER recommend an investigation without a clinical reason from the patient's history.
4. NEVER recommend all investigations blindly.
5. NEVER fabricate clinical reasons for investigations.
6. NEVER diagnose.
7. NEVER prescribe medications.
8. NEVER invent medical history.
9. If red flags are present, set urgency to URGENT or EMERGENCY.

VALID INVESTIGATIONS TO POTENTIALLY DISCUSS (only when clinically relevant):
- Complete Blood Count (CBC)
- Fasting blood glucose / HbA1c (if diabetes history or concern)
- Kidney function tests (urea, creatinine) — for nephrology or relevant symptoms
- Liver function tests — if clinically relevant
- Thyroid function tests — if clinically relevant
- X-ray — for bone/joint symptoms
- CT scan — for neurological or trauma concerns (doctor decides)
- MRI — for neurological, spine, or soft tissue concerns (doctor decides)
- Ultrasound — for abdominal or renal symptoms
- ECG — for cardiac symptoms
- Echocardiogram — for cardiac symptoms (doctor decides)
- Urine routine examination — for urinary or kidney symptoms
- HbA1c — for blood sugar concerns

URGENCY LEVELS:
- ROUTINE:   Stable symptoms, no red flags — schedule at convenience
- SOON:      Symptoms warrant attention within a few days
- URGENT:    Symptoms require prompt specialist review (within 24-48 hours)
- EMERGENCY: Potentially life-threatening — seek emergency care immediately

OUTPUT FORMAT:
Return a JSON block wrapped in <CLINICAL_RECOMMENDATION>...</CLINICAL_RECOMMENDATION> tags:
<CLINICAL_RECOMMENDATION>
{
  "consultation": {
    "department": "NEURO",
    "reason": "One-sided headache for two days with photophobia"
  },
  "possible_investigations_to_discuss": [
    "Discuss with your doctor whether blood pressure monitoring is appropriate",
    "Your doctor may consider blood glucose testing given your history of elevated blood sugar"
  ],
  "information_to_bring": [
    "List of current medications",
    "Any previous blood pressure readings",
    "Previous neurological investigation reports if available"
  ],
  "urgency": "ROUTINE",
  "safety_note": "If your headache suddenly becomes much worse, or you develop vision changes, weakness, or difficulty speaking, please seek emergency care immediately."
}
</CLINICAL_RECOMMENDATION>
"""

_VALID_URGENCIES = {u.value for u in Urgency}


class ClinicalSupportAgent:
    """
    Converts specialist assessment to a structured consultation recommendation.
    """

    def __init__(self) -> None:
        self._model_client = get_model_client()
        self._agent = AssistantAgent(
            name="ClinicalSupportAgent",
            model_client=self._model_client,
            system_message=_CLINICAL_SUPPORT_SYSTEM_PROMPT,
            description="Creates clinician-reviewable next-step plans from specialist assessments.",
        )

    async def generate_recommendation(
        self,
        intake_data: IntakeData,
        specialist_assessment: SpecialistAssessment,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ClinicalRecommendation:
        """
        Generate a clinical next-step recommendation from the specialist assessment.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        task = (
            f"=== Patient Summary ===\n{intake_data.to_summary()}\n\n"
            f"=== Specialist Assessment ({specialist_assessment.department.value}) ===\n"
            f"{specialist_assessment.assessment}\n\n"
            f"=== Red Flags Identified ===\n"
            f"{chr(10).join('- ' + r for r in specialist_assessment.red_flags_identified) or 'None identified'}\n\n"
            f"=== Key Points for Doctor ===\n"
            f"{chr(10).join('- ' + p for p in specialist_assessment.key_points_for_doctor) or 'None listed'}\n\n"
            f"=== Information Gaps ===\n"
            f"{chr(10).join('- ' + g for g in specialist_assessment.information_gaps) or 'None identified'}\n\n"
            f"Please generate the clinical next-step recommendation."
        )

        logger.debug("[CLINICAL_SUPPORT] Generating recommendation for dept: %s",
                     specialist_assessment.department.value)

        try:
            result = await self._agent.run(task=task, cancellation_token=cancellation_token)
        except Exception as exc:
            logger.error("[CLINICAL_SUPPORT] Agent run failed: %s", exc)
            return _fallback_recommendation(specialist_assessment)

        response_text = ""
        for msg in reversed(result.messages):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                response_text = msg.content
                break

        recommendation = _parse_clinical_recommendation(response_text, specialist_assessment)
        logger.info("[CLINICAL_SUPPORT] Recommendation generated, urgency=%s", recommendation.urgency)
        return recommendation


def _parse_clinical_recommendation(
    text: str,
    specialist_assessment: SpecialistAssessment,
) -> ClinicalRecommendation:
    """Extract and validate the ClinicalRecommendation JSON from agent output."""
    match = re.search(r"<CLINICAL_RECOMMENDATION>(.*?)</CLINICAL_RECOMMENDATION>", text, re.DOTALL)
    if not match:
        logger.warning("[CLINICAL_SUPPORT] No structured output found in response")
        return _fallback_recommendation(specialist_assessment)

    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
        raw_urgency = str(data.get("urgency", "ROUTINE")).upper().strip()
        urgency = Urgency(raw_urgency) if raw_urgency in _VALID_URGENCIES else Urgency.ROUTINE

        # Escalate urgency if red flags were identified by specialist
        if specialist_assessment.red_flags_identified and urgency == Urgency.ROUTINE:
            urgency = Urgency.URGENT

        return ClinicalRecommendation(
            consultation=data.get("consultation", {}),
            possible_investigations_to_discuss=[
                str(x) for x in data.get("possible_investigations_to_discuss", [])
            ],
            information_to_bring=[
                str(x) for x in data.get("information_to_bring", [])
            ],
            urgency=urgency,
            safety_note=str(data.get("safety_note", "")),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("[CLINICAL_SUPPORT] JSON parse error: %s", exc)
        return _fallback_recommendation(specialist_assessment)


def _fallback_recommendation(specialist_assessment: SpecialistAssessment) -> ClinicalRecommendation:
    """Return a safe fallback recommendation when parsing fails."""
    return ClinicalRecommendation(
        consultation={
            "department": specialist_assessment.department.value,
            "reason": "Specialist consultation recommended",
        },
        possible_investigations_to_discuss=[],
        information_to_bring=[
            "List of current medications",
            "Previous medical reports if available",
            "List of known allergies",
        ],
        urgency=Urgency.SOON if specialist_assessment.red_flags_identified else Urgency.ROUTINE,
        safety_note=(
            "If your symptoms worsen suddenly or you experience severe symptoms, "
            "please seek emergency care immediately."
        ),
    )
