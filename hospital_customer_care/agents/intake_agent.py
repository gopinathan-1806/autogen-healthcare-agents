"""
Patient Intake Agent

Collects structured patient and clinical information through a conversational
interface before routing the request to the appropriate specialist.

IMPORTANT:
  - This agent does NOT diagnose the patient.
  - It asks only relevant follow-up questions.
  - Not all fields are mandatory; users may respond 'Not known'.
  - Returns structured IntakeData internally; raw JSON is never shown to the patient.
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
    IntakeData,
    PatientProfile,
    Complaint,
    MedicalHistory,
)
from ..services.model_client import get_model_client
from ..services.memory import SessionMemory

logger = logging.getLogger(__name__)

_INTAKE_SYSTEM_PROMPT = """You are the Patient Intake Coordinator for CityMed Hospital's AI Customer Care system.

Your role is to collect relevant patient and clinical information in a friendly, professional manner BEFORE the patient is routed to a specialist.

CRITICAL RULES:
1. You must NEVER diagnose the patient.
2. You must NEVER prescribe or suggest medications.
3. You must NEVER prescribe or order tests.
4. You must NEVER make medical conclusions.
5. You must NEVER frighten the patient unnecessarily.
6. You should ask only RELEVANT follow-up questions based on what the patient describes.
7. Accept "Not known" or "I don't know" as a valid answer for any field.
8. Do not force the patient to provide every field.

INFORMATION TO COLLECT (only if relevant):

BASIC DETAILS:
- Name (first name is enough)
- Age
- Gender

CHIEF COMPLAINT:
- Main symptom or problem
- Location of the symptom
- Duration (how long)
- Severity (1-10 scale)
- Frequency (constant, intermittent, occasional)
- What makes it better or worse

VITALS (if available / already measured):
- Blood pressure
- Blood sugar (fasting or random)
- Temperature
- Heart rate
- Oxygen saturation

MEDICAL HISTORY:
- Existing medical conditions (diabetes, hypertension, etc.)
- Previous surgeries
- Previous hospitalizations
- Previous major illnesses

MEDICATIONS & ALLERGIES:
- Current medications
- Known drug allergies
- Other allergies

PREVIOUS INVESTIGATIONS (if any):
- Blood tests
- Imaging (X-ray, CT, MRI, Ultrasound)
- ECG
- Other reports

CONVERSATION APPROACH:
- Start by greeting the patient warmly.
- Ask for the main problem first.
- Ask 2-3 follow-up questions based on the complaint.
- Do not ask all fields at once (avoid overwhelming the patient).
- Once you have enough information to route the request, say: "Thank you. I have enough information to connect you with the right specialist."
- If this is a potential emergency, IMMEDIATELY say: "URGENT: This sounds like it may require immediate medical attention. Please call emergency services or go to the nearest emergency department right away."

At the END of intake, output a JSON block (ONLY for internal use, not visible to patient) wrapped in <INTAKE_DATA>...</INTAKE_DATA> tags containing:
{
  "patient": {
    "name": "",
    "age": null,
    "gender": "",
    "blood_pressure": "",
    "blood_sugar": "",
    "temperature": "",
    "heart_rate": "",
    "oxygen_saturation": ""
  },
  "complaint": {
    "symptom": "",
    "location": "",
    "duration": "",
    "severity": null,
    "frequency": "",
    "aggravating_factors": "",
    "relieving_factors": ""
  },
  "medical_history": {
    "conditions": [],
    "surgeries": [],
    "hospitalizations": [],
    "major_illnesses": [],
    "current_medications": [],
    "drug_allergies": [],
    "other_allergies": [],
    "previous_tests": []
  },
  "raw_conversation": "",
  "intake_complete": true
}

Use "Not provided" for string fields the patient did not supply.
Use null for numeric fields that were not provided.
Use [] for list fields with no entries.
"""


class IntakeAgent:
    """
    Manages the patient intake conversation.

    Wraps an AutoGen AssistantAgent to collect structured clinical context.
    """

    def __init__(self, memory: Optional[SessionMemory] = None) -> None:
        self._memory = memory
        self._model_client = get_model_client()
        memory_list = [memory.get_autogen_memory()] if memory else []
        self._agent = AssistantAgent(
            name="PatientIntakeAgent",
            model_client=self._model_client,
            system_message=_INTAKE_SYSTEM_PROMPT,
            memory=memory_list if memory_list else None,
            description="Collects structured patient information before specialist routing.",
        )

    async def process_message(
        self,
        user_message: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> tuple[str, Optional[IntakeData]]:
        """
        Process one user message in the intake conversation.

        Returns:
            (response_text, intake_data_or_None)
            intake_data is populated when intake is marked complete.
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        logger.debug("[INTAKE] Processing message: %.100s...", user_message)

        try:
            result = await self._agent.run(
                task=user_message,
                cancellation_token=cancellation_token,
            )
        except Exception as exc:
            logger.error("[INTAKE] Agent run failed: %s", exc)
            return (
                "I'm sorry, I encountered a technical issue. Please try again.",
                None,
            )

        # Extract the last assistant message
        response_text = ""
        for msg in reversed(result.messages):
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                response_text = msg.content
                break

        if not response_text:
            response_text = "Could you please tell me more about how you're feeling?"

        # Parse structured intake data if present
        intake_data = _extract_intake_data(response_text)

        # Strip the internal JSON block from the visible response
        clean_response = re.sub(r"<INTAKE_DATA>.*?</INTAKE_DATA>", "", response_text, flags=re.DOTALL).strip()

        if intake_data and self._memory:
            await self._memory.add(
                f"Patient intake completed: {intake_data.complaint.symptom}, "
                f"Age {intake_data.patient.age}, "
                f"Duration {intake_data.complaint.duration}"
            )

        logger.info(
            "[INTAKE] Response generated, intake_complete=%s",
            intake_data.intake_complete if intake_data else False,
        )
        return clean_response, intake_data


def _extract_intake_data(text: str) -> Optional[IntakeData]:
    """Extract and parse the internal JSON block from agent output."""
    match = re.search(r"<INTAKE_DATA>(.*?)</INTAKE_DATA>", text, re.DOTALL)
    if not match:
        return None
    raw_json = match.group(1).strip()
    try:
        data = json.loads(raw_json)
        patient = PatientProfile(**data.get("patient", {}))
        complaint = Complaint(**data.get("complaint", {}))
        history_raw = data.get("medical_history", {})
        history = MedicalHistory(**history_raw)
        return IntakeData(
            patient=patient,
            complaint=complaint,
            medical_history=history,
            raw_conversation=data.get("raw_conversation", ""),
            intake_complete=bool(data.get("intake_complete", False)),
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("[INTAKE] Failed to parse intake JSON: %s", exc)
        return None
