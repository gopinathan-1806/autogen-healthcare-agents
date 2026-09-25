# AI Hospital Customer Care & Patient Navigation System

> **Educational / Customer-Care Prototype — NOT a clinical diagnostic system.**
> This application assists with patient navigation and information only.
> It does not diagnose diseases, prescribe medications, or autonomously order medical tests.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Web UI (app.py)                    │
│         Clean patient-facing interface — no raw agent output    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│               HospitalOrchestrator (orchestration.py)           │
│           Deterministic workflow controller — not LLM-driven    │
└─────┬───────────────────────────────────────────────────────────┘
      │
      │  ┌───────────────────────────────────────────────────────┐
      │  │             Patient Intake Agent                       │
      │  │  Collects structured patient info via conversation    │
      │  │  Returns IntakeData (never shown raw to patient)       │
      │  └───────────────────────────┬───────────────────────────┘
      │                              │
      │  ┌───────────────────────────▼───────────────────────────┐
      │  │               Manager Agent                           │
      │  │  Routes to department — validates against allowlist   │
      │  │  Detects: VALID / OUT_OF_SCOPE / EMERGENCY            │
      │  │  Returns ManagerDecision (internal only)               │
      │  └──────┬────────────┬──────────────────────────────────┘
      │         │            │
      │   EMERGENCY      OUT_OF_SCOPE        VALID
      │         │            │                  │
      │   ┌─────▼──┐   ┌─────▼──┐    ┌─────────▼────────────────┐
      │   │Emergency│   │Scope   │    │  Specialist Agent (1 of 5)│
      │   │Response │   │Response│    │  ORTHO / NEURO / NEPHRO  │
      │   └─────────┘   └────────┘    │  DENTAL / CARDIO         │
      │                               └─────────────┬────────────┘
      │                                             │
      │                          ┌──────────────────▼─────────────┐
      │                          │    Clinical Support Agent       │
      │                          │  Generates next-step plan       │
      │                          │  "Discuss with your doctor..."  │
      │                          └──────────────────┬─────────────┘
      │                                             │
      │                          ┌──────────────────▼─────────────┐
      │                          │       Reviewer Agent            │
      │                          │  Safety & quality gate          │
      │                          │  ONLY output shown to patient   │
      │                          └──────────────────┬─────────────┘
      │                                             │
      │  ┌───────────────────────────────────────────▼────────────┐
      │  │               Appointment Agent (via MCP)               │
      │  │  Retrieves doctors and slots from hospital_mcp_server  │
      │  │  Requires explicit user confirmation to book           │
      │  └───────────────────────────────────────────────────────┘
      │
      │  ┌─────────────────────────────────────────────────────── ┐
      │  │             Hospital MCP Server                         │
      │  │  hospital_mcp_server.py — FastMCP via stdio            │
      │  │  Tools: list_departments, get_department_scope,        │
      │  │         get_emergency_guidance, get_available_doctors,  │
      │  │         get_available_appointments, get_doctor_details, │
      │  │         get_hospital_services                           │
      │  │  Mock data only — no real patient records               │
      │  └─────────────────────────────────────────────────────── ┘
```

---

## 1. Project Overview

The **AI Hospital Customer Care & Patient Navigation System** is a production-style prototype that demonstrates how Agentic AI (Microsoft AutoGen), MCP (Model Context Protocol), and a GPT-compatible LLM can be used to create a multi-agent healthcare customer-care system.

**Key capabilities:**
- Conversational patient intake to collect structured clinical context
- Intelligent routing to the appropriate medical department
- Safe specialist-level customer-care guidance (without diagnosis or prescription)
- Clinician-reviewable next-step recommendations
- Safety review gate (Reviewer Agent) before any output reaches the patient
- Appointment availability via MCP-connected hospital data server
- In-session memory for contextual continuity

---

## 2. Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Agent Framework | AutoGen AgentChat 0.7.5 |
| LLM | OpenAI-compatible GPT (configurable) |
| MCP | FastMCP (mcp 1.28+) |
| UI | Streamlit 1.35+ |
| Schemas | Pydantic v2 |
| Memory | AutoGen ListMemory |
| Config | python-dotenv |

---

## 3. Agent Responsibilities

### Patient Intake Agent (`agents/intake_agent.py`)
Collects structured patient and clinical information conversationally. Returns `IntakeData` (Pydantic model). Never displays raw JSON to the patient. Does not diagnose.

### Manager Agent (`agents/manager_agent.py`)
Central orchestrator. Validates requests, detects emergencies, and routes to the correct department (ORTHO/NEURO/NEPHRO/DENTAL/CARDIO). Returns `ManagerDecision`. Application validates the LLM's department choice against an allowlist.

### Specialist Agents (`agents/specialist_agents.py`)
Five agents — one per department. Activated only for the relevant department. Provides safe specialist guidance without diagnosing or prescribing. Returns `SpecialistAssessment`.

### Clinical Support Agent (`agents/clinical_support_agent.py`)
Converts the specialist assessment into a structured `ClinicalRecommendation`. Lists possible investigations framed as "discuss with your doctor." Never orders tests autonomously.

### Reviewer Agent (`agents/reviewer_agent.py`)
Final safety gate. Reviews all agent outputs against a 13-point safety checklist. Rewrites unsafe content. Returns `ReviewResult`. **Only the Reviewer's `final_answer` is ever shown to the patient.**

### Appointment Agent (`agents/appointment_agent.py`)
Uses AutoGen McpWorkbench to query the hospital MCP server for doctor availability and appointment slots. Requires **explicit user confirmation** before booking.

---

## 4. AutoGen Workflow

```
Patient Intake Agent  (conversational, multi-turn)
         ↓
