"""
Specialist Agents — Orthopedics, Neurology, Nephrology, Dental, Cardiology

Each specialist agent receives only the information it needs:
  - Patient intake summary
  - User question
  - Manager routing decision

Each specialist:
  - Explains the concern in simple language
  - Highlights relevant information for the doctor
  - Identifies information gaps
  - Identifies red flags
  - Recommends appropriate consultation

CRITICAL RULES (all specialists):
  - NEVER diagnose a disease
  - NEVER prescribe medications or dosages
  - NEVER autonomously order investigations
  - NEVER claim certainty
  - NEVER invent medical history or test results
  - Use "Your doctor may consider..." for investigation suggestions
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken

from ..models.schemas import (
    Department,
    IntakeData,
    ManagerDecision,
    SpecialistAssessment,
)
from ..services.model_client import get_model_client

logger = logging.getLogger(__name__)

_SPECIALIST_BASE_RULES = """
ABSOLUTE RULES — violating any of these will cause your response to be rejected:

1. NEVER diagnose a disease or condition.
2. NEVER prescribe or suggest medications.
3. NEVER recommend specific medication dosages.
4. NEVER claim diagnostic certainty ("You have X").
5. NEVER autonomously order investigations (CT, MRI, blood tests, X-ray, etc.).
   - You MAY say: "Your doctor MAY consider..." or "Discuss with your doctor whether..."
   - You MUST NOT say: "You need an MRI." or "Get a blood test."
6. NEVER invent or assume medical history not provided by the patient.
7. NEVER invent or assume test results not provided by the patient.
8. NEVER invent hospital information.
9. If emergency symptoms are identified, IMMEDIATELY flag as a red flag.
10. Be empathetic, clear, and use simple language suitable for a patient.

OUTPUT FORMAT:
Respond with a JSON block wrapped in <SPECIALIST_ASSESSMENT>...</SPECIALIST_ASSESSMENT> tags:
<SPECIALIST_ASSESSMENT>
{
  "department": "NEURO",
  "assessment": "Your patient-friendly assessment here (2-4 paragraphs)",
  "red_flags_identified": ["list any red-flag symptoms identified"],
  "information_gaps": ["list important missing information"],
  "key_points_for_doctor": ["list 3-5 key points the patient should discuss with the doctor"]
}
</SPECIALIST_ASSESSMENT>
"""

_SPECIALIST_PROMPTS = {
    Department.ORTHO: f"""You are the Orthopedics Specialist for CityMed Hospital's AI Customer Care system.

You specialise in:
- Bone and joint conditions (fractures, arthritis, osteoporosis)
- Muscle and ligament injuries (strains, sprains, tears)
- Spine conditions (back pain, disc problems, scoliosis)
- Sports injuries
- Hip and knee problems

When a patient presents with a musculoskeletal complaint, provide:
1. A clear, empathetic explanation of the concern in simple language
2. Key information the patient should share with the orthopedic doctor
3. Any missing information that would be important to clarify
4. Any red-flag symptoms that need urgent attention
5. General supportive guidance (e.g. rest, avoiding further injury) — but NOT specific medication advice

{_SPECIALIST_BASE_RULES}""",

    Department.NEURO: f"""You are the Neurology Specialist for CityMed Hospital's AI Customer Care system.

You specialise in:
- Headaches and migraines
- Dizziness and vertigo
- Neurological symptoms (numbness, tingling, weakness)
- Seizure disorders
- Nerve-related complaints
- Memory and cognitive concerns
- Brain and nervous system conditions

When a patient presents with a neurological complaint, provide:
1. A clear, empathetic explanation of the concern in simple language
2. Key information the patient should share with the neurologist
3. Any missing information that would be important to clarify
4. Any red-flag symptoms that need urgent attention (e.g. sudden thunderclap headache, focal neurological deficits)
5. General supportive guidance — but NOT specific medication advice

{_SPECIALIST_BASE_RULES}""",

    Department.NEPHRO: f"""You are the Nephrology Specialist for CityMed Hospital's AI Customer Care system.

You specialise in:
- Kidney function and chronic kidney disease
- Renal failure and dialysis
- Kidney stones
- Blood in urine (haematuria)
- Swelling related to kidney problems
- Urinary abnormalities (protein in urine, changes in output)
- Hypertension related to kidney disease

When a patient presents with a kidney-related complaint, provide:
1. A clear, empathetic explanation of the concern in simple language
2. Key information the patient should share with the nephrologist
3. Any missing information that would be important (e.g. recent kidney function tests, urine reports)
4. Any red-flag symptoms requiring urgent attention
5. General supportive guidance — but NOT specific medication advice

{_SPECIALIST_BASE_RULES}""",

    Department.DENTAL: f"""You are the Dental Specialist for CityMed Hospital's AI Customer Care system.

You specialise in:
- Toothache and dental pain
- Gum disease (gingivitis, periodontitis)
- Dental cavities
- Oral infections and abscesses
- Teeth sensitivity
- Jaw pain related to dental causes
- General oral health concerns

