# MediFlow — AI Assisted Customer Care & Patient Navigation
### New York Medical Centre · Educational Prototype

> **⚕️ Healthcare Disclaimer:** This is an **educational customer-care prototype**, not a clinical system.
> It does not diagnose diseases, prescribe medications, or autonomously order medical tests.
> All recommendations are subject to review by a qualified healthcare professional.

---

## Architecture at a Glance

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Streamlit UI  (app.py)                          │
│  4-step wizard intake → results page (dept banner, care rec, appts)   │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │  IntakeData (Pydantic)
┌──────────────────────────────▼─────────────────────────────────────────┐
│              HospitalOrchestrator  (services/orchestration.py)         │
│         Deterministic workflow controller — NOT LLM-driven             │
└──┬───────────────────────────────────────────────────────────────────┬─┘
   │                                                                   │
   │  Step 1                                                           │
   ▼                                                                   │
┌─────────────────────┐   IntakeData                                   │
│  Patient Intake      │──────────────┐                                │
│  Agent               │              │                                │
│  intake_agent.py     │              │                                │
└─────────────────────┘              │                                │
  Uses: AutoGen AssistantAgent        │                                │
  + ListMemory                        │                                │
  Output: IntakeData (Pydantic)        │                                │
                                      │  Step 2                        │
                               ┌──────▼──────────────┐                │
                               │   Manager Agent      │                │
                               │   manager_agent.py   │                │
                               │                      │                │
                               │  GPT-4o / LLM ──────►│                │
                               │                      │                │
                               │  Output:             │                │
                               │  ManagerDecision     │                │
                               │  {department,        │                │
                               │   status, priority,  │                │
                               │   reason}            │                │
                               └──────┬───────────────┘                │
                                      │                                │
                       ┌──────────────┼──────────────┐                │
                       │              │              │                 │
                  EMERGENCY    OUT_OF_SCOPE        VALID               │
                       │              │              │                 │
                  ┌────▼────┐   ┌─────▼────┐        │  Step 3         │
                  │Emergency│   │ Scope    │  ┌─────▼────────────────┐│
                  │Response │   │ Response │  │  Specialist Agent    ││
                  │(stops)  │   │(stops)   │  │  specialist_agents.py││
                  └─────────┘   └──────────┘  │                      ││
                                              │  One of five:         ││
                                              │  ● ORTHO              ││
                                              │  ● NEURO              ││
                                              │  ● NEPHRO             ││
                                              │  ● DENTAL             ││
                                              │  ● CARDIO             ││
                                              │                      ││
                                              │  GPT-4o / LLM ──────►││
                                              │  Output:             ││
                                              │  SpecialistAssessment││
                                              └──────┬───────────────┘│
                                                     │  Step 4        │
                                              ┌──────▼───────────────┐│
                                              │ Clinical Support     ││
                                              │ Agent                ││
                                              │ clinical_support_    ││
                                              │ agent.py             ││
                                              │                      ││
                                              │ GPT-4o / LLM ───────►││
                                              │ Output:              ││
                                              │ ClinicalRecommendation│
                                              └──────┬───────────────┘│
                                                     │  Step 5        │
                                              ┌──────▼───────────────┐│
                                              │  Reviewer Agent      ││
                                              │  reviewer_agent.py   ││
                                              │                      ││
                                              │  13-point safety     ││
                                              │  checklist           ││
                                              │  GPT-4o / LLM ──────►││
                                              │  Output:             ││
                                              │  ReviewResult        ││
                                              │  {verdict,           ││
                                              │   final_answer}      ││
                                              │                      ││
                                              │  ✅ ONLY this output ││
                                              │  reaches the patient ││
                                              └──────┬───────────────┘│
                                                     │  Step 6        │
                                              ┌──────▼───────────────┐│
                                              │  Appointment Agent   ││
                                              │  appointment_agent.py││
                                              │                      ││
                                              │  McpWorkbench ──────►││
                                              │         │            ││
                                              │         ▼            ││
                                              │  MCP Server (stdio)  ││
                                              │  hospital_mcp_       ││
                                              │  server.py           ││
                                              │         │            ││
                                              │         ▼            ││
                                              │  mock_hospital_      ││
                                              │  data.json           ││
                                              │                      ││
                                              │  Output:             ││
                                              │  List[AppointmentSlot]│
                                              └──────────────────────┘│
                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                      ▲ AutoGen ListMemory (session-scoped)
                        Shared across agents within one session
