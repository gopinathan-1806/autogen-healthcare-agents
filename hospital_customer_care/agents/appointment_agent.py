"""
Appointment Agent

Helps the patient identify an appropriate doctor and available appointment slots
using the hospital MCP server.

CRITICAL RULES:
  - Does NOT automatically book appointments.
  - Requires explicit user confirmation before any booking operation.
  - Uses MCP tools to retrieve live (mock) data.
  - Validates all tool arguments against the department allowlist.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_core import CancellationToken
from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams

from ..models.schemas import AppointmentSlot, Department, DoctorInfo
from ..services.model_client import get_model_client

logger = logging.getLogger(__name__)

# Path to the MCP server script
_MCP_SERVER_PATH = str(
    Path(__file__).parent.parent / "hospital_mcp_server.py"
)

_APPOINTMENT_SYSTEM_PROMPT = """You are the Appointment Scheduling Assistant for CityMed Hospital.

You help patients identify the right doctor and available appointment slots.

YOU HAVE ACCESS TO THESE TOOLS:
- get_available_doctors(department): List available doctors for a department
- get_available_appointments(department): List available appointment slots
- get_doctor_details(doctor_id): Get details about a specific doctor
- get_hospital_services(): Get general hospital information

RULES:
1. Only retrieve appointments for valid departments: ORTHO, NEURO, NEPHRO, DENTAL, CARDIO
2. Present appointment options clearly — date, time, doctor name, specialty
3. NEVER automatically book an appointment — always wait for explicit patient confirmation
4. If asked about a doctor, use get_doctor_details for accurate information
5. NEVER invent or guess appointment availability — use only tool data
6. If MCP tools fail, inform the patient to call the hospital directly

FORMAT your response as a clear, friendly message listing available slots.
"""


class AppointmentAgent:
    """
    Retrieves doctor information and available appointment slots from the MCP server.

    Uses AutoGen McpWorkbench to connect to the hospital_mcp_server.
    """

    def __init__(self) -> None:
        self._model_client = get_model_client()

    async def get_slots(
        self,
        department: Department,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> tuple[str, List[AppointmentSlot]]:
        """
        Retrieve available appointment slots for the given department.

        Returns:
            (human_readable_text, list_of_AppointmentSlot)
        """
        if cancellation_token is None:
            cancellation_token = CancellationToken()

        server_params = StdioServerParams(
            command=sys.executable,
            args=[_MCP_SERVER_PATH],
        )

        slots: List[AppointmentSlot] = []
        response_text = ""

        logger.debug("[APPOINTMENT] Fetching slots for dept: %s", department.value)

        try:
            workbench = McpWorkbench(server_params=server_params)
            async with workbench:
                agent = AssistantAgent(
                    name="AppointmentAgent",
                    model_client=self._model_client,
                    workbench=workbench,
                    system_message=_APPOINTMENT_SYSTEM_PROMPT,
                    description="Retrieves hospital appointment slots from the MCP server.",
                    reflect_on_tool_use=True,
                )

                task = (
                    f"Please retrieve the available doctors and appointment slots for the "
                    f"{department.value} department. "
                    f"List them clearly with doctor names, specialties, dates, and times."
                )

                result = await agent.run(
                    task=task,
                    cancellation_token=cancellation_token,
                )

                for msg in reversed(result.messages):
                    if hasattr(msg, "content") and isinstance(msg.content, str) and msg.source != "user":
                        response_text = msg.content
                        break

                # Also fetch structured slot data directly
                slots = await _fetch_slots_direct(workbench, department)

        except Exception as exc:
            logger.error("[APPOINTMENT] MCP fetch failed: %s", exc)
            response_text = (
                f"I was unable to retrieve live appointment data at this time. "
                f"Please contact the hospital directly to schedule your {department.value} appointment.\n"
                f"📞 Hospital: +1-800-CITYMED"
            )

        logger.info("[APPOINTMENT] Retrieved %d slots for %s", len(slots), department.value)
        return response_text, slots


async def _fetch_slots_direct(
    workbench: McpWorkbench,
    department: Department,
) -> List[AppointmentSlot]:
    """
    Fetch appointment slots directly via the workbench (structured data).

    The McpWorkbench returns a ToolResult whose .result is a list of
    TextResultContent items — each containing one JSON object as a string.
    """
    import json as _json

    try:
        raw = await workbench.call_tool(
            "get_available_appointments",
            {"department": department.value},
        )
        slots = []

        # raw is a ToolResult; .result is a list of TextResultContent
        result_list = getattr(raw, "result", None) or getattr(raw, "content", None)
        if not result_list:
            return slots

        for item in result_list:
            # Each item is a TextResultContent with a .content string
            text = getattr(item, "content", None) or getattr(item, "text", None)
            if not text:
                continue
            try:
                data = _json.loads(text)
                # data may be a single dict or a list of dicts
                items = data if isinstance(data, list) else [data]
                for slot_data in items:
                    if slot_data.get("available", True):
                        slots.append(
                            AppointmentSlot(
                                date=slot_data.get("date", ""),
                                time=slot_data.get("time", ""),
                                doctor_name=slot_data.get("doctor_name", ""),
                                doctor_id=slot_data.get("doctor_id", ""),
                                department=slot_data.get("department", department.value),
                                available=True,
                            )
                        )
            except (_json.JSONDecodeError, TypeError):
                continue

        return slots
    except Exception as exc:
        logger.warning("[APPOINTMENT] Direct slot fetch failed: %s", exc)
        return []