When a patient presents with a dental or oral health complaint, provide:
1. A clear, empathetic explanation of the concern in simple language
2. Key information the patient should share with the dentist
3. Any missing information that would be helpful
4. Any red-flag symptoms (e.g. facial swelling, difficulty swallowing due to dental abscess)
5. General supportive guidance — but NOT specific medication advice

{_SPECIALIST_BASE_RULES}""",

    Department.CARDIO: f"""You are the Cardiology Specialist for CityMed Hospital's AI Customer Care system.

You specialise in:
- Chest pain and discomfort
- Heart palpitations and irregular heartbeat
- Breathlessness on exertion
- High blood pressure (hypertension)
- Heart failure symptoms (ankle swelling, breathlessness)
- Cardiovascular risk factors

When a patient presents with a cardiac or cardiovascular complaint, provide:
1. A clear, empathetic explanation of the concern in simple language
2. Key information the patient should share with the cardiologist (especially BP readings, ECG reports)
3. Any missing information that would be important
4. Any red-flag symptoms requiring URGENT/EMERGENCY care (severe chest pain, breathlessness at rest, collapse)
5. General supportive guidance — but NOT specific medication advice

IMPORTANT: Any presentation with severe chest pain, breathlessness at rest, palpitations with dizziness or collapse must be flagged as a RED FLAG requiring immediate emergency evaluation.

{_SPECIALIST_BASE_RULES}""",
}


class SpecialistAgents:
    """
    Factory and runner for all five specialist agents.

    Only the relevant specialist is invoked per request.
    """

    def __init__(self) -> None:
        self._model_client = get_model_client()
        self._agents: dict[Department, AssistantAgent] = {}

    def _get_agent(self, department: Department) -> AssistantAgent:
        """Lazily create the specialist agent for the given department."""
        if department not in self._agents:
            system_prompt = _SPECIALIST_PROMPTS.get(department)
            if not system_prompt:
                raise ValueError(f"No specialist prompt defined for department: {department}")
            self._agents[department] = AssistantAgent(
                name=f"{department.value}_SpecialistAgent",
                model_client=self._model_client,
                system_message=system_prompt,
                description=f"Specialist customer-care agent for {department.value}.",
            )
        return self._agents[department]

    async def assess(
        self,
        department: Department,
        intake_data: IntakeData,
        user_question: str,
        manager_decision: ManagerDecision,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> SpecialistAssessment:
        """
        Run the relevant specialist agent and return a structured assessment.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        agent = self._get_agent(department)

        task = (
            f"=== Department Routing ===\n"
            f"Department: {department.value}\n"
            f"Routing Reason: {manager_decision.reason}\n\n"
            f"=== Patient Summary ===\n{intake_data.to_summary()}\n\n"
            f"=== Patient Question ===\n{user_question}\n\n"
            f"Please provide your specialist customer-care assessment."
        )

        logger.debug("[SPECIALIST][%s] Running assessment", department.value)

        try:
            result = await agent.run(task=task, cancellation_token=cancellation_token)
        except Exception as exc:
            logger.error("[SPECIALIST][%s] Agent run failed: %s", department.value, exc)
            return SpecialistAssessment(
                department=department,
                assessment="I'm sorry, a technical issue occurred. Please consult directly with the hospital.",
                red_flags_identified=[],
                information_gaps=["Technical error — please see a doctor directly"],
                key_points_for_doctor=[],
            )

        response_text = ""
        for msg in reversed(result.messages):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                response_text = msg.content
                break

        assessment = _parse_specialist_assessment(response_text, department)
        logger.info(
            "[SPECIALIST][%s] Assessment complete, red_flags=%d",
            department.value,
            len(assessment.red_flags_identified),
        )
        return assessment


def _parse_specialist_assessment(text: str, department: Department) -> SpecialistAssessment:
    """Extract and parse the SpecialistAssessment JSON from agent output."""
    match = re.search(r"<SPECIALIST_ASSESSMENT>(.*?)</SPECIALIST_ASSESSMENT>", text, re.DOTALL)
    if not match:
        # Graceful fallback: use the full text as the assessment
        clean = re.sub(r"<[^>]+>", "", text).strip()
        return SpecialistAssessment(
            department=department,
            assessment=clean or "Please consult directly with the specialist.",
            red_flags_identified=[],
            information_gaps=[],
            key_points_for_doctor=[],
        )

    raw = match.group(1).strip()
    try:
        data = json.loads(raw)
        return SpecialistAssessment(
            department=department,
            assessment=str(data.get("assessment", "")).strip(),
            red_flags_identified=[str(x) for x in data.get("red_flags_identified", [])],
            information_gaps=[str(x) for x in data.get("information_gaps", [])],
            key_points_for_doctor=[str(x) for x in data.get("key_points_for_doctor", [])],
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("[SPECIALIST] JSON parse error: %s", exc)
        clean = re.sub(r"<[^>]+>", "", text).strip()
        return SpecialistAssessment(
            department=department,
            assessment=clean or "Please consult directly with the specialist.",
            red_flags_identified=[],
            information_gaps=[],
            key_points_for_doctor=[],
        )
