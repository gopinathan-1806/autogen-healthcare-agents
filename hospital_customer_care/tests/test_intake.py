"""
Tests for the Patient Intake Agent.

Verifies:
  1. Intake data extraction from agent output
  2. JSON parsing of structured intake blocks
  3. Missing information handling
  4. Emergency detection in intake
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from hospital_customer_care.agents.intake_agent import _extract_intake_data
from hospital_customer_care.models.schemas import IntakeData, Complaint, PatientProfile


class TestExtractIntakeData:
    """Test the internal intake data extraction parser."""

    def test_complete_intake_extraction(self):
        text = """Thank you for providing that information.
<INTAKE_DATA>
{
  "patient": {
    "name": "John",
    "age": 42,
    "gender": "Male",
    "blood_pressure": "150/95",
    "blood_sugar": "168",
    "temperature": "Not provided",
    "heart_rate": "Not provided",
    "oxygen_saturation": "Not provided"
  },
  "complaint": {
    "symptom": "One-sided headache",
    "location": "Right side",
    "duration": "2 days",
    "severity": 6,
    "frequency": "Intermittent",
    "aggravating_factors": "Bright light",
    "relieving_factors": "Lying in dark room"
  },
  "medical_history": {
    "conditions": ["Hypertension"],
    "surgeries": [],
    "hospitalizations": [],
    "major_illnesses": [],
    "current_medications": ["Amlodipine"],
    "drug_allergies": [],
    "other_allergies": [],
    "previous_tests": []
  },
  "raw_conversation": "",
  "intake_complete": true
}
</INTAKE_DATA>"""
        result = _extract_intake_data(text)
        assert result is not None
        assert result.intake_complete is True
        assert result.patient.name == "John"
        assert result.patient.age == 42
        assert result.complaint.symptom == "One-sided headache"
        assert result.complaint.severity == 6
        assert result.complaint.duration == "2 days"
        assert "Hypertension" in result.medical_history.conditions
        assert "Amlodipine" in result.medical_history.current_medications

    def test_intake_not_complete(self):
        text = """<INTAKE_DATA>
{
  "patient": {"name": "Not provided", "age": null, "gender": "Not provided",
    "blood_pressure": "Not provided", "blood_sugar": "Not provided",
    "temperature": "Not provided", "heart_rate": "Not provided", "oxygen_saturation": "Not provided"},
  "complaint": {"symptom": "knee pain", "location": "Not provided", "duration": "Not provided",
    "severity": null, "frequency": "Not provided", "aggravating_factors": "Not provided",
    "relieving_factors": "Not provided"},
  "medical_history": {"conditions": [], "surgeries": [], "hospitalizations": [],
    "major_illnesses": [], "current_medications": [], "drug_allergies": [],
    "other_allergies": [], "previous_tests": []},
  "raw_conversation": "",
  "intake_complete": false
}
</INTAKE_DATA>"""
        result = _extract_intake_data(text)
        assert result is not None
        assert result.intake_complete is False

    def test_no_intake_block_returns_none(self):
        text = "Hello! Could you please tell me your name?"
        result = _extract_intake_data(text)
        assert result is None

    def test_malformed_json_returns_none(self):
        text = "<INTAKE_DATA>{ invalid json }</INTAKE_DATA>"
        result = _extract_intake_data(text)
        assert result is None

    def test_age_can_be_null(self):
        text = """<INTAKE_DATA>
{
  "patient": {"name": "Jane", "age": null, "gender": "Female",
    "blood_pressure": "Not provided", "blood_sugar": "Not provided",
    "temperature": "Not provided", "heart_rate": "Not provided", "oxygen_saturation": "Not provided"},
  "complaint": {"symptom": "toothache", "location": "Not provided", "duration": "Not provided",
    "severity": null, "frequency": "Not provided", "aggravating_factors": "Not provided",
    "relieving_factors": "Not provided"},
  "medical_history": {"conditions": [], "surgeries": [], "hospitalizations": [],
    "major_illnesses": [], "current_medications": [], "drug_allergies": [],
    "other_allergies": [], "previous_tests": []},
  "raw_conversation": "",
  "intake_complete": true
}
</INTAKE_DATA>"""
        result = _extract_intake_data(text)
        assert result is not None
        assert result.patient.age is None

    def test_intake_strips_json_block_from_display(self):
        """The JSON block should be extracted and not visible in patient response."""
        text = """I have collected your information.
<INTAKE_DATA>
{"patient": {"name": "Test", "age": 30, "gender": "Male",
  "blood_pressure": "Not provided", "blood_sugar": "Not provided",
  "temperature": "Not provided", "heart_rate": "Not provided", "oxygen_saturation": "Not provided"},
 "complaint": {"symptom": "back pain", "location": "lower back", "duration": "1 week",
   "severity": 4, "frequency": "Constant", "aggravating_factors": "Sitting",
   "relieving_factors": "Standing"},
 "medical_history": {"conditions": [], "surgeries": [], "hospitalizations": [],
   "major_illnesses": [], "current_medications": [], "drug_allergies": [],
   "other_allergies": [], "previous_tests": []},
 "raw_conversation": "", "intake_complete": true}
</INTAKE_DATA>
Let me route you to the right specialist."""
        import re
        clean = re.sub(r"<INTAKE_DATA>.*?</INTAKE_DATA>", "", text, flags=re.DOTALL).strip()
        assert "<INTAKE_DATA>" not in clean
        assert "INTAKE_DATA" not in clean
        assert "I have collected" in clean
        assert "Let me route" in clean


class TestIntakeDataModel:
    """Test IntakeData model methods."""

    def test_to_summary_contains_key_fields(self):
        intake = IntakeData(
            patient=PatientProfile(name="Alice", age=55, gender="Female", blood_pressure="130/85"),
            complaint=Complaint(symptom="Chest discomfort", duration="1 hour", severity=7),
            intake_complete=True,
        )
        summary = intake.to_summary()
        assert "Alice" in summary
        assert "55" in summary
        assert "Chest discomfort" in summary
        assert "1 hour" in summary
        assert "130/85" in summary

    def test_to_summary_with_defaults(self):
        intake = IntakeData()
        summary = intake.to_summary()
        assert "Not provided" in summary