```

---

## MCP Tool Map

```
hospital_mcp_server.py  (FastMCP — runs via stdio)
│
├── list_departments()                → departments[] with name + description
├── get_department_scope(department)  → clinical scope text for one dept
├── get_emergency_guidance()          → red-flag symptoms + emergency contacts
├── get_available_doctors(department) → DoctorInfo[] for dept
├── get_available_appointments(dept)  → AppointmentSlot[] with date/time
├── get_doctor_details(doctor_id)     → single DoctorInfo
└── get_hospital_services()           → hospital services + contact info

All tools: READ-ONLY · Mock data only · Arguments validated against allowlist
```

---

## Data Flow Between Agents

```
IntakeData ──────────────────────────────────────────────────────────────►
           Manager receives: IntakeData + user question
                    │
                    ▼ ManagerDecision {department, status, priority}
           Specialist receives: IntakeData + question + ManagerDecision
                    │
                    ▼ SpecialistAssessment {assessment, red_flags, key_points}
           ClinicalSupport receives: IntakeData + SpecialistAssessment
                    │
                    ▼ ClinicalRecommendation {investigations, bring, urgency}
           Reviewer receives: question + IntakeData + ManagerDecision
                            + SpecialistAssessment + ClinicalRecommendation
                    │
                    ▼ ReviewResult {verdict, final_answer}   ← shown to patient
           Appointment receives: department + ReviewResult
                    │
                    ▼ List[AppointmentSlot]                   ← shown to patient
