"""
Orchestration Layer

Controls the deterministic workflow:

  Patient Intake → Manager → Emergency? → Specialist → Clinical Support → Reviewer → Appointment → Response

The LLM decides the department; the application validates it.
Each agent receives ONLY the information it needs — no full message-history dumps.
"""
from __future__ import annotations

import logging
import os
from typing import AsyncGenerator, Optional

from autogen_core import CancellationToken

from ..agents.appointment_agent import AppointmentAgent
from ..agents.clinical_support_agent import ClinicalSupportAgent
from ..agents.intake_agent import IntakeAgent
from ..agents.manager_agent import ManagerAgent
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.specialist_agents import SpecialistAgents
from ..models.schemas import (
    Complaint,
    Department,
    IntakeData,
    ManagerDecision,
    Priority,
    ReviewResult,
    SessionState,
    Status,
    Urgency,
    Verdict,
)
from ..services.memory import SessionMemory

logger = logging.getLogger(__name__)

_DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

_EMERGENCY_RESPONSE = """🚨 **URGENT — Please seek emergency care immediately.**

The symptoms you have described may require immediate medical attention.

**Please take one of these actions NOW:**
- **Call emergency services: 112 / 911** (or your local emergency number)
- **Go to the nearest Emergency Department immediately**
- **Call the hospital emergency line: +1-800-EMERGENCY**

**Do not drive yourself** if you are feeling unwell — ask someone to take you or call an ambulance.

⚠️ *This AI customer-care system is not equipped to handle medical emergencies. Please seek immediate in-person medical care.*
"""

_OUT_OF_SCOPE_RESPONSE = """Thank you for reaching out to CityMed Hospital's AI Customer Care system.

I'm sorry, but your request does not appear to be related to hospital or medical care, so I'm unable to assist with it through this system.

If you have a medical concern or would like to schedule a consultation, please feel free to ask and I'll be happy to help.

📞 **For general hospital enquiries:** +1-800-CITYMED
🌐 **Website:** https://citymed.example.com

⚠️ *If this is a medical emergency, please call emergency services immediately.*
"""