Manager Agent         (single-turn routing decision)
         ↓
    Emergency? ──YES──→ Emergency Response (stops here)
         ↓ NO
 Out of Scope? ──YES──→ Scope Response (stops here)
         ↓ NO
Specialist Agent      (only the relevant one — ORTHO/NEURO/etc.)
         ↓
Clinical Support Agent
         ↓
Reviewer Agent        ← ONLY output from here shown to patient
         ↓
Appointment Agent     (via MCP)
         ↓
Final Response
```

---

## 5. MCP Architecture

The MCP server (`hospital_mcp_server.py`) runs as a separate process and communicates via stdio.

**Tools exposed:**

| Tool | Description |
|------|-------------|
| `list_departments()` | All departments with names and descriptions |
| `get_department_scope(department)` | Clinical scope of a specific department |
| `get_emergency_guidance()` | Emergency contacts and red-flag symptoms |
| `get_available_doctors(department)` | Doctors available in a department |
| `get_available_appointments(department)` | Available appointment slots |
| `get_doctor_details(doctor_id)` | Doctor profile and availability |
| `get_hospital_services()` | Hospital services and contact info |

All tools are **read-only**. Department codes and doctor IDs are validated against allowlists before tool execution.

---

## 6. Memory

AutoGen `ListMemory` provides in-session contextual memory. Key clinical context is stored and can be retrieved across agent turns within a session.

**For production healthcare use, memory must include:**
- Encryption at rest and in transit
- Role-based access control
- Retention and deletion policy
- Audit logging
- Patient consent management
- HIPAA/GDPR-compliant backend storage

---

## 7. Patient Intake

The intake agent collects:
- Basic details (name, age, gender)
- Chief complaint (symptom, location, duration, severity, frequency, aggravating/relieving factors)
- Vitals if available (BP, blood sugar, temperature, HR, O2 sat)
- Medical history (conditions, surgeries, hospitalizations)
- Medications and allergies
- Previous investigations

All fields are optional — patients may answer "Not known" for any field.

---

## 8. Safety Architecture

**Emergency Handling:**
Any presentation matching red-flag criteria (e.g. thunderclap headache, severe chest pain, stroke symptoms, loss of consciousness) immediately triggers `EMERGENCY` status. The UI displays a prominent emergency response directing the patient to emergency services. Normal agent processing stops.

**Reviewer Gate:**
Every response passes through a 13-point safety review:
1. Correct department selection
2. Appropriate patient information handling
3. No diagnoses
4. No medication prescriptions
5. No dosage recommendations
6. No unsupported investigation orders
7. Appropriate emergency handling
8. No invented medical history
9. No invented test results
10. No invented hospital information
11. Understandability
12. Appropriate length
13. Relevant content only

---

## 9. Appointment Workflow

1. Reviewer approves the response and identifies the department
2. Appointment Agent queries MCP server for available slots
3. UI displays available doctors and slots by date/time
4. User selects a preferred slot
5. User must **explicitly confirm** via a confirmation button
6. No automatic booking occurs — hospital team confirms directly

---

## 10. Project Structure

```
hospital_autogen_agent/
├── app.py                          # Streamlit UI
├── hospital_customer_care/
│   ├── __init__.py
│   ├── hospital_mcp_server.py      # FastMCP server
│   ├── requirements.txt
│   ├── .env.example
│   ├── .gitignore
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── intake_agent.py         # Patient Intake Agent
│   │   ├── manager_agent.py        # Manager/Router Agent
│   │   ├── specialist_agents.py    # 5 Specialist Agents
│   │   ├── clinical_support_agent.py
│   │   ├── reviewer_agent.py       # Safety Gate
│   │   └── appointment_agent.py    # MCP-connected
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py              # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── model_client.py         # LLM client factory
│   │   ├── memory.py               # Session memory
│   │   └── orchestration.py        # Workflow controller
│   ├── data/
│   │   └── mock_hospital_data.json # Mock hospital data
│   └── tests/
│       ├── __init__.py
│       ├── test_routing.py
│       ├── test_intake.py
│       ├── test_safety.py
│       └── test_review.py
```

---

## 11. Environment Setup

```bash
# Clone the repository
git clone <repo-url>
cd hospital_autogen_agent