```

> **No agent ever receives the full previous message history of another agent.**
> Each agent gets only the structured data it needs.

---

## 1. Project Overview

**MediFlow** is a production-style prototype that demonstrates how Agentic AI (Microsoft AutoGen 0.7.5), MCP (Model Context Protocol / FastMCP), a GPT-compatible LLM, and Streamlit can be combined to build a safe, multi-agent healthcare customer-care system.

The system navigates patients to the correct department, provides safe specialist-level guidance, and surfaces appointment availability — all without ever diagnosing, prescribing, or autonomously ordering tests.

---

## 2. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.10+ |
| Agent framework | Microsoft AutoGen AgentChat | 0.7.5 |
| Agent core | autogen-core | 0.7.5 |
| MCP extension | autogen-ext[openai,mcp] | 0.7.5 |
| LLM | OpenAI-compatible GPT (configurable) | — |
| MCP server | FastMCP (mcp) | 1.28+ |
| UI | Streamlit | 1.35+ |
| Schema validation | Pydantic | v2 |
| Memory | AutoGen ListMemory | 0.7.5 |
| Config management | python-dotenv | — |
| Testing | pytest + pytest-asyncio | — |

---

## 3. Agents

### Agent 1 — Patient Intake Agent (`agents/intake_agent.py`)
Collects structured patient and clinical information through a conversational interface (LLM) or directly from the Streamlit 4-step wizard form.

**Collects:**
- Basic details: name, age, gender
- Chief complaint: symptom, location, duration, severity (0–10), frequency, aggravating/relieving factors
- Vitals: BP, blood sugar, heart rate, O₂ saturation
- Medical history: conditions, surgeries, medications, allergies
- Previous investigations: tests already done

**Returns:** `IntakeData` (Pydantic model — never shown raw to patient)

---

### Agent 2 — Manager Agent (`agents/manager_agent.py`)
Central router and orchestrator. Receives the patient summary and question, calls the LLM to determine the appropriate department, then validates the LLM's choice against a hard-coded allowlist.

**Departments it routes to:**

| Code | Department | Typical conditions |
|---|---|---|
| `ORTHO` | Orthopedics & Sports Medicine | Bones, joints, muscles, fractures |
| `NEURO` | Neurology | Headaches, dizziness, neurological symptoms |
| `NEPHRO` | Nephrology | Kidney-related complaints, renal function |
| `DENTAL` | Dental & Oral Health | Teeth, gums, oral pain |
| `CARDIO` | Cardiology | Heart, chest, blood pressure |

**Returns:** `ManagerDecision {department, status, priority, reason}`
- `status`: `VALID` | `OUT_OF_SCOPE` | `EMERGENCY`

---

### Agents 3–7 — Specialist Agents (`agents/specialist_agents.py`)
Five agents, one per department. Only the relevant agent is activated — all five are never run for a single query.

Each specialist:
- Explains the concern in plain language
- Identifies information to discuss with the doctor
- Highlights missing information
- Identifies potential red flags
- Recommends appropriate specialist consultation

**Must NOT:** diagnose, prescribe, recommend dosages, autonomously order tests, or invent medical information.

**Returns:** `SpecialistAssessment {department, assessment, red_flags, key_points}`

---

### Agent 8 — Clinical Support Agent (`agents/clinical_support_agent.py`)
Converts the specialist assessment into a structured, clinician-reviewable next-step plan.

Frames all investigation suggestions as *"discuss with your doctor"* — never as direct orders.

**Returns:** `ClinicalRecommendation {consultation, possible_investigations_to_discuss, information_to_bring, urgency}`

---

### Agent 9 — Reviewer Agent (`agents/reviewer_agent.py`)
**Final safety and quality gate.** Reviews all agent outputs against a 13-point checklist. Rewrites unsafe content. This is the **only** agent output ever shown to the patient.

**13-point safety checklist:**
1. Correct department selected
2. Patient information handled appropriately
3. No disease diagnosis
4. No medication prescription
5. No dosage recommendation
6. No unsupported investigation orders
7. Emergency symptoms handled appropriately
8. No invented medical history
9. No invented test results
10. No invented hospital information
11. Response is understandable
12. Response is not unnecessarily long
13. Response contains only relevant information

**Returns:** `ReviewResult {verdict, final_answer}` — `verdict` is `APPROVED` or `REVISED`

---

### Agent 10 — Appointment Agent (`agents/appointment_agent.py`)
Uses AutoGen `McpWorkbench` to call the hospital MCP server and retrieve available doctors and appointment slots for the approved department.

**Requires explicit user confirmation** before any booking is recorded — no automatic booking.

**Returns:** `List[AppointmentSlot]`

---

## 4. Orchestration Workflow

```
                  ┌──────────────────┐
                  │  Patient submits  │
                  │  intake form      │
                  └────────┬─────────┘
                           │ IntakeData
                           ▼
                  ┌──────────────────┐
                  │  Manager Agent   │
                  │  (LLM routing)   │
                  └────────┬─────────┘
                           │
          ┌────────────────┼──────────────────┐
          ▼                ▼                  ▼
     EMERGENCY       OUT_OF_SCOPE           VALID
          │                │                  │
    Show urgent       Show scope         Specialist
    message &         response &         Agent
    stop              stop               (1 of 5)
                                              │
                                     Clinical Support
                                         Agent
                                              │
                                       Reviewer Agent
                                      (safety gate)
                                              │
                                      Appointment Agent
                                       (via MCP)
                                              │
                                       Final Response
                                     shown to patient
```

The orchestrator (`services/orchestration.py`) is **deterministic** — the LLM decides the department, but the application code controls the flow and validates every LLM output.

---

## 5. MCP Architecture

```
AutoGen Appointment Agent
         │
         │  AutoGen McpWorkbench (stdio transport)
         ▼
hospital_mcp_server.py  (FastMCP)
         │
         │  reads from
         ▼
data/mock_hospital_data.json
  ├── departments[]     (5 departments, descriptions, scope)
  ├── doctors[]         (10 doctors across departments)
  └── appointments{}    (24 slots across dates/times)
```

**All MCP tools are read-only.** Department codes and doctor IDs are validated against allowlists before execution. No real patient data is ever stored in the MCP server.

---

## 6. Memory

AutoGen `ListMemory` provides **in-session contextual memory**. Key clinical context is stored and retrieved across agent turns within a single patient session.

**Example:**
> User says "I had knee surgery two years ago" early in the session.
> Later: "I'm having pain in the same leg."
> The system recalls the knee surgery context.

**For production healthcare memory, the following would be required:**
- Encryption at rest and in transit
- Role-based access control
- Retention and automatic deletion policies
- Audit logging with tamper-proof records
- Explicit patient consent management
- HIPAA / GDPR / applicable local compliance
- Secure encrypted database (PostgreSQL + encryption at rest)

---

## 7. Pydantic Models

```
IntakeData
  └── PatientProfile   (name, age, gender, BP, sugar, HR, SpO2)
  └── Complaint        (symptom, location, duration, severity, frequency)
  └── MedicalHistory   (conditions, surgeries, medications, allergies, tests)