class HospitalOrchestrator:
    """
    Manages the full deterministic agent workflow for a patient session.
    """

    def __init__(self) -> None:
        self._memory = SessionMemory()
        self._intake_agent = IntakeAgent(memory=self._memory)
        self._manager_agent = ManagerAgent()
        self._specialist_agents = SpecialistAgents()
        self._clinical_support_agent = ClinicalSupportAgent()
        self._reviewer_agent = ReviewerAgent()
        self._appointment_agent = AppointmentAgent()
        self._session_state = SessionState()
        self._intake_complete = False
        self._pending_intake: Optional[IntakeData] = None

    @property
    def session_state(self) -> SessionState:
        return self._session_state

    @property
    def intake_complete(self) -> bool:
        return self._intake_complete

    async def handle_intake_message(
        self,
        user_message: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> str:
        """
        Process one turn of the patient intake conversation.

        Returns the intake agent's response for display in the UI.
        """
        response, intake_data = await self._intake_agent.process_message(
            user_message,
            cancellation_token=cancellation_token,
        )

        if intake_data and intake_data.intake_complete:
            self._pending_intake = intake_data
            self._intake_complete = True
            self._session_state.intake = intake_data
            logger.info("[ORCHESTRATOR] Intake completed")

        return response

    async def run_full_workflow(
        self,
        user_question: str,
        intake_data: Optional[IntakeData] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[tuple[str, SessionState], None]:
        """
        Run the full deterministic agent workflow.

        Yields (step_name, session_state) tuples as each stage completes,
        allowing the UI to show live progress.

        Steps yielded:
          'intake_ready'
          'manager_complete'
          'specialist_complete'
          'clinical_support_complete'
          'reviewer_complete'
          'appointment_complete'
          'workflow_complete'
          'emergency'
          'out_of_scope'
          'error'
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        # Use provided intake or session intake
        effective_intake = intake_data or self._pending_intake or self._session_state.intake
        if not effective_intake:
            effective_intake = IntakeData(
                complaint=Complaint(symptom=user_question),
                intake_complete=True,
            )

        self._session_state.intake = effective_intake
        self._session_state.processing_steps = []

        # ── Step 1: Manager routing ──────────────────────────────────────────
        try:
            _log("[ORCHESTRATOR] Starting manager routing")
            manager_decision = await self._manager_agent.route(
                intake_data=effective_intake,
                user_question=user_question,
                cancellation_token=cancellation_token,
            )
            self._session_state.manager_decision = manager_decision
            self._session_state.processing_steps.append("manager_complete")
            yield "manager_complete", self._session_state
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Manager failed: %s", exc)
            self._session_state.error = "Routing error — please try again"
            yield "error", self._session_state
            return

        # ── Step 2: Emergency check ──────────────────────────────────────────
        if manager_decision.is_emergency():
            _log("[ORCHESTRATOR] EMERGENCY detected")
            await self._memory.add("EMERGENCY flag raised during this session")
            self._session_state.review_result = ReviewResult(
                verdict=Verdict.APPROVED,
                final_answer=_EMERGENCY_RESPONSE,
            )
            self._session_state.processing_steps.append("emergency")
            yield "emergency", self._session_state
            return

        # ── Step 3: Out-of-scope check ───────────────────────────────────────
        if not manager_decision.is_valid():
            _log("[ORCHESTRATOR] OUT_OF_SCOPE — not a medical request")
            self._session_state.review_result = ReviewResult(
                verdict=Verdict.APPROVED,
                final_answer=_OUT_OF_SCOPE_RESPONSE,
            )
            self._session_state.processing_steps.append("out_of_scope")
            yield "out_of_scope", self._session_state
            return

        department = manager_decision.department
        if not department:
            logger.warning("[ORCHESTRATOR] Manager returned no department — defaulting to NEURO")
            department = Department.NEURO

        # ── Step 4: Specialist assessment ────────────────────────────────────
        try:
            _log(f"[ORCHESTRATOR] Running {department.value} specialist agent")
            specialist_assessment = await self._specialist_agents.assess(
                department=department,
                intake_data=effective_intake,
                user_question=user_question,
                manager_decision=manager_decision,
                cancellation_token=cancellation_token,
            )
            self._session_state.specialist_assessment = specialist_assessment
            self._session_state.processing_steps.append("specialist_complete")
            yield "specialist_complete", self._session_state
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Specialist failed: %s", exc)
            self._session_state.error = "Specialist agent error"
            yield "error", self._session_state
            return

        # ── Step 5: Clinical support ─────────────────────────────────────────
        try:
            _log("[ORCHESTRATOR] Running clinical support agent")
            clinical_recommendation = await self._clinical_support_agent.generate_recommendation(
                intake_data=effective_intake,
                specialist_assessment=specialist_assessment,
                cancellation_token=cancellation_token,
            )
            self._session_state.clinical_recommendation = clinical_recommendation
            self._session_state.processing_steps.append("clinical_support_complete")
            yield "clinical_support_complete", self._session_state
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Clinical support failed: %s", exc)
            self._session_state.error = "Clinical support error"
            yield "error", self._session_state
            return

        # ── Step 6: Reviewer ─────────────────────────────────────────────────
        try:
            _log("[ORCHESTRATOR] Running reviewer agent")
            review_result = await self._reviewer_agent.review(
                user_question=user_question,
                intake_data=effective_intake,
                manager_decision=manager_decision,
                specialist_assessment=specialist_assessment,
                clinical_recommendation=clinical_recommendation,
                cancellation_token=cancellation_token,
            )
            self._session_state.review_result = review_result
            self._session_state.processing_steps.append("reviewer_complete")
            yield "reviewer_complete", self._session_state
        except Exception as exc:
            logger.error("[ORCHESTRATOR] Reviewer failed: %s", exc)
            self._session_state.error = "Reviewer error"
            yield "error", self._session_state
            return

        # ── Step 7: Appointment retrieval ────────────────────────────────────
        try:
            _log(f"[ORCHESTRATOR] Fetching appointments for {department.value}")
            appointment_text, slots = await self._appointment_agent.get_slots(
                department=department,
                cancellation_token=cancellation_token,
            )
            self._session_state.available_slots = slots
            self._session_state.processing_steps.append("appointment_complete")
            yield "appointment_complete", self._session_state
        except Exception as exc:
            logger.warning("[ORCHESTRATOR] Appointment fetch failed (non-fatal): %s", exc)
            # Appointment failure is non-fatal — continue to completion
            self._session_state.processing_steps.append("appointment_complete")
            yield "appointment_complete", self._session_state

        self._session_state.processing_steps.append("workflow_complete")
        _log("[ORCHESTRATOR] Workflow complete")
        yield "workflow_complete", self._session_state

    def reset(self) -> None:
        """Reset the session for a new patient."""
        self._session_state = SessionState()
        self._intake_complete = False
        self._pending_intake = None

    async def clear_memory(self) -> None:
        """Clear in-session memory."""
        await self._memory.clear()


def _log(message: str) -> None:
    """Log only when DEBUG_MODE is enabled."""
    if _DEBUG_MODE:
        logger.debug(message)
    else:
        logger.info(message)
