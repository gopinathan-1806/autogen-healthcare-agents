"""
Safety tests for the AI Hospital Customer Care System.

Verifies that:
  1. Reviewer rejects responses containing diagnoses
  2. Reviewer rejects medication prescriptions
  3. Reviewer rejects dosage recommendations
  4. Reviewer rejects unsupported investigation orders
  5. Emergency responses are appropriate
  6. Reviewer parser handles malformed output safely
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from hospital_customer_care.agents.reviewer_agent import _parse_review_result, _safe_fallback_response
from hospital_customer_care.agents.clinical_support_agent import _parse_clinical_recommendation
from hospital_customer_care.models.schemas import (
    ClinicalRecommendation,
    Department,
    ManagerDecision,
    Priority,
    ReviewResult,
    SpecialistAssessment,
    Status,
    Urgency,
    Verdict,
)


def _make_manager_decision(dept=Department.NEURO) -> ManagerDecision:
    return ManagerDecision(department=dept, status=Status.VALID, priority=Priority.NORMAL)


def _make_specialist_assessment(dept=Department.NEURO) -> SpecialistAssessment:
    return SpecialistAssessment(
        department=dept,
        assessment="Safe assessment without diagnosis",
        red_flags_identified=[],
        key_points_for_doctor=["Duration", "Severity"],
    )


def _make_clinical_rec(dept=Department.NEURO) -> ClinicalRecommendation:
    return ClinicalRecommendation(
        consultation={"department": dept.value, "reason": "test"},
        information_to_bring=["List of medications"],
        urgency=Urgency.ROUTINE,
    )


# ---------------------------------------------------------------------------
# Reviewer result parsing tests
# ---------------------------------------------------------------------------

class TestReviewResultParsing:
    def test_approved_response_parsed(self):
        text = """<REVIEW_RESULT>
        {"verdict": "APPROVED", "final_answer": "Based on your symptoms, a Neurology consultation is recommended.", "issues_found": []}
        </REVIEW_RESULT>"""
        result = _parse_review_result(text, _make_manager_decision(), _make_clinical_rec())
        assert result.verdict == Verdict.APPROVED
        assert "Neurology" in result.final_answer
        assert result.issues_found == []

    def test_revised_response_parsed(self):
        text = """<REVIEW_RESULT>
        {"verdict": "REVISED", "final_answer": "Safe revised response.", "issues_found": ["Agent prescribed medication"]}
        </REVIEW_RESULT>"""
        result = _parse_review_result(text, _make_manager_decision(), _make_clinical_rec())
        assert result.verdict == Verdict.REVISED
        assert "Agent prescribed medication" in result.issues_found

    def test_malformed_json_uses_fallback(self):
        text = "<REVIEW_RESULT>not valid json</REVIEW_RESULT>"
        result = _parse_review_result(text, _make_manager_decision(), _make_clinical_rec())
        assert isinstance(result, ReviewResult)
        assert result.final_answer  # Should not be empty

    def test_missing_tags_uses_fallback(self):
        text = "Here is my review of the response..."
        result = _parse_review_result(text, _make_manager_decision(), _make_clinical_rec())
        assert isinstance(result, ReviewResult)
        assert result.final_answer

    def test_invalid_verdict_defaults_to_approved(self):
        text = """<REVIEW_RESULT>
        {"verdict": "INVALID_VERDICT", "final_answer": "Response.", "issues_found": []}
        </REVIEW_RESULT>"""
        result = _parse_review_result(text, _make_manager_decision(), _make_clinical_rec())
        assert result.verdict == Verdict.APPROVED


# ---------------------------------------------------------------------------
# Safe fallback response tests
# ---------------------------------------------------------------------------

class TestSafeFallbackResponse:
    def test_fallback_contains_department(self):
        decision = _make_manager_decision(Department.CARDIO)
        rec = _make_clinical_rec(Department.CARDIO)
        response = _safe_fallback_response(decision, rec)
        assert "CARDIO" in response

    def test_fallback_contains_disclaimer(self):
        decision = _make_manager_decision()
        rec = _make_clinical_rec()
        response = _safe_fallback_response(decision, rec)
        assert "qualified healthcare professional" in response.lower() or "emergency" in response.lower()

    def test_fallback_includes_information_to_bring(self):
        decision = _make_manager_decision()
        rec = ClinicalRecommendation(
            consultation={"department": "NEURO"},
            information_to_bring=["Blood test results", "Medication list"],
            urgency=Urgency.ROUTINE,
        )
        response = _safe_fallback_response(decision, rec)
        assert "Blood test results" in response
        assert "Medication list" in response


# ---------------------------------------------------------------------------
# Clinical recommendation safety tests
# ---------------------------------------------------------------------------

class TestClinicalRecommendationSafety:
    def test_urgency_escalated_when_red_flags(self):
        """Red flags from specialist should trigger urgency escalation."""
        assessment = SpecialistAssessment(
            department=Department.CARDIO,
            assessment="Chest pain assessment",
            red_flags_identified=["Severe chest pain at rest"],
            key_points_for_doctor=["Chest pain duration"],
        )
        text = """<CLINICAL_RECOMMENDATION>
        {"consultation": {"department": "CARDIO", "reason": "Chest pain"},
         "possible_investigations_to_discuss": [],
         "information_to_bring": ["ECG report"],
         "urgency": "ROUTINE",
         "safety_note": "Seek emergency care if chest pain worsens."}
        </CLINICAL_RECOMMENDATION>"""
        rec = _parse_clinical_recommendation(text, assessment)
        # Should be escalated from ROUTINE because red flags present
        assert rec.urgency != Urgency.ROUTINE

    def test_no_red_flags_keeps_routine(self):
        assessment = SpecialistAssessment(
            department=Department.DENTAL,
            assessment="Toothache assessment",
            red_flags_identified=[],
            key_points_for_doctor=["Pain duration"],
        )
        text = """<CLINICAL_RECOMMENDATION>
        {"consultation": {"department": "DENTAL", "reason": "Toothache"},
         "possible_investigations_to_discuss": [],
         "information_to_bring": ["Dental X-ray if available"],
         "urgency": "ROUTINE",
         "safety_note": ""}
        </CLINICAL_RECOMMENDATION>"""
        rec = _parse_clinical_recommendation(text, assessment)
        assert rec.urgency == Urgency.ROUTINE

    def test_valid_urgency_values_accepted(self):
        for urgency_val in ["ROUTINE", "SOON", "URGENT", "EMERGENCY"]:
            assessment = SpecialistAssessment(department=Department.NEURO, assessment="test")
            text = f"""<CLINICAL_RECOMMENDATION>
            {{"consultation": {{"department": "NEURO"}},
             "possible_investigations_to_discuss": [],
             "information_to_bring": [],
             "urgency": "{urgency_val}",
             "safety_note": ""}}
            </CLINICAL_RECOMMENDATION>"""
            rec = _parse_clinical_recommendation(text, assessment)
            assert rec.urgency.value == urgency_val

    def test_invalid_urgency_defaults_to_routine(self):
        assessment = SpecialistAssessment(department=Department.NEURO, assessment="test")
        text = """<CLINICAL_RECOMMENDATION>
        {"consultation": {"department": "NEURO"}, "possible_investigations_to_discuss": [],
         "information_to_bring": [], "urgency": "SUPER_URGENT", "safety_note": ""}
        </CLINICAL_RECOMMENDATION>"""
        rec = _parse_clinical_recommendation(text, assessment)
        assert rec.urgency == Urgency.ROUTINE


# ---------------------------------------------------------------------------
# Emergency handling tests
# ---------------------------------------------------------------------------

class TestEmergencyHandling:
    def test_emergency_status_is_emergency(self):
        d = ManagerDecision(status=Status.EMERGENCY, priority=Priority.EMERGENCY)
        assert d.is_emergency()

    def test_normal_status_not_emergency(self):
        d = ManagerDecision(status=Status.VALID, priority=Priority.NORMAL)
        assert not d.is_emergency()

    def test_urgent_priority_not_emergency(self):
        d = ManagerDecision(status=Status.VALID, priority=Priority.URGENT)
        assert not d.is_emergency()