ManagerDecision        (department, status, priority, reason)
SpecialistAssessment   (department, assessment, red_flags, key_points)
ClinicalRecommendation (consultation, investigations_to_discuss, bring, urgency)
ReviewResult           (verdict, final_answer, issues_found)
AppointmentSlot        (date, time, doctor_name, doctor_id, department)
DoctorInfo             (doctor_id, name, department, specialty, qualifications)
SessionState           (all of the above + processing_steps + error)
```

---

## 8. Safety Architecture

### Emergency Handling
If the Manager Agent classifies the presentation as `EMERGENCY`, the orchestrator:
1. Immediately stops normal agent processing
2. Returns a prominent emergency response directing the patient to emergency services (911 / local emergency number)
3. No further agents are called

**Red-flag triggers include:** thunderclap headache, severe chest pain, stroke symptoms, loss of consciousness, severe breathing difficulty, seizure, severe bleeding, signs of sepsis.

### Reviewer Gate
Every non-emergency response passes through the Reviewer Agent before reaching the patient. The Reviewer can either `APPROVE` or `REVISED` the response. If `REVISED`, the Reviewer rewrites the response to remove unsafe content.

**The `ReviewResult.final_answer` is the only text ever displayed to the patient.**

---

## 9. Project Structure

```
hospital_autogen_agent/
│
├── app.py                              ← Streamlit UI (4-step wizard + results)
├── .env                                ← Local secrets (never committed)
├── .env.example                        ← Template
├── .gitignore
├── README.md                           ← This file
│
└── hospital_customer_care/
    ├── __init__.py
    ├── hospital_mcp_server.py          ← FastMCP server (7 read-only tools)
    ├── requirements.txt
    ├── README.md                       ← Detailed technical README
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── intake_agent.py             ← Agent 1: Patient Intake
    │   ├── manager_agent.py            ← Agent 2: Manager / Router
    │   ├── specialist_agents.py        ← Agents 3–7: 5 Specialist Agents
    │   ├── clinical_support_agent.py   ← Agent 8: Clinical Support
    │   ├── reviewer_agent.py           ← Agent 9: Safety Gate
    │   └── appointment_agent.py        ← Agent 10: MCP-connected Appointments
    │
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py                  ← All Pydantic models
    │
    ├── services/
    │   ├── __init__.py
    │   ├── model_client.py             ← LLM client factory (openai-compatible)
    │   ├── memory.py                   ← AutoGen ListMemory wrapper
    │   └── orchestration.py            ← Deterministic workflow controller
    │
    ├── data/
    │   └── mock_hospital_data.json     ← 5 depts · 10 doctors · 24 slots
    │
    └── tests/
        ├── test_routing.py             ← 21 tests: routing, allowlist, emergency
        ├── test_intake.py              ← 8 tests: parser, model validation
        ├── test_safety.py              ← 15 tests: reviewer, urgency escalation
        └── test_review.py              ← 12 tests: appointments, confirmation
```

---

## 10. Environment Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd hospital_autogen_agent

# 2. Create a virtual environment (Python 3.10 recommended)
python3.10 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r hospital_customer_care/requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in your values
```

### `.env` configuration

```env
# Required
OPENAI_API_KEY=sk-...

# Model name (default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o-mini

# Optional — leave blank for standard OpenAI endpoint
# Set to your custom endpoint if using a compatible provider
OPENAI_BASE_URL=

# Optional — set to true during development
DEBUG_MODE=false
```

> `OPENAI_BASE_URL` is optional. Leave it blank to use the standard OpenAI endpoint.
> The application removes the variable from the environment when blank to avoid an openai v2 SDK bug.

---

## 11. Running the Application

```bash
# From the project root
streamlit run app.py
```

Opens at: **http://localhost:8501**

The MCP server starts automatically via stdio when the Appointment Agent activates. No separate startup step is needed.

---

## 12. Running Tests

