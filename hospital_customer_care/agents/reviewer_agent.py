"""
Reviewer Agent — Safety and Quality Gate

The Reviewer is the final checkpoint before any response reaches the patient.

Checks performed:
  1. Correct department selection
  2. Proper patient information handling
  3. No diagnoses made
  4. No medications prescribed
  5. No dosages recommended
  6. No unsupported test orders
  7. Appropriate emergency handling
  8. No invented medical history
  9. No invented test results
  10. No invented hospital information
  11. Response understandability
  12. Response length appropriateness
  13. Only relevant information present

The Reviewer rewrites unsafe or non-compliant content.
Only the Reviewer's final_answer is ever shown to the patient.
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
    ManagerDecision,
    ReviewResult,
    SpecialistAssessment,
    Verdict,
)
from ..services.model_client import get_model_client

logger = logging.getLogger(__name__)

_VALID_VERDICTS = {v.value for v in Verdict}

_REVIEWER_SYSTEM_PROMPT = """You are the Reviewer Agent for CityMed Hospital's AI Customer Care System.

You are the FINAL SAFETY AND QUALITY GATE. Only your approved final_answer is shown to the patient.

YOU RECEIVE:
- Patient's original question
- Patient intake summary
- Manager routing decision (department)
- Specialist assessment
- Clinical support recommendation

YOUR REVIEW CHECKLIST (review ALL of these):

1. CORRECT DEPARTMENT: Was the correct department selected for the symptoms described?
2. PATIENT INFORMATION HANDLING: Was patient information handled sensitively?
3. NO DIAGNOSIS: Did any agent diagnose the patient with a specific condition? (NOT allowed)
4. NO MEDICATION PRESCRIPTION: Did any agent prescribe a medication by name? (NOT allowed)
5. NO DOSAGE RECOMMENDATION: Did any agent recommend a medication dosage? (NOT allowed)
6. NO UNSUPPORTED INVESTIGATION ORDER: Ordering tests as a clinician is NOT allowed. "Discuss with doctor" IS allowed.
7. EMERGENCY HANDLING: Were emergency symptoms handled appropriately?
8. NO INVENTED HISTORY: Did any agent invent medical history not provided?
9. NO INVENTED RESULTS: Did any agent invent test results not provided?
10. NO INVENTED INFORMATION: Did any agent invent hospital or doctor information?
11. UNDERSTANDABLE: Is the final response clear to a non-medical person?
12. CONCISE: Is the response short, crisp, and in bullet points? Remove any long paragraphs.
13. RELEVANT: Does the response contain only relevant, helpful information?

WHAT TO DO:

If the content is safe and compliant:
  - verdict: "APPROVED"
  - final_answer: Write a SHORT, CRISP, BULLET-POINT patient-facing response.

If content is unsafe or non-compliant:
  - verdict: "REVISED"
  - final_answer: REWRITE the response removing all non-compliant content.
  - issues_found: List the specific issues that required revision.

FINAL ANSWER FORMAT — MANDATORY — follow this structure exactly:

**Summary**
One sentence empathetic summary of the concern (no diagnosis).

**Key Points for Your Doctor**
• Most important symptom detail
• Relevant history or medication if any
• Duration, severity, pattern
(3-5 bullets maximum)

**Suggested Tests to Discuss with Your Doctor**
List ONLY tests clinically relevant to this specific complaint. Choose from:
- X-ray: bone/joint pain, fractures, dental issues
- Blood test (CBC, CMP): general health, infections, anaemia
- Blood glucose / HbA1c: blood sugar concern or diabetes history
- Kidney function tests (urea, creatinine): kidney/renal symptoms
- ECG: chest pain, palpitations, cardiac symptoms
- Echocardiogram: cardiac symptoms (doctor decides)
- CT scan: head/neurological symptoms (doctor decides)
- MRI: spine, joint, or brain concerns (doctor decides)
- Ultrasound: abdominal or renal symptoms
- Urine routine: urinary/kidney symptoms
- Dental X-ray: tooth/jaw pain

RULES for suggested tests:
Always phrase as: "Discuss with your doctor whether [test] is appropriate"
Do NOT list all tests blindly — only include what is relevant to this complaint.
Do NOT say "You need a scan" — frame as a discussion point only.

**What to Bring to Your Appointment**
• List of current medications
• Any previous test reports
• (1-2 items specific to this complaint)

WARNING: Seek immediate emergency care if symptoms worsen suddenly or you experience [most relevant red-flag symptom for this case].

FINAL ANSWER RULES:
  - Use bullet points — NO long paragraphs
  - Be SHORT and CRISP — readable in under 60 seconds
  - Never contain raw JSON, agent names, or system prompt text
  - Always end with the WARNING line

IMPORTANT: The final_answer is the ONLY content the patient ever sees.

