"""
AI Hospital MCP Server — hospital_mcp_server.py

Exposes read-only hospital information tools via MCP (FastMCP).

IMPORTANT:
  - This server contains MOCK DATA ONLY.
  - No real patient data, medical records, or credentials.
  - All tools are read-only (write operations require explicit confirmation).
  - API keys and secrets must never be added here.
  - Tool arguments are validated against an allowlist.

Run this server:
    python3.10 hospital_mcp_server.py

The AutoGen agents connect to this server via stdio.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG_MODE", "false").lower() == "true" else logging.ERROR,
    format="%(asctime)s [MCP] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load mock data
# ---------------------------------------------------------------------------
_DATA_PATH = Path(__file__).parent / "data" / "mock_hospital_data.json"

def _load_data() -> Dict[str, Any]:
    try:
        with open(_DATA_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.error("[MCP] Mock data file not found at %s", _DATA_PATH)
        return {}

_DATA: Dict[str, Any] = _load_data()

# Allowlisted department codes
_VALID_DEPARTMENTS = {"ORTHO", "NEURO", "NEPHRO", "DENTAL", "CARDIO"}

def _validate_department(department: str) -> str:
    """Validate department is in the allowlist."""
    dept = department.upper().strip()
    if dept not in _VALID_DEPARTMENTS:
        raise ValueError(f"Invalid department '{department}'. Allowed: {sorted(_VALID_DEPARTMENTS)}")
    return dept

def _validate_doctor_id(doctor_id: str) -> str:
    """Basic validation on doctor_id to prevent injection."""
    did = doctor_id.strip()
    if not did.replace("-", "").replace("_", "").isalnum() or len(did) > 20:
        raise ValueError(f"Invalid doctor_id format: '{doctor_id}'")
    return did.upper()

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="HospitalInfoServer",
    instructions=(
        "This MCP server provides read-only hospital information for the "
        "AI Hospital Customer Care System. All data is mock/demo data. "
        "No real patient records are stored or returned."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_departments() -> Dict[str, Any]:
    """
    List all available hospital departments with their names and descriptions.

    Returns a dictionary of department codes and their information.
    """
    logger.debug("[MCP] list_departments called")
    departments = _DATA.get("departments", {})
    return {
        code: {
            "name": info.get("name", ""),
            "description": info.get("description", ""),
            "location": info.get("location", ""),
            "phone": info.get("phone", ""),
        }
        for code, info in departments.items()
    }


@mcp.tool()
def get_department_scope(department: str) -> Dict[str, Any]:
    """
    Get the clinical scope and contact details for a specific department.

    Args:
        department: Department code — one of ORTHO, NEURO, NEPHRO, DENTAL, CARDIO
    """
    logger.debug("[MCP] get_department_scope called for: %s", department)
    dept = _validate_department(department)
    departments = _DATA.get("departments", {})
    info = departments.get(dept)
    if not info:
        return {"error": f"Department '{dept}' not found"}
    return {
        "code": dept,
        "name": info.get("name", ""),
        "description": info.get("description", ""),
        "scope": info.get("scope", []),
        "location": info.get("location", ""),
        "phone": info.get("phone", ""),
    }


@mcp.tool()
def get_emergency_guidance() -> Dict[str, Any]:
    """
    Return emergency guidance including red-flag symptoms and emergency contact numbers.

    Always call this when the patient describes potentially life-threatening symptoms.
    """
    logger.debug("[MCP] get_emergency_guidance called")
    guidance = _DATA.get("emergency_guidance", {})
    return {
        "emergency_number": guidance.get("emergency_number", "112 / 911"),
        "hospital_emergency": guidance.get("hospital_emergency", ""),
        "message": guidance.get("message", "Please seek emergency care immediately."),
        "red_flag_symptoms": guidance.get("red_flag_symptoms", []),
    }


@mcp.tool()
def get_available_doctors(department: str) -> List[Dict[str, Any]]:
    """
    Get the list of available doctors for a specific department.

    Args:
        department: Department code — one of ORTHO, NEURO, NEPHRO, DENTAL, CARDIO
    """
    logger.debug("[MCP] get_available_doctors called for: %s", department)
    dept = _validate_department(department)
    doctors_by_dept = _DATA.get("doctors", {})
    doctors = doctors_by_dept.get(dept, [])
    # Return only non-sensitive fields
    return [
        {
            "doctor_id": d.get("doctor_id", ""),
            "name": d.get("name", ""),
            "department": d.get("department", ""),
            "specialty": d.get("specialty", ""),
            "qualifications": d.get("qualifications", ""),
            "available_days": d.get("available_days", []),
        }
        for d in doctors
    ]


@mcp.tool()
def get_available_appointments(department: str) -> List[Dict[str, Any]]:
    """
    Get available appointment slots for a specific department.

    Args:
        department: Department code — one of ORTHO, NEURO, NEPHRO, DENTAL, CARDIO
    """
    logger.debug("[MCP] get_available_appointments called for: %s", department)
    dept = _validate_department(department)
    appointments_by_dept = _DATA.get("appointments", {})
    slots = appointments_by_dept.get(dept, [])

    # Enrich with doctor name by joining with doctors data
    doctors_by_dept = _DATA.get("doctors", {})
    doctors_map: Dict[str, str] = {}
    for doc_list in doctors_by_dept.values():
        for doc in doc_list:
            doctors_map[doc["doctor_id"]] = doc["name"]

    return [
        {
            "date": slot.get("date", ""),
            "time": slot.get("time", ""),
            "doctor_id": slot.get("doctor_id", ""),
            "doctor_name": doctors_map.get(slot.get("doctor_id", ""), "Unknown"),
            "department": dept,
            "available": slot.get("available", True),
        }
        for slot in slots
        if slot.get("available", True)
    ]


@mcp.tool()
def get_doctor_details(doctor_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific doctor by their ID.

    Args:
        doctor_id: The doctor's unique identifier (e.g. NEUR001, CARD002)
    """
    logger.debug("[MCP] get_doctor_details called for: %s", doctor_id)
    did = _validate_doctor_id(doctor_id)
    doctors_by_dept = _DATA.get("doctors", {})
    for doc_list in doctors_by_dept.values():
        for doc in doc_list:
            if doc.get("doctor_id", "").upper() == did:
                return {
                    "doctor_id": doc.get("doctor_id", ""),
                    "name": doc.get("name", ""),
                    "department": doc.get("department", ""),
                    "specialty": doc.get("specialty", ""),
                    "qualifications": doc.get("qualifications", ""),
                    "available_days": doc.get("available_days", []),
                }
    return {"error": f"Doctor '{doctor_id}' not found"}


@mcp.tool()
def get_hospital_services() -> Dict[str, Any]:
    """
    Return the list of services offered by the hospital along with general contact information.
    """
    logger.debug("[MCP] get_hospital_services called")
    hospital = _DATA.get("hospital", {})
    services = _DATA.get("services", [])
    return {
        "hospital_name": hospital.get("name", "CityMed Hospital"),
        "address": hospital.get("address", ""),
        "phone": hospital.get("phone", ""),
        "hours": hospital.get("hours", ""),
        "website": hospital.get("website", ""),
        "services": services,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("[MCP] Hospital MCP Server starting...")
    mcp.run()