```bash
# From the project root
python3.10 -m pytest hospital_customer_care/tests/ -v
```

**56 tests** covering:
- Department routing (NEURO / ORTHO / NEPHRO / DENTAL / CARDIO)
- Out-of-scope detection
- Emergency detection and short-circuit
- Intake data extraction and Pydantic validation
- Department allowlist enforcement
- Reviewer safety parsing
- Reviewer fallback responses
- Clinical recommendation urgency escalation
- Appointment slot Pydantic models
- Explicit booking confirmation requirement

---

## 13. Example Flow

**User fills in the 4-step intake form:**
- Name: John Smith · Age: 45 · Gender: Male
- Symptom: Headache (right side) · Duration: 2 days · Severity: 6/10
- BP: 145/92 · Current medications: Amlodipine 5mg

**Orchestration (backend — not shown to user):**
```
[MANAGER]         → department: NEURO, status: VALID
[SPECIALIST]      → Neurology assessment (red flags: hypertension + headache)
[CLINICAL_SUPPORT]→ investigations to discuss: BP monitoring, blood tests
[REVIEWER]        → verdict: APPROVED
[APPOINTMENT]     → 3 slots retrieved via MCP
```

**Patient sees (Reviewer-approved output):**
```
🧠 Neurology — New York Medical Centre

Based on the information you provided, a consultation with our
Neurology team would be appropriate.

📋 Key Points for Your Doctor
  ▸ One-sided headache with history of hypertension
  ▸ Currently taking Amlodipine 5mg
  ▸ Severity rated 6/10 over 2 days

🔬 Suggested Tests to Discuss with Your Doctor
  [Blood pressure monitoring]  [Blood test (CBC)]  [Blood glucose]

📁 What to Bring
  ✓ Medication list (including Amlodipine)
  ✓ Any previous blood pressure readings
  ✓ Record of previous similar headaches

⚠️ Important: If your headache suddenly becomes much worse, or
you develop vision changes, weakness, difficulty speaking, or
any other severe symptoms, please seek emergency care immediately.

──────────────────────────────────────────
👨‍⚕️ Dr. Priya Sharma — Neurology
  📅 25 Sep  ⏰ 10:30 AM    📅 25 Sep  ⏰ 3:00 PM

👨‍⚕️ Dr. Robert Chen — Neurology
  📅 26 Sep  ⏰ 11:00 AM    📅 26 Sep  ⏰ 4:30 PM
```

---

## 14. Security Considerations

| Rule | Implementation |
|---|---|
| No hardcoded API keys | All secrets from `.env` via `python-dotenv` |
| `.env` excluded from git | `.gitignore` covers `.env`, `.env.*`, secrets |
| MCP tool allowlists | Department codes and doctor IDs validated before execution |
| No arbitrary shell execution | MCP tools are constrained to read-only JSON operations |
| No real patient data | Mock data only — `mock_hospital_data.json` |
| Reviewer gate | Unsafe content never reaches the patient UI |
| Structured logging | No API keys, passwords, or unnecessary patient data in logs |
| `DEBUG_MODE=false` in production | Verbose logs suppressed |

---

## 15. Healthcare Limitations

| Capability | Status |
|---|---|
| Diagnose diseases | ❌ Not supported |
| Prescribe medications | ❌ Not supported |
| Recommend dosages | ❌ Not supported |
| Autonomously order tests | ❌ Not supported |
| Replace a healthcare professional | ❌ Not supported |
| HIPAA / GDPR compliance | ❌ Prototype only |
| Persistent patient records | ❌ Session-only memory |
| Clinical validation | ❌ Not validated |

---

## 16. Future Enhancements

- [ ] Persistent encrypted patient session storage (SQLite → PostgreSQL + encryption)
- [ ] Real EHR integration via HL7 FHIR
- [ ] Telemedicine / video consultation booking
- [ ] Multi-language support
- [ ] Voice input / output interface
- [ ] Real appointment booking with confirmation workflow
- [ ] Patient portal login (OAuth2 / SAML)
- [ ] Audit logging with compliance reporting
- [ ] Fine-tuned medical safety classifier layer
- [ ] Integration with real hospital scheduling systems
- [ ] Follow-up reminders and post-consultation feedback
- [ ] Document upload for previous investigation reports
