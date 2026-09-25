"""
MediFlow AI Assisted Customer Care — New York Medical Centre
Streamlit Application — app.py

Run:
    cd hospital_autogen_agent
    streamlit run app.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_ROOT / ".env", override=False)

_DEBUG = os.environ.get("DEBUG_MODE", "false").lower() == "true"
logging.basicConfig(
    level=logging.DEBUG if _DEBUG else logging.ERROR,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

import streamlit as st

st.set_page_config(
    page_title="MediFlow — New York Medical Centre",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from hospital_customer_care.services.orchestration import HospitalOrchestrator
    from hospital_customer_care.models.schemas import (
        AppointmentSlot,
        Complaint,
        IntakeData,
        MedicalHistory,
        PatientProfile,
        SessionState,
    )
except ImportError as exc:
    st.error(f"❌ Import error: {exc}\n\nInstall: `pip install -r hospital_customer_care/requirements.txt`")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,400;0,500;0,600;0,700;0,800;1,400&display=swap');

  /* ═══════════════════════════════════════════════════════
     CSS CUSTOM PROPERTIES — light mode defaults
     ═══════════════════════════════════════════════════════ */
  :root {
    --bg:            #ffffff;
    --bg-surface:    #f7f9fc;
    --bg-card:       #ffffff;
    --border:        #dae5f2;
    --border-soft:   #e8edf5;
    --text-primary:  #1a202c;
    --text-body:     #2d3748;
    --text-muted:    #4a5568;
    --text-faint:    #718096;
    --accent:        #0f2d4e;
    --accent-mid:    #1e5280;
    --accent-light:  #2b6cb0;
    --link:          #3182ce;
    --divider:       #e2e8f0;
    --row-border:    #f0f4f8;

    /* Cards */
    --card-info-bg:     #ebf8ff;
    --card-info-border: #90cdf4;
    --card-info-text:   #1a365d;
    --card-ok-bg:       #f0fff4;
    --card-ok-border:   #9ae6b4;
    --card-ok-text:     #1a3a2a;
    --card-warn-bg:     #fffbeb;
    --card-warn-border: #f6ad55;
    --card-warn-text:   #744210;
    --card-err-bg:      #fff3f3;
    --card-err-border:  #e53e3e;
    --card-err-text:    #742a2a;

    /* Wizard */
    --wiz-dot-bg:       #ffffff;
    --wiz-dot-border:   #bee3f8;
    --wiz-dot-color:    #a0aec0;
    --wiz-label-color:  #718096;
    --wiz-label-active: #0f2d4e;
    --wiz-conn:         #bee3f8;

    /* Pills */
    --pill-bg:     #ebf8ff;
    --pill-border: #bee3f8;
    --pill-text:   #1a5276;

    /* Doc card */
    --doc-bg:     #ffffff;
    --doc-border: #bee3f8;
    --doc-name:   #0f2d4e;
    --doc-spec:   #4a5568;

    /* Steps bar */
    --step-done: #276749;
    --step-wait: #a0aec0;
  }

  /* ═══════════════════════════════════════════════════════
     DARK MODE OVERRIDES
     ═══════════════════════════════════════════════════════ */
  @media (prefers-color-scheme: dark) {
    :root {
      --bg:            #0e1117;
      --bg-surface:    #1a1f2e;
      --bg-card:       #1e2535;
      --border:        #2d3a52;
      --border-soft:   #2a3448;
      --text-primary:  #e8edf5;
      --text-body:     #d1d9e6;
      --text-muted:    #a0aec0;
      --text-faint:    #8892a4;
      --accent:        #63b3ed;
      --accent-mid:    #90cdf4;
      --accent-light:  #63b3ed;
      --link:          #63b3ed;
      --divider:       #2d3a52;
      --row-border:    #2a3448;

      --card-info-bg:     #1a2840;
      --card-info-border: #2c5282;
      --card-info-text:   #90cdf4;
      --card-ok-bg:       #1a2e22;
      --card-ok-border:   #276749;
      --card-ok-text:     #9ae6b4;
      --card-warn-bg:     #2d2010;
      --card-warn-border: #c05621;
      --card-warn-text:   #fbd38d;
      --card-err-bg:      #2d1515;
      --card-err-border:  #e53e3e;
      --card-err-text:    #feb2b2;

      --wiz-dot-bg:       #1e2535;
      --wiz-dot-border:   #2d4a6e;
      --wiz-dot-color:    #8892a4;
      --wiz-label-color:  #a0aec0;
      --wiz-label-active: #90cdf4;
      --wiz-conn:         #2d4a6e;

      --pill-bg:     #1a2840;
      --pill-border: #2c5282;
      --pill-text:   #90cdf4;

      --doc-bg:     #1e2535;
      --doc-border: #2d4a6e;
      --doc-name:   #90cdf4;
      --doc-spec:   #a0aec0;

      --step-done: #68d391;
      --step-wait: #4a5568;
    }
  }

  /* ── Base ─────────────────────────────────────────── */
  .main .block-container {
    padding-top: 0.6rem; max-width: 860px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 1.05rem;
  }
  p, li, label, div { font-size: 1.05rem !important; }
  h3 {
    color: var(--accent-mid); font-size: 1.15rem !important;
    font-weight: 700; margin: 0.8rem 0 0.3rem;
  }
  h4 { color: var(--text-primary) !important; }

  /* ── BRAND HERO ──────────────────────────────────── */
  .brand-hero {
    background: linear-gradient(120deg, #0a1f35 0%, #0f2d4e 55%, #1a4a7a 100%);
    border-radius: 18px; padding: 2rem 2.4rem 1.8rem;
    margin-bottom: 0.4rem;
    box-shadow: 0 4px 24px rgba(10,31,53,0.35);
  }
  .brand-hero .mf-wordmark {
    font-size: 2.9rem; font-weight: 800; color: #ffffff;
    letter-spacing: -1.5px; line-height: 1;
    text-shadow: 0 2px 8px rgba(0,0,0,0.35);
  }
  .brand-hero .mf-wordmark span { color: #63b3ed; }
  .brand-hero .mf-tagline {
    font-size: 1.08rem; font-weight: 500; color: #90cdf4;
    margin-top: 0.35rem; letter-spacing: 0.3px;
  }
  .brand-hero .mf-hospital {
    display: inline-block; margin-top: 0.75rem;
    background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.22);
    border-radius: 30px; padding: 0.22rem 0.9rem;
    font-size: 0.82rem; font-weight: 600; color: #e2e8f0;
    text-transform: uppercase; letter-spacing: 1.3px;
  }
  .brand-hero .mf-pulse {
    display: inline-block; width: 7px; height: 7px;
    background: #68d391; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
    box-shadow: 0 0 0 3px rgba(104,211,145,0.3);
  }

  /* ── Wizard progress bar ──────────────────────────── */
  .wiz-bar {
    display: flex; align-items: center; gap: 0; margin: 1.4rem 0 1.8rem;
  }
  .wiz-step { flex: 1; text-align: center; position: relative; }
  .wiz-step-dot {
    width: 34px; height: 34px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 0.85rem; font-weight: 700;
    border: 2px solid var(--wiz-dot-border);
    background: var(--wiz-dot-bg);
    color: var(--wiz-dot-color);
    position: relative; z-index: 2;
  }
  .wiz-step-dot.done   { background: #276749; border-color: #276749; color: #ffffff; }
  .wiz-step-dot.active { background: #1a4a7a; border-color: #63b3ed; color: #ffffff; }
  .wiz-step-label {
    display: block; font-size: 0.75rem;
    color: var(--wiz-label-color);
    margin-top: 4px; font-weight: 500;
  }
  .wiz-step-label.active { color: var(--wiz-label-active); font-weight: 700; }
  .wiz-connector {
    flex: 1; height: 2px;
    background: var(--wiz-conn);
    margin: 0 -2px; margin-top: -16px;
    position: relative; z-index: 1;
  }
  .wiz-connector.done { background: #276749; }

  /* ── Form field labels ────────────────────────────── */
  .stTextInput label, .stSelectbox label,
  .stMultiSelect label, .stRadio label,
  .stSlider label, .stTextArea label {
    font-size: 1rem !important; font-weight: 600 !important;
  }

  /* ── Page heading ─────────────────────────────────── */
  .page-heading {
    font-size: 1.35rem; font-weight: 700;
    color: var(--accent);
    margin: 0 0 0.2rem; letter-spacing: -0.3px;
  }
  .page-sub {
    font-size: 1rem; color: var(--text-muted); margin-bottom: 1.4rem;
  }

  /* ── Department banner ────────────────────────────── */
  .dept-banner {
    background: linear-gradient(135deg, #0f2d4e 0%, #1e5280 100%);
    color: #ffffff; border-radius: 14px; padding: 1.4rem 2rem;
    margin: 1rem 0; text-align: center;
  }
  .dept-banner .db-label {
    font-size: 0.78rem; color: rgba(255,255,255,0.78);
    text-transform: uppercase; letter-spacing: 1.4px; margin-bottom: 0.3rem;
  }
  .dept-banner .db-name { font-size: 1.75rem; font-weight: 800; margin: 0.2rem 0; color: #ffffff; }
  .dept-banner .db-desc { font-size: 0.95rem; color: rgba(255,255,255,0.88); }

  /* ── Care card ────────────────────────────────────── */
  .care-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-radius: 14px; padding: 1.6rem 1.8rem; margin-bottom: 1.1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  }
  .care-card h4 {
    color: var(--accent) !important; font-size: 1.12rem !important; font-weight: 700;
    margin: 0 0 1rem 0; padding-bottom: 0.65rem;
    border-bottom: 2px solid var(--border);
  }
  .cr-section {
    margin: 1.1rem 0 0.45rem;
    font-size: 0.85rem !important; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.9px; color: var(--accent-light);
  }
  .cr-row {
    display: flex; align-items: flex-start; gap: 0.6rem;
    padding: 0.5rem 0; border-bottom: 1px solid var(--row-border);
    font-size: 1rem !important; line-height: 1.6; color: var(--text-body);
  }
  .cr-row:last-child { border-bottom: none; }
  .cr-bullet { color: var(--link); font-size: 1.05rem !important; flex-shrink: 0; margin-top: 2px; }
  .cr-text   { flex: 1; color: var(--text-body); }
  .test-pill {
    display: inline-flex; align-items: center; gap: 0.35rem;
    background: var(--pill-bg); border: 1px solid var(--pill-border);
    border-radius: 20px; padding: 0.3rem 0.85rem;
    font-size: 0.9rem !important; color: var(--pill-text);
    margin: 0.25rem 0.25rem 0 0;
  }
  .warning-strip {
    background: var(--card-warn-bg); border-left: 4px solid var(--card-warn-border);
    border-radius: 0 8px 8px 0; padding: 0.7rem 1rem;
    font-size: 0.95rem !important; color: var(--card-warn-text);
    margin-top: 1rem; line-height: 1.55;
  }

  /* ── Emergency card ───────────────────────────────── */
  .emergency-card {
    background: var(--card-err-bg); border: 2px solid var(--card-err-border);
    border-radius: 12px; padding: 1.3rem 1.6rem; margin-bottom: 1rem;
    font-size: 1.02rem !important; line-height: 1.65;
    color: var(--card-err-text);
  }

  /* ── Urgency badge ────────────────────────────────── */
  .urg-routine  { background: #276749; }
  .urg-soon     { background: #b7791f; }
  .urg-urgent   { background: #c05621; }
  .urg-emergency{ background: #c53030; }
  .urg-badge {
    display: inline-flex; align-items: center; gap: 0.3rem;
    border-radius: 20px; color: #ffffff;
    padding: 0.28rem 1rem; font-size: 0.88rem !important; font-weight: 600;
    margin-bottom: 0.5rem;
  }

  /* ── Doctor card ──────────────────────────────────── */
  .doc-card {
    background: var(--doc-bg); border: 1.5px solid var(--doc-border);
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.7rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  }
  .doc-name { font-weight: 700; color: var(--doc-name); font-size: 1.05rem !important; }
  .doc-spec { font-size: 0.9rem !important; color: var(--doc-spec); margin: 0.15rem 0; }

  /* ── Status / info cards ──────────────────────────── */
  .success-card {
    background: var(--card-ok-bg); border: 1px solid var(--card-ok-border);
    border-radius: 10px; padding: 1rem 1.3rem; margin-bottom: 1rem;
    font-size: 1rem !important; line-height: 1.65;
    color: var(--card-ok-text);
  }
  .info-card {
    background: var(--card-info-bg); border: 1px solid var(--card-info-border);
    border-radius: 10px; padding: 1rem 1.3rem; margin-bottom: 1rem;
    font-size: 1rem !important; line-height: 1.6;
    color: var(--card-info-text);
  }

  /* ── Processing step bar ──────────────────────────── */
  .step-done { color: var(--step-done); font-weight: 700; font-size: 0.82rem !important; text-align: center; }
  .step-wait { color: var(--step-wait); font-size: 0.82rem !important; text-align: center; }

  /* ── Disclaimer ───────────────────────────────────── */
  .disclaimer {
    background: var(--card-warn-bg); border: 1px solid var(--card-warn-border);
    border-radius: 8px; padding: 0.8rem 1.1rem;
    font-size: 0.88rem !important; color: var(--card-warn-text);
    margin-top: 1.4rem; line-height: 1.55;
  }

  /* ── Section divider ──────────────────────────────── */
  .shr { border: none; border-top: 1px solid var(--divider); margin: 1.2rem 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Constants / option lists
# ─────────────────────────────────────────────────────────────────────────────
_DEPT_NAMES = {"ORTHO":"Orthopedics & Sports Medicine","NEURO":"Neurology",
               "NEPHRO":"Nephrology","DENTAL":"Dental & Oral Health","CARDIO":"Cardiology"}
_DEPT_ICONS = {"ORTHO":"🦴","NEURO":"🧠","NEPHRO":"🫘","DENTAL":"🦷","CARDIO":"❤️"}
_DEPT_DESC  = {"ORTHO":"Bones, joints, muscles & sports injuries",
               "NEURO":"Headaches, neurological & nerve concerns",
               "NEPHRO":"Kidney & renal health",
               "DENTAL":"Teeth, gums & oral health",
               "CARDIO":"Heart, blood pressure & cardiovascular"}

_URGENCY_CSS = {"ROUTINE":"urg-routine","SOON":"urg-soon","URGENT":"urg-urgent","EMERGENCY":"urg-emergency"}
_URGENCY_LBL = {"ROUTINE":"Routine","SOON":"Schedule soon","URGENT":"⚠️ Urgent","EMERGENCY":"🚨 Emergency"}

_PROCESSING_STEPS = [
    ("manager_complete","Validated & Routed"),
    ("specialist_complete","Specialist Review"),
    ("clinical_support_complete","Next Steps"),
    ("reviewer_complete","Safety Review"),
    ("appointment_complete","Appointments"),
]

# Symptom options per category
_SYMPTOM_OPTIONS = [
    "Select your main symptom...",
    # Musculoskeletal
    "Knee pain","Hip pain","Back pain","Neck pain","Shoulder pain",
    "Wrist / Hand pain","Ankle / Foot pain","Arm pain","Leg pain",
    "Joint swelling","Muscle pain","Fracture / Injury",
    # Neurological
    "Headache","Migraine","Dizziness / Vertigo","Numbness / Tingling",
    "Weakness in limbs","Memory problems","Seizure","Tremor",
    # Cardiac
    "Chest pain","Chest tightness","Palpitations","Breathlessness",
    "High blood pressure","Leg swelling",
    # Renal
    "Kidney pain","Blood in urine","Swollen ankles","Frequent urination",
    "Difficulty urinating","Kidney stones",
    # Dental
    "Toothache","Gum pain","Jaw pain","Mouth sores","Tooth sensitivity",
    "Tooth swelling",
    # Other
    "Other (please describe below)",
]

_GENDER_OPTIONS   = ["Prefer not to say","Male","Female","Other"]
_DURATION_OPTIONS = ["Less than 1 day","1–3 days","4–7 days","1–2 weeks",
                     "2–4 weeks","1–3 months","3–6 months","More than 6 months","Not sure"]
_FREQUENCY_OPTIONS = ["Constant","Intermittent (comes and goes)","Occasional","First time","Not sure"]
_CONDITION_OPTIONS = ["None","Diabetes","Hypertension (High BP)","Heart disease","Kidney disease",
                      "Thyroid disorder","Asthma / COPD","Arthritis","Epilepsy","Cancer",
                      "Previous stroke","Obesity","Other (please describe)"]
_SURGERY_OPTIONS   = ["None","Knee surgery","Hip replacement","Heart surgery","Spine surgery",
                      "Abdominal surgery","Dental procedure","Eye surgery","Brain surgery","Other"]
_ALLERGY_OPTIONS   = ["None","Penicillin","Aspirin / NSAIDs","Sulfa drugs","Latex","Iodine",
                      "Anaesthesia","Food allergies","Other"]
_AGGRAVATING_OPTIONS = ["Not sure","Movement / Walking","Standing for long","Sitting for long",
                        "Bending / Twisting","Eating / Drinking","Stress","Bright light",
                        "Cold weather","Heat","Morning time","Evening / Night","Other"]
_RELIEVING_OPTIONS   = ["Not sure","Rest","Ice pack","Heat pack","Lying down","Sitting still",
                        "After eating","Medication","Pain is constant","Other"]
_TESTS_OPTIONS = ["None","Blood test (CBC)","Blood glucose / Sugar test","HbA1c",
                  "Kidney function test","Liver function test","Lipid profile",
                  "X-ray","CT scan","MRI","Ultrasound","ECG / EKG",
                  "Echocardiogram","Urine test","Dental X-ray","Other"]

# ─────────────────────────────────────────────────────────────────────────────
# Session helpers
# ─────────────────────────────────────────────────────────────────────────────
def _init_session() -> None:
    defaults = {
        "orchestrator":          HospitalOrchestrator(),
        "page":                  "intake",   # intake | results
        "workflow_state":        None,
        "selected_slot":         None,
        "appointment_confirmed": False,
        "error_message":         None,
        # Wizard state
        "intake_step":           1,          # 1–4
        "form_data":             {},         # accumulated across steps
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session() -> None:
    st.session_state.orchestrator.reset()
    st.session_state.page                  = "intake"
    st.session_state.workflow_state        = None
    st.session_state.selected_slot         = None
    st.session_state.appointment_confirmed = False
    st.session_state.error_message         = None
    st.session_state.intake_step           = 1
    st.session_state.form_data             = {}

# ─────────────────────────────────────────────────────────────────────────────
# Async helpers
# ─────────────────────────────────────────────────────────────────────────────
def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=180)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _run_workflow(orch: HospitalOrchestrator, intake: IntakeData):
    steps = []
    async for step, state in orch.run_full_workflow(
        intake.complaint.symptom, intake_data=intake
    ):
        steps.append((step, state))
    return steps

# ─────────────────────────────────────────────────────────────────────────────
# Form helpers
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Build IntakeData from form values
# ─────────────────────────────────────────────────────────────────────────────
def _build_intake_from_form(fd: dict) -> IntakeData:
    """Convert validated form dict → IntakeData Pydantic model."""
    symptom_raw = fd.get("symptom", "")
    symptom = fd.get("symptom_other", symptom_raw) if symptom_raw.lower().startswith("other") else symptom_raw

    age_val = fd.get("age")
    try:
        age = int(age_val) if age_val else None
    except (ValueError, TypeError):
        age = None

    severity = fd.get("severity", 5)

    freq_raw = fd.get("frequency", "Not provided")
    # normalise: strip the parenthetical part
    frequency = freq_raw.split("(")[0].strip() if freq_raw else "Not provided"

    agg_raw  = fd.get("aggravating", [])
    rel_raw  = fd.get("relieving", [])
    agg = ", ".join(agg_raw) if isinstance(agg_raw, list) else str(agg_raw)
    rel = ", ".join(rel_raw) if isinstance(rel_raw, list) else str(rel_raw)

    cond_list = [c for c in fd.get("conditions", []) if c.lower() != "none"]
    surg_list = [s for s in fd.get("surgeries", []) if s.lower() != "none"]
    allergy_list = [a for a in fd.get("allergies", []) if a.lower() != "none"]
    meds_raw = fd.get("medications", "").strip()
    meds = [m.strip() for m in meds_raw.split(",") if m.strip()] if meds_raw else []
    tests_list = [t for t in fd.get("tests", []) if t.lower() != "none"]

    bp = fd.get("bp", "").strip() or "Not provided"
    sugar = fd.get("sugar", "").strip() or "Not provided"

    patient = PatientProfile(
        name=fd.get("name", "Not provided").strip() or "Not provided",
        age=age,
        gender=fd.get("gender", "Not provided"),
        blood_pressure=bp,
        blood_sugar=sugar,
    )
    complaint = Complaint(
        symptom=symptom or "Not provided",
        location=fd.get("location", "Not provided").strip() or "Not provided",
        duration=fd.get("duration", "Not provided"),
        severity=severity,
        frequency=frequency,
        aggravating_factors=agg or "Not provided",
        relieving_factors=rel or "Not provided",
    )
    history = MedicalHistory(
        conditions=cond_list,
        surgeries=surg_list,
        drug_allergies=allergy_list,
        current_medications=meds,
        previous_tests=tests_list,
    )
    # Build a natural-language summary as the "question" for the workflow
    complaint_summary = (
        f"{symptom} in {fd.get('location','')}, "
        f"duration {fd.get('duration','')}, severity {severity}/10, "
        f"frequency {frequency}."
    )
    return IntakeData(
        patient=patient,
        complaint=complaint,
        medical_history=history,
        raw_conversation=complaint_summary,
        intake_complete=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Render: processing steps bar
# ─────────────────────────────────────────────────────────────────────────────
def _render_steps(steps_done: list[str]) -> None:
    cols = st.columns(len(_PROCESSING_STEPS))
    for i, (key, label) in enumerate(_PROCESSING_STEPS):
        with cols[i]:
            css = "step-done" if key in steps_done else "step-wait"
            icon = "✅" if key in steps_done else "⬜"
            st.markdown(
                f'<div class="{css}">{icon}<br>{label}</div>',
                unsafe_allow_html=True,
            )

# ─────────────────────────────────────────────────────────────────────────────
# Render: department banner
# ─────────────────────────────────────────────────────────────────────────────
def _render_dept_banner(state: SessionState) -> None:
    if not state.manager_decision or not state.manager_decision.department:
        return
    code = state.manager_decision.department.value
    st.markdown(
        f'<div class="dept-banner">'
        f'<div class="db-label">Based on your symptoms, we recommend</div>'
        f'<div class="db-name">{_DEPT_ICONS.get(code,"🏥")} {_DEPT_NAMES.get(code,code)}</div>'
        f'<div class="db-desc">{_DEPT_DESC.get(code,"")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Render: care recommendation — structured HTML renderer
# ─────────────────────────────────────────────────────────────────────────────
import re as _re

def _parse_care_sections(text: str) -> dict:
    """
    Parse the reviewer's structured output into keyed sections.
    Handles **Section Title** headings and bullet lines (•, -, *, numbered).
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Detect **Heading** lines
        heading_match = _re.match(r"^\*{1,2}(.+?)\*{1,2}\s*$", line)
        if heading_match:
            current = heading_match.group(1).strip()
            sections.setdefault(current, [])
            continue
        # Detect WARNING / ⚠️ line
        if line.upper().startswith("WARNING") or line.startswith("⚠️"):
            sections.setdefault("_warning", [])
            sections["_warning"].append(line)
            continue
        # Bullet lines
        bullet_match = _re.match(r"^[-•*]\s+(.*)", line)
        numbered_match = _re.match(r"^\d+[.)]\s+(.*)", line)
        if (bullet_match or numbered_match) and current:
            content = (bullet_match or numbered_match).group(1).strip()
            sections[current].append(content)
        elif current and not heading_match:
            # Plain text under a section (e.g. Summary paragraph)
            sections[current].append(line)
    return sections


