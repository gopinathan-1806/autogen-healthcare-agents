"""
Pydantic schemas for AI Hospital Customer Care & Patient Navigation System.

These models define structured data exchanged between agents.
No raw patient data is persisted beyond the session.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Department(str, Enum):
    ORTHO = "ORTHO"
    NEURO = "NEURO"
    NEPHRO = "NEPHRO"
    DENTAL = "DENTAL"
    CARDIO = "CARDIO"


class Status(str, Enum):
    VALID = "VALID"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    EMERGENCY = "EMERGENCY"


class Priority(str, Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class Urgency(str, Enum):
    ROUTINE = "ROUTINE"
    SOON = "SOON"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    REVISED = "REVISED"


# ---------------------------------------------------------------------------
# Patient data models
# ---------------------------------------------------------------------------

class PatientProfile(BaseModel):
    name: str = Field(default="Not provided")
    age: Optional[int] = Field(default=None)
    gender: str = Field(default="Not provided")
    blood_pressure: str = Field(default="Not provided")
    blood_sugar: str = Field(default="Not provided")
    temperature: str = Field(default="Not provided")
    heart_rate: str = Field(default="Not provided")
    oxygen_saturation: str = Field(default="Not provided")


class Complaint(BaseModel):
    symptom: str = Field(default="Not provided")
    location: str = Field(default="Not provided")
    duration: str = Field(default="Not provided")
    severity: Optional[int] = Field(default=None, ge=1, le=10)
    frequency: str = Field(default="Not provided")
    aggravating_factors: str = Field(default="Not provided")
    relieving_factors: str = Field(default="Not provided")


class MedicalHistory(BaseModel):
    conditions: List[str] = Field(default_factory=list)
    surgeries: List[str] = Field(default_factory=list)
    hospitalizations: List[str] = Field(default_factory=list)
    major_illnesses: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    drug_allergies: List[str] = Field(default_factory=list)
    other_allergies: List[str] = Field(default_factory=list)
    previous_tests: List[str] = Field(default_factory=list)


class IntakeData(BaseModel):
    """Structured output from the Patient Intake Agent."""
    patient: PatientProfile = Field(default_factory=PatientProfile)
    complaint: Complaint = Field(default_factory=Complaint)
    medical_history: MedicalHistory = Field(default_factory=MedicalHistory)
    raw_conversation: str = Field(default="")
    intake_complete: bool = Field(default=False)
    follow_up_question: Optional[str] = Field(default=None)

    def to_summary(self) -> str:
        """Return a human-readable clinical summary (no raw JSON exposed)."""
        lines = [
            "=== Patient Summary ===",
            f"Name: {self.patient.name}",
            f"Age: {self.patient.age or 'Not provided'}",
            f"Gender: {self.patient.gender}",
            "",
            "--- Chief Complaint ---",
            f"Symptom: {self.complaint.symptom}",
            f"Location: {self.complaint.location}",
            f"Duration: {self.complaint.duration}",
            f"Severity: {self.complaint.severity}/10" if self.complaint.severity else "Severity: Not provided",
            f"Frequency: {self.complaint.frequency}",
            f"Aggravating factors: {self.complaint.aggravating_factors}",
            f"Relieving factors: {self.complaint.relieving_factors}",
            "",
            "--- Vitals (if provided) ---",
            f"BP: {self.patient.blood_pressure}",
            f"Blood sugar: {self.patient.blood_sugar}",
            f"Temperature: {self.patient.temperature}",
            f"Heart rate: {self.patient.heart_rate}",
            f"O2 sat: {self.patient.oxygen_saturation}",
            "",
            "--- Medical History ---",
            f"Conditions: {', '.join(self.medical_history.conditions) or 'None reported'}",
            f"Surgeries: {', '.join(self.medical_history.surgeries) or 'None reported'}",
            f"Hospitalizations: {', '.join(self.medical_history.hospitalizations) or 'None reported'}",
            f"Current medications: {', '.join(self.medical_history.current_medications) or 'None'}",
            f"Drug allergies: {', '.join(self.medical_history.drug_allergies) or 'None'}",
            f"Other allergies: {', '.join(self.medical_history.other_allergies) or 'None'}",
            f"Previous tests: {', '.join(self.medical_history.previous_tests) or 'None'}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent output models
# ---------------------------------------------------------------------------

class ManagerDecision(BaseModel):
    """Structured output from the Manager Agent."""
    department: Optional[Department] = None
    status: Status = Status.VALID
    priority: Priority = Priority.NORMAL
    reason: str = Field(default="")

    def is_emergency(self) -> bool:
        return self.status == Status.EMERGENCY or self.priority == Priority.EMERGENCY

    def is_valid(self) -> bool:
        return self.status == Status.VALID


class SpecialistAssessment(BaseModel):
    """Structured output from a Specialist Agent."""
    department: Department
    assessment: str = Field(default="")
    red_flags_identified: List[str] = Field(default_factory=list)
    information_gaps: List[str] = Field(default_factory=list)
    key_points_for_doctor: List[str] = Field(default_factory=list)


class ClinicalRecommendation(BaseModel):
    """Structured output from the Clinical Support Agent."""
    consultation: Dict[str, str] = Field(default_factory=dict)
    possible_investigations_to_discuss: List[str] = Field(default_factory=list)
    information_to_bring: List[str] = Field(default_factory=list)
    urgency: Urgency = Urgency.ROUTINE
    safety_note: str = Field(default="")


class ReviewResult(BaseModel):
    """Structured output from the Reviewer Agent."""
    verdict: Verdict = Verdict.APPROVED
    final_answer: str = Field(default="")
    issues_found: List[str] = Field(default_factory=list)


class AppointmentSlot(BaseModel):
    """A single appointment slot."""
    date: str
    time: str
    doctor_name: str
    doctor_id: str
    department: str
    available: bool = True


class DoctorInfo(BaseModel):
    """Doctor profile returned from MCP."""
    doctor_id: str
    name: str
    department: str
    specialty: str
    qualifications: str = ""
    available_days: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Session-level aggregate
# ---------------------------------------------------------------------------

class SessionState(BaseModel):
    """Holds all agent outputs for a single patient session."""
    intake: Optional[IntakeData] = None
    manager_decision: Optional[ManagerDecision] = None
    specialist_assessment: Optional[SpecialistAssessment] = None
    clinical_recommendation: Optional[ClinicalRecommendation] = None
    review_result: Optional[ReviewResult] = None
    available_slots: List[AppointmentSlot] = Field(default_factory=list)
    selected_slot: Optional[AppointmentSlot] = None
    processing_steps: List[str] = Field(default_factory=list)
    error: Optional[str] = None