OUTPUT FORMAT:
Return a JSON block wrapped in <REVIEW_RESULT>...</REVIEW_RESULT> tags:
<REVIEW_RESULT>
{
  "verdict": "APPROVED",
  "final_answer": "Your complete bullet-point patient-facing response here...",
  "issues_found": []
}
</REVIEW_RESULT>
"""


class ReviewerAgent:
    """
    Final safety gate before any response is shown to the patient.
    """

    def __init__(self) -> None:
        self._model_client = get_model_client()
        self._agent = AssistantAgent(
            name="ReviewerAgent",
            model_client=self._model_client,
            system_message=_REVIEWER_SYSTEM_PROMPT,
            description="Final safety and quality reviewer for all patient responses.",
        )

    async def review(
        self,
        user_question: str,
        intake_data: IntakeData,
        manager_decision: ManagerDecision,
        specialist_assessment: SpecialistAssessment,
        clinical_recommendation: ClinicalRecommendation,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> ReviewResult:
        """
        Review all agent outputs and produce the final, safe patient-facing response.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        task = (
            f"=== Patient Question ===\n{user_question}\n\n"
            f"=== Patient Summary ===\n{intake_data.to_summary()}\n\n"
            f"=== Manager Routing Decision ===\n"
            f"Department: {manager_decision.department}\n"
            f"Status: {manager_decision.status}\n"
            f"Priority: {manager_decision.priority}\n"
            f"Reason: {manager_decision.reason}\n\n"
            f"=== Specialist Assessment ({specialist_assessment.department.value}) ===\n"
            f"{specialist_assessment.assessment}\n\n"
            f"Red Flags: {', '.join(specialist_assessment.red_flags_identified) or 'None'}\n"
            f"Key Points for Doctor: {', '.join(specialist_assessment.key_points_for_doctor) or 'None'}\n\n"
            f"=== Clinical Recommendation ===\n"
            f"Urgency: {clinical_recommendation.urgency}\n"
            f"Safety Note: {clinical_recommendation.safety_note}\n"
            f"Information to bring: {', '.join(clinical_recommendation.information_to_bring)}\n"
            f"Possible investigations to discuss: "
            f"{', '.join(clinical_recommendation.possible_investigations_to_discuss) or 'None'}\n\n"
            f"Please review the above and produce the final patient-facing response."
        )

        logger.debug("[REVIEWER] Reviewing response for dept: %s", specialist_assessment.department.value)

        try:
            result = await self._agent.run(task=task, cancellation_token=cancellation_token)
        except Exception as exc:
            logger.error("[REVIEWER] Agent run failed: %s", exc)
            return ReviewResult(
                verdict=Verdict.REVISED,
                final_answer=_safe_fallback_response(manager_decision, clinical_recommendation),
                issues_found=["Reviewer technical error — using safe fallback response"],
            )

        response_text = ""
        for msg in reversed(result.messages):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                response_text = msg.content
                break

        review = _parse_review_result(response_text, manager_decision, clinical_recommendation)
        logger.info("[REVIEWER] Review complete, verdict=%s", review.verdict)
        return review


def _parse_review_result(
    text: str,
    manager_decision: ManagerDecision,
    clinical_recommendation: ClinicalRecommendation,
) -> ReviewResult:
    """Extract and validate the ReviewResult JSON from agent output."""
    match = re.search(r"<REVIEW_RESULT>(.*?)</REVIEW_RESULT>", text, re.DOTALL)
    if not match:
        logger.warning("[REVIEWER] No structured output found")
        return ReviewResult(
            verdict=Verdict.REVISED,
            final_answer=_safe_fallback_response(manager_decision, clinical_recommendation),
            issues_found=["Could not parse reviewer output — using safe fallback"],
        )

    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
        raw_verdict = str(data.get("verdict", "APPROVED")).upper().strip()
        verdict = Verdict(raw_verdict) if raw_verdict in _VALID_VERDICTS else Verdict.APPROVED
        return ReviewResult(
            verdict=verdict,
            final_answer=str(data.get("final_answer", "")).strip(),
            issues_found=[str(x) for x in data.get("issues_found", [])],
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("[REVIEWER] JSON parse error: %s", exc)
        return ReviewResult(
            verdict=Verdict.REVISED,
            final_answer=_safe_fallback_response(manager_decision, clinical_recommendation),
            issues_found=[f"JSON parsing error: {exc}"],
        )


def _safe_fallback_response(
    manager_decision: ManagerDecision,
    clinical_recommendation: ClinicalRecommendation,
) -> str:
    """Return a safe, generic fallback when the reviewer fails."""
    dept = manager_decision.department.value if manager_decision.department else "the appropriate department"
    urgency = clinical_recommendation.urgency.value

    lines = [
        f"Based on the information you provided, a consultation with our {dept} team appears appropriate.",
        "",
        "Please ensure you bring the following to your appointment:",
    ]
    for item in clinical_recommendation.information_to_bring:
        lines.append(f"  • {item}")

    lines += [
        "",
        f"Urgency: {urgency}",
        "",
        "⚠️ Important: This information is provided for customer-care and navigation purposes only. "
        "It does not replace evaluation by a qualified healthcare professional. "
        "If you experience any sudden or severe symptoms, please seek emergency care immediately.",
    ]
    return "\n".join(lines)