def _section_html(title: str, items: list[str], icon: str = "●") -> str:
    """Render a care-card section with lined bullet rows."""
    rows = "".join(
        f'<div class="cr-row"><span class="cr-bullet">{icon}</span>'
        f'<span class="cr-text">{item}</span></div>'
        for item in items if item.strip()
    )
    return (
        f'<div class="cr-section">{title}</div>'
        f'{rows}'
    )


def _tests_html(items: list[str]) -> str:
    """Render suggested tests as pill badges."""
    pills = "".join(
        f'<span class="test-pill">🔬 {item}</span>'
        for item in items if item.strip()
    )
    return (
        '<div class="cr-section">🔬 Suggested Tests to Discuss with Your Doctor</div>'
        f'<div style="margin-top:0.4rem;">{pills}</div>'
    )


def _render_care(state: SessionState) -> None:
    if not state.review_result:
        return
    answer = state.review_result.final_answer
    is_emg = state.manager_decision and state.manager_decision.is_emergency()
    if is_emg or "🚨" in answer:
        st.markdown(f'<div class="emergency-card">{answer}</div>', unsafe_allow_html=True)
        return

    sections = _parse_care_sections(answer)

    html_parts = ['<div class="care-card"><h4>💬 Care Recommendation</h4>']

    # Summary — rendered as a plain paragraph, not bullets
    summary_keys = [k for k in sections if "summary" in k.lower()]
    if summary_keys:
        summary_lines = sections[summary_keys[0]]
        summary_text = " ".join(l for l in summary_lines if l)
        if summary_text:
            html_parts.append(
                f'<div style="font-size:1rem;color:#2d3748;line-height:1.6;'
                f'margin-bottom:0.8rem;padding-bottom:0.8rem;'
                f'border-bottom:1px solid #f0f4f8;">{summary_text}</div>'
            )

    # Key Points
    kp_keys = [k for k in sections if "key point" in k.lower() or "doctor" in k.lower()
               and "test" not in k.lower() and "bring" not in k.lower()]
    if kp_keys:
        html_parts.append(_section_html("📋 Key Points for Your Doctor",
                                        sections[kp_keys[0]], icon="▸"))

    # Suggested tests
    test_keys = [k for k in sections if "test" in k.lower() or "invest" in k.lower()]
    if test_keys:
        html_parts.append(_tests_html(sections[test_keys[0]]))

    # What to bring
    bring_keys = [k for k in sections if "bring" in k.lower()]
    if bring_keys:
        html_parts.append(_section_html("📁 What to Bring to Your Appointment",
                                        sections[bring_keys[0]], icon="✓"))

    # Warning strip
    if "_warning" in sections:
        warn_text = " ".join(sections["_warning"])
        # Strip leading "WARNING:" prefix for cleaner display
        warn_text = _re.sub(r"^WARNING\s*:\s*", "", warn_text, flags=_re.IGNORECASE)
        warn_text = warn_text.replace("⚠️", "").strip()
        html_parts.append(
            f'<div class="warning-strip">⚠️ <strong>Important:</strong> {warn_text}</div>'
        )

    # If parsing produced nothing useful, fall back to plain markdown
    if len(html_parts) == 1:
        html_parts.append(
            f'<div style="font-size:0.96rem;line-height:1.65;color:#2d3748;">{answer}</div>'
        )

    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Render: doctors + appointments (combined, below care recommendation)
