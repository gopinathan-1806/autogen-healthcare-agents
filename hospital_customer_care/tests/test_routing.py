"""
Tests for department routing logic.

These tests verify that:
  1. Each complaint type routes to the correct department
  2. Emergency symptoms are detected
  3. Out-of-scope requests are rejected
  4. The department allowlist is enforced
"""
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from hospital_customer_care.agents.manager_agent import _parse_manager_decision, ManagerAgent
from hospital_customer_care.models.schemas import (
    Department,
    IntakeData,
    ManagerDecision,
    Complaint,
    Priority,
    Status,
)


# ---------------------------------------------------------------------------
# Helper: build minimal intake data
# ---------------------------------------------------------------------------

def _make_intake(symptom: str, age: int = 35) -> IntakeData:
    return IntakeData(
        complaint=Complaint(symptom=symptom, duration="2 days", severity=5),
        intake_complete=True,
    )


# ---------------------------------------------------------------------------
# Test _parse_manager_decision
# ---------------------------------------------------------------------------

class TestParseManagerDecision:
    """Unit tests for the manager decision parser."""

    def test_neuro_routing(self):
        text = """<MANAGER_DECISION>
        {"department": "NEURO", "status": "VALID", "priority": "NORMAL", "reason": "Headache complaint"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department == Department.NEURO
        assert decision.status == Status.VALID
        assert decision.priority == Priority.NORMAL

    def test_ortho_routing(self):
        text = """<MANAGER_DECISION>
        {"department": "ORTHO", "status": "VALID", "priority": "NORMAL", "reason": "Knee pain"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department == Department.ORTHO

    def test_nephro_routing(self):
        text = """<MANAGER_DECISION>
        {"department": "NEPHRO", "status": "VALID", "priority": "NORMAL", "reason": "Kidney pain"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department == Department.NEPHRO

    def test_dental_routing(self):
        text = """<MANAGER_DECISION>
        {"department": "DENTAL", "status": "VALID", "priority": "NORMAL", "reason": "Toothache"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department == Department.DENTAL

    def test_cardio_routing(self):
        text = """<MANAGER_DECISION>
        {"department": "CARDIO", "status": "VALID", "priority": "NORMAL", "reason": "Chest pain"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department == Department.CARDIO

    def test_out_of_scope(self):
        text = """<MANAGER_DECISION>
        {"department": null, "status": "OUT_OF_SCOPE", "priority": "NORMAL", "reason": "Not a medical request"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.status == Status.OUT_OF_SCOPE
        assert not decision.is_valid()

    def test_emergency_detection(self):
        text = """<MANAGER_DECISION>
        {"department": "NEURO", "status": "EMERGENCY", "priority": "EMERGENCY", "reason": "Thunderclap headache"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.status == Status.EMERGENCY
        assert decision.is_emergency()

    def test_invalid_department_is_none(self):
        """Invalid department codes must be rejected — not passed through."""
        text = """<MANAGER_DECISION>
        {"department": "INVALID_DEPT", "status": "VALID", "priority": "NORMAL", "reason": "test"}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert decision.department is None  # Invalid code → None

    def test_missing_json_tags(self):
        """Malformed output should return a safe default."""
        decision = _parse_manager_decision("I think you should see a neurologist.")
        assert isinstance(decision, ManagerDecision)

    def test_malformed_json(self):
        """Malformed JSON should return a safe default."""
        text = "<MANAGER_DECISION>not valid json</MANAGER_DECISION>"
        decision = _parse_manager_decision(text)
        assert isinstance(decision, ManagerDecision)

    def test_reason_length_capped(self):
        """Reason field should be capped at 500 characters."""
        long_reason = "x" * 600
        text = f"""<MANAGER_DECISION>
        {{"department": "NEURO", "status": "VALID", "priority": "NORMAL", "reason": "{long_reason}"}}
        </MANAGER_DECISION>"""
        decision = _parse_manager_decision(text)
        assert len(decision.reason) <= 500


# ---------------------------------------------------------------------------
# Test department allowlist enforcement
# ---------------------------------------------------------------------------

class TestDepartmentAllowlist:
    """Verify only allowlisted department codes are accepted."""

    VALID_CODES = {"ORTHO", "NEURO", "NEPHRO", "DENTAL", "CARDIO"}
    INVALID_CODES = ["GENERAL", "INTERNAL", "SURGERY", "ADMIN", "DROP TABLE", "../../etc"]

    def test_all_valid_departments_accepted(self):
        for code in self.VALID_CODES:
            text = f"""<MANAGER_DECISION>
            {{"department": "{code}", "status": "VALID", "priority": "NORMAL", "reason": "test"}}
            </MANAGER_DECISION>"""
            decision = _parse_manager_decision(text)
            assert decision.department is not None, f"Department {code} should be accepted"
            assert decision.department.value == code

    def test_invalid_departments_rejected(self):
        for code in self.INVALID_CODES:
            text = f"""<MANAGER_DECISION>
            {{"department": "{code}", "status": "VALID", "priority": "NORMAL", "reason": "test"}}
            </MANAGER_DECISION>"""
            decision = _parse_manager_decision(text)
            assert decision.department is None, f"Department '{code}' should be rejected"


# ---------------------------------------------------------------------------
# Test ManagerDecision model
# ---------------------------------------------------------------------------

class TestManagerDecisionModel:
    def test_is_emergency_with_status(self):
        d = ManagerDecision(status=Status.EMERGENCY, priority=Priority.NORMAL)
        assert d.is_emergency()

    def test_is_emergency_with_priority(self):
        d = ManagerDecision(status=Status.VALID, priority=Priority.EMERGENCY)
        assert d.is_emergency()

    def test_is_not_emergency(self):
        d = ManagerDecision(status=Status.VALID, priority=Priority.NORMAL)
        assert not d.is_emergency()

    def test_is_valid(self):
        d = ManagerDecision(status=Status.VALID)
        assert d.is_valid()

    def test_out_of_scope_is_not_valid(self):
        d = ManagerDecision(status=Status.OUT_OF_SCOPE)
        assert not d.is_valid()