# Create virtual environment
python3.10 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r hospital_customer_care/requirements.txt

# Configure environment
cp hospital_customer_care/.env.example .env
# Edit .env and set your OPENAI_API_KEY and OPENAI_MODEL
```

---

## 12. Installation

```bash
pip install autogen-agentchat==0.7.5 autogen-core==0.7.5 "autogen-ext[openai,mcp]==0.7.5"
pip install streamlit pydantic python-dotenv mcp
pip install pytest pytest-asyncio
```

---

## 13. Running Streamlit

```bash
# From the project root (hospital_autogen_agent/)
cd hospital_autogen_agent
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## 14. Running the MCP Server

The MCP server runs automatically via stdio when the Appointment Agent invokes it. To test it manually:

```bash
python3.10 hospital_customer_care/hospital_mcp_server.py
```

---

## 15. Testing

```bash
# From the project root
cd hospital_autogen_agent
python3.10 -m pytest hospital_customer_care/tests/ -v
```

Tests cover:
- Department routing (NEURO/ORTHO/NEPHRO/DENTAL/CARDIO)
- Out-of-scope detection
- Emergency detection
- Intake data extraction and parsing
- Department allowlist enforcement
- Reviewer safety parsing
- Reviewer fallback responses
- Clinical recommendation urgency escalation
- Appointment slot models
- Explicit booking confirmation requirement

---

## 16. Example Conversation

**User:** "I have a headache on the right side for two days."

**Intake Agent:** "I'm sorry to hear you're experiencing that. Could you tell me a bit more — how severe would you rate the pain on a scale of 1 to 10, and have you noticed any symptoms like nausea, sensitivity to light, or vision changes?"

**User:** "About 6 out of 10. I do feel nauseous and light bothers me."

**Intake Agent:** "Thank you. Do you have any known medical conditions or are you currently taking any medications? Also, have you had similar headaches before?"

**User:** "I have high blood pressure and I take amlodipine. I've had headaches before but not like this."

*[Intake completes — routes to workflow]*

**Care Recommendation (Reviewer-approved):**
> "Based on the information you provided, a consultation with our Neurology team would be appropriate.
>
> Your one-sided headache with nausea and light sensitivity, combined with your history of hypertension, is something the neurologist will want to evaluate carefully.
>
> **Please bring to your appointment:**
> - List of current medications (including amlodipine)
> - Any previous blood pressure readings
> - Record of previous similar headaches
>
> **Your doctor may consider** (this is for discussion at the appointment):
> - Blood pressure monitoring
> - Discuss with your doctor whether any blood tests or imaging are appropriate after clinical examination
>
> **Available Neurology appointments:**
> - 25 Sep — Dr. Priya Sharma — 10:30 AM
> - 25 Sep — Dr. Priya Sharma — 3:00 PM
> - 26 Sep — Dr. Robert Chen — 11:00 AM
>
> ⚠️ If your headache suddenly becomes much worse, or you develop any vision changes, weakness, difficulty speaking, or other severe symptoms, please seek emergency care immediately."

---

## 17. Security Considerations

- API keys loaded exclusively from environment variables (never hardcoded)
- `.env` file excluded from version control via `.gitignore`
- MCP tool arguments validated against allowlists (department codes, doctor IDs)
- No arbitrary shell command execution from tool calls
- No real patient data stored anywhere
- Reviewer gate ensures no unsafe content reaches patients
- Structured logging does not include sensitive patient information or credentials
- `DEBUG_MODE=false` in production suppresses verbose logs

---

## 18. Healthcare Limitations

This is an **educational customer-care prototype**, not a clinical system. It:

- ❌ Does NOT diagnose diseases
- ❌ Does NOT prescribe medications
- ❌ Does NOT recommend specific medication dosages
- ❌ Does NOT autonomously order medical tests
- ❌ Is NOT validated for clinical use
- ❌ Does NOT replace a qualified healthcare professional
- ❌ Is NOT HIPAA/GDPR compliant (prototype only)
- ❌ Does NOT store patient data persistently

For production healthcare use, this system would require:
- Clinical validation and regulatory approval
- Full HIPAA/GDPR compliance
- Encrypted patient data storage with access control
- Audit logging
- Integration with real EHR systems
- Medical professional oversight
- Appropriate professional indemnity

---

## 19. Future Enhancements

- [ ] Persistent encrypted patient session storage (SQLite + encryption → PostgreSQL)
- [ ] Real EHR integration via HL7 FHIR
- [ ] Telemedicine video consultation booking
- [ ] Multi-language support
- [ ] Voice input/output interface
- [ ] Real appointment booking (with confirmation workflow)
- [ ] Patient portal login (OAuth2 / SAML)
- [ ] Audit logging with compliance reporting
- [ ] Fine-tuned safety classifier layer
- [ ] Integration with real hospital scheduling systems
- [ ] Follow-up reminders
- [ ] Post-consultation feedback collection