# ─────────────────────────────────────────────────────────────────────────────
def _render_doctors_and_appointments(state: SessionState) -> None:
    slots = state.available_slots
    if not slots:
        dept = (state.manager_decision.department.value
                if state.manager_decision and state.manager_decision.department else "")
        st.markdown(
            '<div class="info-card">📅 Please call <strong>+1-212-555-0100</strong> '
            f'to schedule a {_DEPT_NAMES.get(dept, dept)} appointment.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="care-card">', unsafe_allow_html=True)
    st.markdown("#### 👨‍⚕️ Available Doctors & Appointment Slots")

    # ── If already confirmed ─────────────────────────────────────────────────
    if st.session_state.appointment_confirmed and st.session_state.selected_slot:
        s = st.session_state.selected_slot
        st.markdown(
            f'<div class="success-card">'
            f"✅ **Appointment request noted!**<br><br>"
            f"**Doctor:** {s.doctor_name}<br>"
            f"**Date:** {s.date} &nbsp;|&nbsp; **Time:** {s.time}<br><br>"
            f"<em>The hospital team will confirm your appointment. "
            f"Please call +1-212-555-0100 to finalise.</em>"
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── Group slots by doctor ────────────────────────────────────────────────
    by_doctor: dict[str, list[AppointmentSlot]] = {}
    for s in slots:
        by_doctor.setdefault(s.doctor_name, []).append(s)

    current_sel = st.session_state.selected_slot

    for doctor_name, doc_slots in by_doctor.items():
        # Doctor info card
        sample = doc_slots[0]
        st.markdown(
            f'<div class="doc-card">'
            f'<div class="doc-name">👨‍⚕️ {doctor_name}</div>'
            f'<div class="doc-spec">🏥 {_DEPT_NAMES.get(sample.department, sample.department)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Slot buttons in columns
        n = min(len(doc_slots), 4)
        cols = st.columns(n)
        for i, slot in enumerate(doc_slots[:4]):
            is_sel = (
                current_sel is not None
                and current_sel.doctor_id == slot.doctor_id
                and current_sel.date == slot.date
                and current_sel.time == slot.time
            )
            with cols[i]:
                btn_label = f"📅 {slot.date}\n⏰ {slot.time}"
                btn_type = "primary" if is_sel else "secondary"
                if st.button(btn_label,
                             key=f"sl_{slot.doctor_id}_{slot.date}_{slot.time}",
                             type=btn_type,
                             use_container_width=True):
                    st.session_state.selected_slot = slot
                    st.rerun()

    # ── Confirm panel ────────────────────────────────────────────────────────
    if current_sel:
        st.markdown('<hr class="shr">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-card">'
            f'<strong>Selected:</strong> {current_sel.doctor_name} — '
            f'{current_sel.date} at {current_sel.time}'
            f'</div>',
            unsafe_allow_html=True,
        )
        col_confirm, col_cancel = st.columns([2, 1])
        with col_confirm:
            if st.button("✅ Confirm Appointment", type="primary", use_container_width=True):
                st.session_state.appointment_confirmed = True
                st.rerun()
        with col_cancel:
            if st.button("✖ Clear Selection", use_container_width=True):
                st.session_state.selected_slot = None
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Render: disclaimer
# ─────────────────────────────────────────────────────────────────────────────
def _render_disclaimer() -> None:
    st.markdown(
        '<div class="disclaimer">⚕️ <strong>Important Notice — New York Medical Centre / MediFlow:</strong> '
        'This application provides customer-care and informational support only. It does not replace '
        'evaluation by a qualified healthcare professional. All recommendations should be reviewed '
        'with your treating doctor. In a medical emergency, call <strong>911</strong> or go to the '
        'nearest Emergency Department immediately.</div>',
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Wizard helpers
# ─────────────────────────────────────────────────────────────────────────────
_WIZ_STEPS = [
    ("👤", "Personal\nDetails"),
    ("🩺", "Chief\nComplaint"),
    ("📊", "Vitals"),
    ("🏥", "History &\nSubmit"),
]

def _render_wizard_bar(current: int) -> None:
    """Render the wizard progress bar (1-based current step)."""
    n = len(_WIZ_STEPS)
    parts: list[str] = ['<div class="wiz-bar">']
    for i, (icon, label) in enumerate(_WIZ_STEPS):
        step_num = i + 1
        if step_num < current:
            dot_cls, lbl_cls, dot_content = "done", "", "✓"
        elif step_num == current:
            dot_cls, lbl_cls, dot_content = "active", " active", str(step_num)
        else:
            dot_cls, lbl_cls, dot_content = "", "", str(step_num)

        parts.append(
            f'<div class="wiz-step">'
            f'<span class="wiz-step-dot {dot_cls}">{dot_content}</span>'
            f'<span class="wiz-step-label{lbl_cls}">{icon} {label.replace(chr(10), " ")}</span>'
            f'</div>'
        )
        if i < n - 1:
            conn_cls = "done" if step_num < current else ""
            parts.append(f'<div class="wiz-connector {conn_cls}"></div>')

    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _nav_buttons(step: int, back_label: str = "← Back",
                 next_label: str = "Next →",
                 next_type: str = "primary") -> tuple[bool, bool]:
    """Render Back / Next buttons. Returns (back_clicked, next_clicked)."""
    cols = st.columns([1, 3, 1]) if step > 1 else st.columns([4, 1])
    back_clicked = False
    if step > 1:
        with cols[0]:
            back_clicked = st.form_submit_button(back_label, use_container_width=True)
        next_col = cols[2]
    else:
        next_col = cols[1]
    with next_col:
        next_clicked = st.form_submit_button(next_label, type=next_type,
                                             use_container_width=True)
    return back_clicked, next_clicked


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Intake form — 4-step wizard
# ─────────────────────────────────────────────────────────────────────────────
def _page_intake() -> None:
    step: int = st.session_state.intake_step
    fd: dict  = st.session_state.form_data   # accumulated data from previous steps

    _render_wizard_bar(step)

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 1 — Personal Details
    # ══════════════════════════════════════════════════════════════════════════
    if step == 1:
        st.markdown('<p class="page-heading">👤 Personal Details</p>', unsafe_allow_html=True)
        st.markdown('<p class="page-sub">Tell us a little about yourself to get started.</p>',
                    unsafe_allow_html=True)

        with st.form("wiz_step1", clear_on_submit=False):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                name = st.text_input("Full Name *", value=fd.get("name", ""),
                                     placeholder="e.g. John Smith")
            with c2:
                age = st.text_input("Age *", value=fd.get("age", ""),
                                    placeholder="e.g. 42")
            with c3:
                gender_idx = _GENDER_OPTIONS.index(fd.get("gender", "Prefer not to say"))
                gender = st.selectbox("Gender", _GENDER_OPTIONS, index=gender_idx)

            _, next_clicked = _nav_buttons(step, next_label="Next — Chief Complaint →")

        if next_clicked:
            errors = []
            if not name.strip():
                errors.append("Please enter your full name.")
            if not age.strip():
                errors.append("Please enter your age.")
            else:
                try:
                    age_int = int(age.strip())
                    if age_int < 1 or age_int > 120:
                        errors.append("Please enter a valid age (1–120).")
                except ValueError:
                    errors.append("Age must be a number.")
            if errors:
                for e in errors:
                    st.error(f"⚠️ {e}")
            else:
                st.session_state.form_data.update(
                    {"name": name.strip(), "age": age.strip(), "gender": gender}
                )
                st.session_state.intake_step = 2
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 2 — Chief Complaint
    # ══════════════════════════════════════════════════════════════════════════
    elif step == 2:
        st.markdown('<p class="page-heading">🩺 Chief Complaint</p>', unsafe_allow_html=True)
        st.markdown('<p class="page-sub">Describe your main symptom and how it affects you.</p>',
                    unsafe_allow_html=True)

        _sev_labels = {
            0: "😊 No pain", 1: "😐 Very mild", 2: "😐 Mild",
            3: "😟 Mild-Moderate", 4: "😟 Moderate", 5: "😣 Moderate",
            6: "😣 Moderate-Severe", 7: "😰 Severe", 8: "😰 Very Severe",
            9: "😱 Extremely Severe", 10: "🔴 Worst possible",
        }

        # Recover previous selections
        prev_symptom = fd.get("symptom", "Select your main symptom...")
        prev_symp_idx = (
            _SYMPTOM_OPTIONS.index(prev_symptom)
            if prev_symptom in _SYMPTOM_OPTIONS else 0
        )

        with st.form("wiz_step2", clear_on_submit=False):
            symptom_sel = st.selectbox("Main Symptom *", _SYMPTOM_OPTIONS,
                                       index=prev_symp_idx)
            symptom_other = st.text_input(
                "Please describe your symptom *",
                value=fd.get("symptom_other", ""),
                placeholder="Describe your main concern in your own words...",
                help="Required when 'Other' is chosen above; optional otherwise for extra detail.",
            )
            location = st.text_input(
                "Location / Area of Symptom",
                value=fd.get("location", ""),
                placeholder="e.g. Right knee, Lower back, Left side of chest...",
            )

            prev_dur_idx = (
                _DURATION_OPTIONS.index(fd.get("duration", _DURATION_OPTIONS[0]))
                if fd.get("duration") in _DURATION_OPTIONS else 0
            )
            duration = st.selectbox("How long have you had this symptom? *",
                                    _DURATION_OPTIONS, index=prev_dur_idx)

            st.markdown("**Pain / Discomfort Severity** (0 = none, 10 = worst)")
            severity = st.slider(
                "severity_slider",
                min_value=0, max_value=10,
                value=fd.get("severity", 5),
                step=1, format="%d / 10",
                label_visibility="collapsed",
            )
            st.caption(_sev_labels.get(severity, ""))

            st.markdown("**Frequency of Symptom**")
            prev_freq = fd.get("frequency", _FREQUENCY_OPTIONS[0])
            freq_idx  = (_FREQUENCY_OPTIONS.index(prev_freq)
                         if prev_freq in _FREQUENCY_OPTIONS else 0)
            frequency = st.radio(
                "frequency_radio", _FREQUENCY_OPTIONS,
                index=freq_idx, horizontal=True,
                label_visibility="collapsed",
            )

            ca, cr = st.columns(2)
            with ca:
                agg_sel = st.multiselect(
                    "What makes it WORSE?", _AGGRAVATING_OPTIONS,
                    default=[x for x in fd.get("aggravating_raw", [])
                             if x in _AGGRAVATING_OPTIONS],
                )
            with cr:
                rel_sel = st.multiselect(
                    "What makes it BETTER?", _RELIEVING_OPTIONS,
                    default=[x for x in fd.get("relieving_raw", [])
                             if x in _RELIEVING_OPTIONS],
                )

            back_clicked, next_clicked = _nav_buttons(
                step, next_label="Next — Vitals →"
            )

        if back_clicked:
            st.session_state.intake_step = 1
            st.rerun()

        if next_clicked:
            effective_symptom = (
                symptom_other.strip()
                if symptom_sel.lower().startswith("other")
                   or symptom_sel == "Select your main symptom..."
                else symptom_sel
            )
            errors = []
            if not effective_symptom:
                errors.append("Please select or describe your main symptom.")
            if errors:
                for e in errors:
                    st.error(f"⚠️ {e}")
            else:
                agg_clean = [a for a in agg_sel if not a.lower().startswith("other")]
                rel_clean = [r for r in rel_sel if not r.lower().startswith("other")]
                st.session_state.form_data.update({
                    "symptom":       effective_symptom,
                    "symptom_other": symptom_other.strip(),
                    "location":      location.strip(),
                    "duration":      duration,
                    "severity":      severity,
                    "frequency":     frequency,
                    "aggravating":   agg_clean,
                    "aggravating_raw": agg_sel,
                    "relieving":     rel_clean,
                    "relieving_raw": rel_sel,
                })
                st.session_state.intake_step = 3
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3 — Vitals
    # ══════════════════════════════════════════════════════════════════════════
    elif step == 3:
        st.markdown('<p class="page-heading">📊 Vitals</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="page-sub">Enter any recently measured vital signs. '
            'Leave blank if not available — this information is optional.</p>',
            unsafe_allow_html=True,
        )

        with st.form("wiz_step3", clear_on_submit=False):
            v1, v2 = st.columns(2)
            with v1:
                bp = st.text_input("Blood Pressure (mmHg)",
                                   value=fd.get("bp", ""),
                                   placeholder="e.g. 130/85")
                sugar = st.text_input("Blood Sugar (mg/dL)",
                                      value=fd.get("sugar", ""),
                                      placeholder="e.g. 110 fasting")
            with v2:
                heart_rate = st.text_input("Heart Rate (bpm)",
                                           value=fd.get("heart_rate", ""),
                                           placeholder="e.g. 78")
                spo2 = st.text_input("Oxygen Saturation (%)",
                                     value=fd.get("spo2", ""),
                                     placeholder="e.g. 97%")

            back_clicked, next_clicked = _nav_buttons(
                step, next_label="Next — Medical History →"
            )

        if back_clicked:
            st.session_state.intake_step = 2
            st.rerun()

        if next_clicked:
            st.session_state.form_data.update({
                "bp":         bp.strip(),
                "sugar":      sugar.strip(),
                "heart_rate": heart_rate.strip(),
                "spo2":       spo2.strip(),
            })
            st.session_state.intake_step = 4
            st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 4 — Medical History + Medications + Tests + Submit
    # ══════════════════════════════════════════════════════════════════════════
    elif step == 4:
        st.markdown('<p class="page-heading">🏥 Medical History & Final Review</p>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="page-sub">Please provide any relevant medical background. '
            'You may skip anything that does not apply.</p>',
            unsafe_allow_html=True,
        )

        with st.form("wiz_step4", clear_on_submit=False):

            st.markdown("#### 🏥 Medical History")
            cond_sel = st.multiselect(
                "Existing Medical Conditions",
                _CONDITION_OPTIONS,
                default=[x for x in fd.get("conditions_raw", [])
                         if x in _CONDITION_OPTIONS],
            )
            cond_other = st.text_input(
                "Other conditions (if any)",
                value=fd.get("conditions_other", ""),
                placeholder="e.g. Lupus, Fibromyalgia...",
            )

            surg_sel = st.multiselect(
                "Previous Surgeries / Procedures",
                _SURGERY_OPTIONS,
                default=[x for x in fd.get("surgeries_raw", [])
                         if x in _SURGERY_OPTIONS],
            )
            surg_other = st.text_input(
                "Other surgeries (if any)",
                value=fd.get("surgeries_other", ""),
                placeholder="e.g. Gallbladder removal...",
            )

            st.markdown("#### 💊 Medications & Allergies")
            medications = st.text_input(
                "Current Medications",
                value=fd.get("medications", ""),
                placeholder="e.g. Amlodipine 5mg, Metformin 500mg (or type None)",
            )
            allergy_sel = st.multiselect(
                "Known Drug / Other Allergies",
                _ALLERGY_OPTIONS,
                default=[x for x in fd.get("allergies_raw", [])
                         if x in _ALLERGY_OPTIONS],
            )
            allergy_other = st.text_input(
                "Other allergies (if any)",
                value=fd.get("allergies_other", ""),
                placeholder="e.g. Contrast dye, Latex...",
            )

            st.markdown("#### 🔬 Previous Investigations / Reports")
            st.caption("Please bring any previous reports to your appointment.")
            tests_sel = st.multiselect(
                "Tests / Reports Already Done",
                _TESTS_OPTIONS,
                default=[x for x in fd.get("tests_raw", [])
                         if x in _TESTS_OPTIONS],
            )
            tests_other = st.text_input(
                "Other tests / reports (if any)",
                value=fd.get("tests_other", ""),
                placeholder="e.g. Bone density scan, PET scan...",
            )

            st.markdown("---")
            back_clicked, submit_clicked = _nav_buttons(
                step,
                next_label="🔍 Analyse My Symptoms & Get Guidance",
                next_type="primary",
            )

        if back_clicked:
            st.session_state.intake_step = 3
            st.rerun()

        if submit_clicked:
            # Merge "Other" free-text into lists
            def _merge(sel_list: list[str], other_val: str) -> list[str]:
                cleaned = [s for s in sel_list if not s.lower().startswith("other")]
                if other_val.strip():
                    cleaned.append(other_val.strip())
                return cleaned

            cond_final    = _merge(cond_sel,    cond_other)
            surg_final    = _merge(surg_sel,    surg_other)
            allergy_final = _merge(allergy_sel, allergy_other)
            tests_final   = _merge(tests_sel,   tests_other)

            st.session_state.form_data.update({
                "conditions":      cond_final,
                "conditions_raw":  cond_sel,
                "conditions_other": cond_other.strip(),
                "surgeries":       surg_final,
                "surgeries_raw":   surg_sel,
                "surgeries_other": surg_other.strip(),
                "medications":     medications.strip(),
                "allergies":       allergy_final,
                "allergies_raw":   allergy_sel,
                "allergies_other": allergy_other.strip(),
                "tests":           tests_final,
                "tests_raw":       tests_sel,
                "tests_other":     tests_other.strip(),
            })

            intake = _build_intake_from_form(st.session_state.form_data)

            with st.spinner(
                "🔍 Our specialist team is reviewing your case — please wait up to 60 seconds..."
            ):
                try:
                    orch: HospitalOrchestrator = st.session_state.orchestrator
                    steps_result = _run_async(_run_workflow(orch, intake))
                    final_state  = steps_result[-1][1] if steps_result else None
                    if final_state:
                        st.session_state.workflow_state = final_state
                        st.session_state.page           = "results"
                except Exception as exc:
                    st.session_state.error_message = (
                        f"A technical error occurred: {str(exc)[:120]}. "
                        "Please try again or contact the hospital."
                    )
                    logger.error("[APP] Workflow error: %s", exc)

            if st.session_state.error_message:
                st.error(st.session_state.error_message)
            else:
                st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Results
# ─────────────────────────────────────────────────────────────────────────────
def _page_results() -> None:
    state: SessionState = st.session_state.workflow_state

    # Processing steps bar
    _render_steps(state.processing_steps)
    st.markdown('<hr class="shr">', unsafe_allow_html=True)

    # 1. Department banner
    _render_dept_banner(state)

    # 2. Care recommendation
    _render_care(state)

    # 3. Doctors + appointments (directly below — no second page)
    _render_doctors_and_appointments(state)

    # 4. New consultation button
    st.markdown('<hr class="shr">', unsafe_allow_html=True)
    if st.button("🔄 Start New Consultation", type="secondary"):
        _reset_session()
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    _init_session()

    # ── Brand hero header ────────────────────────────────────────────────────
    st.markdown(
        '<div class="brand-hero">'
        '<div class="mf-wordmark">Medi<span>Flow</span></div>'
        '<div class="mf-tagline">AI Assisted Customer Care &amp; Patient Navigation</div>'
        '<div class="mf-hospital">'
        '<span class="mf-pulse"></span>New York Medical Centre'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<hr class="shr">', unsafe_allow_html=True)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            '<div style="font-size:1.15rem;font-weight:700;color:#0f2d4e;">🏥 New York Medical Centre</div>'
            '<div style="font-size:0.8rem;color:#4a7fa5;margin-top:2px;">MediFlow AI Assisted Customer Care</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown("#### 📞 Contacts")
        st.markdown("📲 General: +1-212-555-0100")
        st.markdown("🚨 Emergency: 911 / +1-212-555-0911")
        st.markdown("🌐 nymedicalcentre.example.com")
        st.markdown("---")
        st.markdown("#### 🏢 Departments")
        for code, name in _DEPT_NAMES.items():
            st.markdown(f"{_DEPT_ICONS[code]} **{code}** — {name}")
        st.markdown("---")
        if st.button("🔄 New Consultation", use_container_width=True):
            _reset_session()
            st.rerun()
        st.markdown("---")
        st.markdown(
            '<div style="font-size:0.72rem;color:#a0aec0;">v1.0 · MediFlow Educational Prototype<br>Not for clinical use</div>',
            unsafe_allow_html=True,
        )

    # ── Route pages ───────────────────────────────────────────────────────────
    if st.session_state.page == "intake":
        _page_intake()
    elif st.session_state.page == "results" and st.session_state.workflow_state:
        _page_results()
    else:
        _page_intake()

    # ── Bottom disclaimer ─────────────────────────────────────────────────────
    st.markdown('<hr class="shr">', unsafe_allow_html=True)
    _render_disclaimer()


if __name__ == "__main__":
    main()
