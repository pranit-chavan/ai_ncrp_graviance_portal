"""
DASHBOARD - Cybercrime Intake & Investigation Portal MVP

Six pages, one file:
    1. Home               - Landing & overview, emergency helplines, filing access
    2. Report Cyber Crime - 3-step citizen filing wizard (zero-friction intake + checklist)
    3. Saved Records      - Find a complaint record stored on this computer
    4. Case Register      - Completed records available for investigator review
    5. Case Review        - Evidence, triage, and recorded review actions
    6. Operations         - Workload indicators from the local investigator inbox

THE WIZARD (page 2) has three steps:
    Step 1  Describe the incident and review evidence
    Step 2  Review contact and incident details
    Step 3  Review and save a local complaint record

DESIGN RULES:
    - Do not imply government affiliation, official filing, or authenticated access.
    - Use plain language for complainants and action-oriented labels for investigator review.
    - Use responsive, accessible controls and high-contrast typography.
    - Citizen drafts stay in case_files/; consented completed submissions also enter investigator_inbox/.
    - All wizard state lives in st.session_state["wiz"].
"""

import glob
import html
import json
import os
import re
import sys
from datetime import date, datetime
from datetime import time as dtime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules import investigator_store
from modules.ocr_extract import format_entity_reading

CASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "case_files")
INVESTIGATOR_INBOX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "investigator_inbox")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
MAX_UPLOAD_MB = 5

# ---- Portal Design System -------------------------------------------------
GOV_BLUE = "#12372f"
GOV_BLUE_DARK = "#08291f"
GOV_BLUE_HEADER = "#075e4d"
GOV_BLUE_LIGHT = "#edf5f2"
GOV_ACCENT_ORANGE = "#d97706"
GOV_ACCENT_GREEN = "#087f5b"
GOV_GREY = "#f7faf8"
GOV_BORDER = "#d5e1dc"
SEQ_BLUE = "#146c68"

BAND_COLOR = {"HIGH": "#166534", "MEDIUM": "#854d0e", "LOW": "#991b1b", "NOT SUPPLIED": "#475569"}
BAND_BG = {"HIGH": "#dcfce7", "MEDIUM": "#fef9c3", "LOW": "#fee2e2", "NOT SUPPLIED": "#f1f5f9"}
BAND_BORDER = {"HIGH": "#16a34a", "MEDIUM": "#ca8a04", "LOW": "#dc2626", "NOT SUPPLIED": "#94a3b8"}
BAND_ORDER = ["HIGH", "MEDIUM", "LOW", "NOT SUPPLIED"]

try:
    from modules.sentiment_analysis import analyze_sentiment_and_urgency
except ImportError:
    try:
        from sentiment_analysis import analyze_sentiment_and_urgency
    except ImportError:
        analyze_sentiment_and_urgency = None

try:
    from modules.gap_detection import detect_gaps
except ImportError:
    try:
        from gap_detection import detect_gaps
    except ImportError:
        detect_gaps = None

try:
    from modules.speech_to_text import transcribe_audio_bytes, get_supported_languages, is_whisper_available
    _stt_available = is_whisper_available()
except ImportError:
    _stt_available = False
    transcribe_audio_bytes = None
    get_supported_languages = None

try:
    from modules.mo_knowledge_base import match_mo, get_victim_guidance, list_all_mos
    from modules.entity_extractor import extract_entities_v2
    from modules.auto_fill import generate_autofill_payload
    from modules.victim_guidance import generate_victim_guidance
    from modules.pattern_engine import find_linked_cases, build_suspect_dossier
    from modules.doc_generator import generate_investigation_document, list_available_templates
    _v2_modules_available = True
except Exception:
    _v2_modules_available = False


def inject_custom_css():
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, Arial, sans-serif;
            color: #182b3b;
        }
        .stApp { background: #ffffff; }
        .block-container { max-width: 1180px; padding: 1.1rem 2rem 3rem; }
        header[data-testid="stHeader"] { background: #ffffff !important; }
        h1 { color: #12372f !important; font-weight: 740 !important; letter-spacing: 0 !important; font-size: 2.2rem !important; }
        h2, h3 { color: #12372f !important; font-weight: 700 !important; letter-spacing: 0 !important; }
        p, label, [data-testid="stMarkdownContainer"] { line-height: 1.55; }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff; border: 1px solid #dbe3ec; border-radius: 10px;
        }
        div[data-testid="stExpander"] { border: 1px solid #dbe3ec; border-radius: 8px; background: #fff; }
        
        div.stButton > button[kind="primary"] {
            background-color: #087f5b !important;
            color: #ffffff !important;
            border: 1px solid #087f5b !important;
            border-radius: 5px !important;
            font-weight: 650 !important;
            min-height: 42px !important;
            padding: 8px 16px !important;
            transition: background-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out !important;
            box-shadow: 0 2px 4px rgba(10, 37, 64, 0.12) !important;
        }
        [data-testid="stFormSubmitButton"] button {
            background-color: #087f5b !important;
            color: #ffffff !important;
            border: 1px solid #087f5b !important;
            border-radius: 5px !important;
            font-weight: 650 !important;
            min-height: 42px !important;
            padding: 8px 16px !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #075e4d !important;
            border-color: #075e4d !important;
            box-shadow: 0 2px 8px rgba(8, 95, 77, 0.18) !important;
        }
        div.stButton > button[kind="secondary"] {
            background-color: #ffffff !important;
            color: #12372f !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 5px !important;
            font-weight: 650 !important;
            min-height: 44px !important;
            padding: 8px 16px !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            background-color: #edf5f2 !important;
            border-color: #75a69b !important;
        }
        div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
            border-radius: 7px !important;
            border-color: #cbd5e1 !important;
            font-size: 1em !important;
        }
        div[data-baseweb="input"] input:focus, div[data-baseweb="textarea"] textarea:focus {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 1px #2563eb !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #e2e8f0 !important;
            border-radius: 10px !important;
            overflow: hidden;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.45em !important;
            font-weight: 800 !important;
            color: #123451 !important;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.82em !important;
            font-weight: 600 !important;
            color: #64748b !important;
        }
        section[data-testid="stSidebar"] {
            background: #ffffff !important;
            border-right: 1px solid #dce4ed !important;
        }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label {
            border-radius: 7px; padding: 4px 8px; font-weight: 600;
        }
        div[data-testid="stAlert"] { border-radius: 9px; }
        div[data-testid="stMetric"] { background: #fff; border: 1px solid #dbe3ec; border-radius: 8px; padding: 12px 14px; }
        .ca-masthead { border-bottom: 1px solid #d5e1dc; background: #fff; }
        .ca-helpline-band { background: #12372f; color: #fff; padding: 20px 24px; display:grid; grid-template-columns:1.15fr repeat(3,1fr); gap:20px; align-items:center; }
        .ca-helpline-band h2 { color:#fff !important; font-size:1.15rem !important; margin:0; }
        .ca-help-item { display:flex; flex-direction:column; gap:3px; min-width:0; border-left:1px solid rgba(255,255,255,.45); padding-left:18px; }
        .ca-helpline-band a { color: #fff !important; text-decoration: none; }
        .ca-help-item:first-of-type strong { color:#ffbf47; }
        .ca-help-item strong { font-size:2rem; line-height:1.1; }
        .ca-help-item span { font-size:.88rem; line-height:1.35; }
        .ca-small-link a { color: #075e4d !important; font-weight: 650; }
        div[data-testid="stImage"] img { max-height: 310px; object-fit: cover; }
        section[data-testid="stSidebar"] [data-testid="stRadio"] label { min-height: 42px; }
        @media (max-width: 768px) {
            .block-container { padding: 1rem 1rem 2rem; }
            h1 { font-size: 1.8rem !important; }
        }
        .portal-hero-title { font-size: 2.25em; }
        @media (max-width: 700px) {
            .block-container { padding: 1rem 1rem 2rem; }
            .portal-masthead { margin: -1rem -1rem 1.2rem -1rem !important; padding: 12px 16px !important; }
            .portal-hero { padding: 28px 20px !important; }
            .portal-hero-title { font-size: 1.55em !important; line-height: 1.25; }
            .ca-masthead { margin:-1rem -1rem 1.2rem -1rem !important; padding:12px 16px !important; }
            .ca-masthead a { white-space:normal !important; text-align:right; }
            .ca-helpline-band { grid-template-columns:1fr 1fr; gap:16px; padding:18px; }
            .ca-help-item { border-left:0; padding-left:0; }
            .ca-help-item strong { font-size:1.65rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def urgency_badge(level, is_golden_hour=False):
    if is_golden_hour or level == "EMERGENCY_GOLDEN_HOUR":
        return '<span style="background:#fee2e2;color:#991b1b;border:1px solid #dc2626;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">CRITICAL: GOLDEN HOUR</span>'
    elif level == "HIGH_URGENCY":
        return '<span style="background:#ffedd5;color:#9a3412;border:1px solid #ea580c;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">HIGH URGENCY</span>'
    elif level == "MODERATE_URGENCY":
        return '<span style="background:#fef3c7;color:#92400e;border:1px solid #d97706;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">MODERATE</span>'
    return '<span style="background:#f1f5f9;color:#334155;border:1px solid #94a3b8;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">STANDARD</span>'


def tone_badge(tone, label=None):
    lbl = label or tone or "Neutral"
    if tone == "PANICKED_DISTRESSED":
        return '<span style="background:#fee2e2;color:#991b1b;border:1px solid #f87171;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">Severe Distress</span>'
    elif tone == "ANXIOUS_THREATENED":
        return '<span style="background:#fef3c7;color:#92400e;border:1px solid #fcd34d;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">Active Threat / Intimidation</span>'
    elif tone == "FRUSTRATED_ANGRY":
        return '<span style="background:#f3e8ff;color:#6b21a8;border:1px solid #d8b4fe;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">High Grievance</span>'
    return '<span style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;padding:3px 9px;border-radius:4px;font-weight:700;font-size:0.78em;letter-spacing:0.04em;text-transform:uppercase;">Informational</span>'


def band_badge(band, size="0.78em"):
    return ""



# ---- taxonomy (mirrors modules/legal_mapping.json) --------------------------
KNOWN_CATEGORIES = [
    "AePS Fraud", "Debit/Credit Card Fraud / SIM Swap Fraud", "Demat / Depository Fraud",
    "E-Wallet Related Fraud", "Internet Banking Related Fraud", "UPI Related Frauds",
    "Online Job Fraud", "Online Matrimonial Fraud",
    "Impersonating Email (Business Email Compromise)", "Cheating by Impersonation",
    "Email Phishing", "Email Hacking", "Profile Hacking / Identity Theft",
    "Fake / Impersonating Profile", "Cyber Bullying / Stalking / Sexting",
    "Provocative Speech for Unlawful Acts", "Intimidating Email",
    "Damage to Computer / Computer System", "Unauthorised Access / Data Breach",
    "Tampering with Computer Source Document", "Website Defacement / Hacking",
]

MAIN_CATEGORIES = [
    "Online and Social Media Related Crime",
    "Online Financial Fraud",
    "Hacking / Damage to Computer",
    "Other / Not Sure",
]

SUB_TO_MAIN_CATEGORY = {
    "Cheating by Impersonation": "Online and Social Media Related Crime",
    "Cyber Bullying / Stalking / Sexting": "Online and Social Media Related Crime",
    "Email Phishing": "Online and Social Media Related Crime",
    "Fake / Impersonating Profile": "Online and Social Media Related Crime",
    "Impersonating Email (Business Email Compromise)": "Online and Social Media Related Crime",
    "Intimidating Email": "Online and Social Media Related Crime",
    "Online Job Fraud": "Online and Social Media Related Crime",
    "Online Matrimonial Fraud": "Online and Social Media Related Crime",
    "Profile Hacking / Identity Theft": "Online and Social Media Related Crime",
    "Provocative Speech for Unlawful Acts": "Online and Social Media Related Crime",
    "AePS Fraud": "Online Financial Fraud",
    "Debit/Credit Card Fraud / SIM Swap Fraud": "Online Financial Fraud",
    "Demat / Depository Fraud": "Online Financial Fraud",
    "E-Wallet Related Fraud": "Online Financial Fraud",
    "Internet Banking Related Fraud": "Online Financial Fraud",
    "UPI Related Frauds": "Online Financial Fraud",
    "Damage to Computer / Computer System": "Hacking / Damage to Computer",
    "Email Hacking": "Hacking / Damage to Computer",
    "Tampering with Computer Source Document": "Hacking / Damage to Computer",
    "Unauthorised Access / Data Breach": "Hacking / Damage to Computer",
    "Website Defacement / Hacking": "Hacking / Damage to Computer",
}

MODUS_OPERANDI_HINTS = {
    "AePS Fraud": "Unauthorised biometric-authenticated withdrawal without OTP or card use",
    "Debit/Credit Card Fraud / SIM Swap Fraud": "Card details compromised, or SIM swapped to intercept OTPs",
    "Demat / Depository Fraud": "Unauthorised trading or withdrawal from a demat/trading account",
    "E-Wallet Related Fraud": "Unauthorised debit from a mobile wallet",
    "Internet Banking Related Fraud": "Unauthorised net-banking transaction, often via a phishing link",
    "UPI Related Frauds": "Fraudulent UPI collect request or malicious QR code scan",
    "Online Job Fraud": "Fake job offer with an upfront registration or training fee demanded",
    "Online Matrimonial Fraud": "Fake matrimonial profile used to build trust, then request money",
    "Impersonating Email (Business Email Compromise)": "Email impersonating a business contact to redirect a payment",
    "Cheating by Impersonation": "Caller or contact impersonated a trusted authority to extract money",
    "Email Phishing": "Phishing email or deceptive link used to harvest user credentials",
    "Email Hacking": "Unauthorised access to the complainant's email account",
    "Profile Hacking / Identity Theft": "Unauthorised access to a social media account or stolen identity",
    "Fake / Impersonating Profile": "A fraudulent profile created using the complainant's identity or photos",
    "Cyber Bullying / Stalking / Sexting": "Harassment, stalking, or non-consensual dissemination of private media",
    "Provocative Speech for Unlawful Acts": "Content inciting unlawful acts or communal discord online",
    "Intimidating Email": "Threatening or coercive email received",
    "Damage to Computer / Computer System": "Malware, virus, or ransomware damage to a computer system",
    "Unauthorised Access / Data Breach": "Unauthorised system intrusion, credential exfiltration, or breach",
    "Tampering with Computer Source Document": "Source code or electronic document tampered with or altered",
    "Website Defacement / Hacking": "Website hacked, unauthorised modifications, or server defacement",
}

INCIDENT_LOCATIONS = [
    "Email", "Facebook", "Instagram", "LinkedIn", "Mobile App", "Other Media",
    "Snapchat", "Telegram", "Twitter", "Website URL", "WhatsApp", "YouTube",
]

SUSPECT_ID_TYPES = [
    "Driving License", "Email", "Gov. Issued Card", "Mobile Number", "PAN Card",
    "Voter Card", "Social Media Profile URL", "Landline Call", "International Call",
    "WhatsApp Call", "Bank Account Number", "URL", "Other",
]

MONEY_TRANSFER_METHODS = ["UPI", "IMPS", "NEFT/RTGS", "Debit Card", "Credit Card",
                          "Net Banking", "Wallet Transfer", "Cash Deposit", "Other"]

COMPLAINANT_ID_TYPES = ["Not provided", "Aadhaar Card", "PAN Card", "Voter ID", "Passport", "Driving License", "Other"]

HELPLINES = [
    ("1930", "Cyber financial fraud", GOV_ACCENT_ORANGE),
    ("112", "Police, fire or medical emergency", "#f8fafc"),
    ("181", "Women’s helpline", "#f8fafc"),
]

st.set_page_config(
    page_title="CyberAssist | Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP",
    layout="wide",
    initial_sidebar_state="auto",
)
inject_custom_css()


# =============================================================================
# Helper Utilities
# =============================================================================

def g(d, *path, default="not supplied"):
    """Safe nested dictionary access."""
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
    return default if cur is None else cur


@st.cache_data(ttl=5)
def load_case_files():
    """Load and parse case files from disk."""
    cases, errors = [], []
    for path in sorted(glob.glob(os.path.join(CASE_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("root is not a JSON object")
            data["_path"] = path
            cases.append(data)
        except Exception as e:
            errors.append((os.path.basename(path), str(e)))
    return cases, errors


@st.cache_data(ttl=5)
def load_investigator_cases():
    """Load only records intentionally received into the investigator inbox."""
    return investigator_store.load_cases(INVESTIGATOR_INBOX_DIR)


def band_of(case):
    band = g(case, "classification", "confidence_band", default="NOT SUPPLIED")
    return band if band in BAND_COLOR else "NOT SUPPLIED"


def confirmation_banner():
    st.info(
        "**Computer-generated suggestion:** The category below is an estimate from the information provided. Please check it. It is not a legal decision or an official assessment."
    )


def low_confidence_banner(band):
    pass


def fmt_confidence(conf):
    if conf in (None, ""):
        return "Not available"
    try:
        value = float(conf)
        return f"{value:.0%}" if value <= 1 else f"{value:.1f}%"
    except (TypeError, ValueError):
        return "Not available"


def pdf_path_for(case):
    case_path = case.get("_path")
    if case_path:
        imported_pdf = os.path.splitext(case_path)[0] + ".pdf"
        return imported_pdf if os.path.isfile(imported_pdf) else None
    ref = case.get("reference")
    if not ref:
        return None
    p = os.path.join(CASE_DIR, ref.replace("/", "-") + ".pdf")
    return p if os.path.exists(p) else None


def save_case(case):
    path = case.get("_path")
    if not path:
        st.error("Cannot save: case record has no valid disk path.")
        return False
    try:
        to_write = {k: v for k, v in case.items() if k != "_path"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(to_write, f, indent=2, ensure_ascii=False)
        load_case_files.clear()
        return True
    except Exception as e:
        st.error(f"Could not persist case file: {e}")
        return False


@st.cache_data
def load_benchmark_metrics():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "benchmark_metrics.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def render_legal_sections(legal):
    st.markdown(
        '<div style="display:inline-flex;align-items:center;gap:6px;background:#eff6f7;border:1px solid #9bc5c5;'
        'color:#14535b;font-size:0.78em;font-weight:700;padding:4px 10px;border-radius:6px;margin-bottom:8px;">'
        'Possible legal references — review and verify before relying on them</div>',
        unsafe_allow_html=True,
    )
    it_act = legal.get("it_act") or []
    bns = legal.get("bns") or []
    other = legal.get("other") or []
    rows = []
    for s in it_act:
        rows.append({"Statutory Provision": f"IT Act Section {s.get('section', '?')}", "Substantive Offence": s.get("description", "")})
    for s in bns:
        ipc = f" [IPC Equivalent: Sec {s['ipc_equivalent']}]" if s.get("ipc_equivalent") else ""
        rows.append({"Statutory Provision": f"BNS Section {s.get('section', '?')}", "Substantive Offence": s.get("description", "") + ipc})
    for s in other:
        sec = f" Section {s['section']}" if s.get("section") else ""
        rows.append({"Statutory Provision": f"{s.get('act', '?')}{sec}", "Substantive Offence": s.get("description", "")})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption("No statutory sections resolved for this classification.")

    elements = legal.get("statutory_elements") or []
    if elements:
        with st.expander("Investigating Officer Proof Checklist (Statutory Ingredients)", expanded=False):
            for idx, el in enumerate(elements, 1):
                st.markdown(f"**{idx}.** {el}")

    for cond in legal.get("conditional_applied") or []:
        status = cond.get("status", "")
        if status.startswith("NOT EVALUATED"):
            st.warning(f"Advisory: {status} — {cond.get('action', '')}")
        elif status == "APPLIED":
            st.info(f"Statutory rule applied: {cond.get('rule', '')} ({cond.get('reason', '')})")

    st.caption("This automatically generated mapping is a starting point only. A qualified professional must verify applicable laws and evidence requirements.")

    if legal.get("notes"):
        st.markdown(f"**Investigator Guidance:** {legal['notes']}")


# =============================================================================
# Shared visual elements
# =============================================================================

def header_bar():
    st.markdown(
        f"""
        <div class="ca-masthead" style="margin:-1.1rem -2rem 1.5rem -2rem;padding:14px 32px;">
          <div style="max-width:1180px;margin:auto;display:flex;justify-content:space-between;align-items:center;gap:16px;">
            <div>
              <div style="color:{GOV_BLUE_DARK};font-size:1.35em;font-weight:800;line-height:1.2;">CyberAssist</div>
              <div style="color:#53665f;font-size:.82em;margin-top:3px;">Cybercrime complaint support · Independent academic prototype</div>
            </div>
            <a href="tel:1930" style="color:{GOV_BLUE_HEADER};font-size:.95em;font-weight:750;text-decoration:none;white-space:nowrap;">Urgent financial fraud? Call 1930</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(text):
    st.markdown(
        f'<div style="background:transparent;border-left:3px solid {GOV_ACCENT_ORANGE};'
        f'padding:4px 12px;margin:23px 0 12px 0;font-weight:750;color:{GOV_BLUE};'
        f'font-size:1.02em;letter-spacing:0;">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def req(text, mandatory=True):
    return f"{text}  :red[*]" if mandatory else text


def progress_steps(current):
    steps = ["Describe", "Review details", "Review and save"]
    cells = []
    for i, label in enumerate(steps, 1):
        if i < current:
            bg, fg, border = "#e2e8f0", GOV_BLUE_DARK, "#94a3b8"
            marker = "✓"
        elif i == current:
            bg, fg, border = GOV_BLUE, "#ffffff", GOV_ACCENT_ORANGE
            marker = str(i)
        else:
            bg, fg, border = "#f8fafc", "#64748b", "#cbd5e1"
            marker = str(i)
        cells.append(
            f'<div style="flex:1;text-align:center;background:{bg};color:{fg};border:1px solid {border};'
            f'padding:11px 8px;font-weight:700;font-size:0.86em;border-radius:8px;">'
            f'<span style="display:inline-block;width:20px;height:20px;line-height:18px;border-radius:50%;'
            f'background:rgba(255,255,255,0.25);margin-right:6px;font-size:0.85em;border:1px solid currentColor;">{marker}</span>{label}</div>'
        )
    st.markdown(f'<div style="display:flex;gap:8px;margin-bottom:18px;">{"".join(cells)}</div>',
                unsafe_allow_html=True)


# =============================================================================
# Session State Initialization
# =============================================================================

st.session_state.setdefault("nav_page", "Home")
st.session_state.setdefault("selected_case_path", None)
st.session_state.setdefault("wizard_step", 1)
st.session_state.setdefault("reclassify_open", False)
st.session_state.setdefault("last_submitted_case", None)

if "wiz" not in st.session_state:
    st.session_state["wiz"] = {
        "incident_text": "", "category": "", "sub_category": "", "modus_operandi": "",
        "ai_sub_category": None, "ai_confidence": None, "ai_narrative_ok": None,
        "incident_date": None, "incident_time": None,
        "lost_money": "No", "transactions": [],
        "has_suspect_txn": "No", "suspect_transactions": [],
        "incident_location": [],
        "evidence": [],
        "relationship_with_victim": "Self", "name": "", "age": 0, "phone": "",
        "email": "", "city": "", "state": "",
        "id_type": COMPLAINANT_ID_TYPES[0], "id_upload_name": None,
        "suspects": [], "suspect_photo": None,
        "share_suspect_address": "No", "suspect_address": "",
        "consent": False,
        "intake_analysis": None,
        "sentiment": None,
        "qa_round": 0,
        "qa_answers": {},
        "qa_questions": [],
        "guided_intake": {"started": False, "complete": False, "messages": [], "docket": {}, "language": "en", "initial_statement": ""},
    }


def new_wizard():
    st.session_state.pop("local_record_consent", None)
    st.session_state["wiz"] = {
        "incident_text": "", "category": "", "sub_category": "", "modus_operandi": "",
        "ai_sub_category": None, "ai_confidence": None, "ai_narrative_ok": None,
        "incident_date": None, "incident_time": None,
        "lost_money": "No", "transactions": [],
        "has_suspect_txn": "No", "suspect_transactions": [],
        "incident_location": [],
        "evidence": [],
        "relationship_with_victim": "Self", "name": "", "age": 0, "phone": "",
        "email": "", "city": "", "state": "",
        "id_type": COMPLAINANT_ID_TYPES[0], "id_upload_name": None,
        "suspects": [], "suspect_photo": None,
        "share_suspect_address": "No", "suspect_address": "",
        "consent": False,
        "intake_analysis": None,
        "sentiment": None,
        "qa_round": 0,
        "qa_answers": {},
        "qa_questions": [],
        "guided_intake": {"started": False, "complete": False, "messages": [], "docket": {}, "language": "en", "initial_statement": ""},
    }
    st.session_state["wizard_step"] = 1


PAGES = ["Home", "Report Cyber Crime", "Check Status", "Case Queue", "Case Review", "Operations"]
USER_PAGES = ["Home", "Report Cyber Crime", "Check Status"]
INVESTIGATOR_PAGES = ["Case Queue", "Case Review", "Operations"]

PAGE_LABELS_CITIZEN = {
    "Home": "Home",
    "Report Cyber Crime": "Prepare a draft",
    "Check Status": "Find a saved draft",
}

PAGE_LABELS_INVESTIGATOR = {
    "Case Queue": "Case register",
    "Case Review": "Case review",
    "Operations": "Overview",
}

CASE_STATUS_LABELS = {
    "RECEIVED - AWAITING REVIEW": "Waiting for review",
    "IN REVIEW": "In review",
    "AWAITING INFORMATION": "Waiting for more information",
    "REFERRED FOR FOLLOW-UP": "Follow-up needed",
    "REVIEW COMPLETE": "Review complete",
    "CONFIRMED BY OFFICER": "Review complete",
    "RECLASSIFIED BY OFFICER": "Category updated",
}


def display_case_status(status):
    value = str(status or "").strip()
    return CASE_STATUS_LABELS.get(value, value.replace("_", " ").title() or "Not set")

header_bar()

current_route = st.query_params.get("route", "")

if current_route == "user":
    st.info(
        "**Independent student prototype:** This creates a local project record, not an official complaint. Depending on configuration, text may be processed by an external AI provider. Use fictional details only; never enter passwords, PINs, one-time codes, or identity documents."
    )
elif current_route == "investigator":
    st.warning(
        "**MVP limitation:** The inbox is stored on this computer and has no login, role controls, or tamper-proof audit. Do not use it for live investigations or real victim data."
    )

if current_route == "user":
    nav_pages = USER_PAGES
elif current_route == "investigator":
    nav_pages = INVESTIGATOR_PAGES
else:
    nav_pages = None

if nav_pages is not None:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:10px 0 8px 0;border-bottom:1px solid #e2e8f0;margin-bottom:12px;">
              <div style="font-weight:800;color:{GOV_BLUE};font-size:1.05em;letter-spacing:0.02em;">
                CyberAssist
              </div>
              <div style="font-size:0.78em;color:#64748b;font-weight:600;margin-top:2px;">
                {'For people reporting an incident' if current_route == 'user' else 'For complaint review'}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        _current = st.session_state["nav_page"]
        if _current not in nav_pages:
            _current = nav_pages[0]
            st.session_state["nav_page"] = _current

        _idx = nav_pages.index(_current)
        label_map = PAGE_LABELS_CITIZEN if current_route == "user" else PAGE_LABELS_INVESTIGATOR
        page = st.radio("Portal Navigation", nav_pages, format_func=lambda p: label_map.get(p, p),
                        index=_idx, label_visibility="collapsed")
        st.session_state["nav_page"] = page

        st.divider()
        if current_route == "investigator":
            all_cases_preview, load_errors_preview = load_investigator_cases()
            pending = sum(1 for c in all_cases_preview if g(c, "status", default="") in {"RECEIVED - AWAITING REVIEW", "IN REVIEW", "AWAITING INFORMATION"})
            st.metric("Cases in register", len(all_cases_preview))
            st.metric("Awaiting action", pending)
            if load_errors_preview:
                with st.expander(f"System Notice: {len(load_errors_preview)} unparsed file(s)"):
                    for name, err in load_errors_preview:
                        st.caption(f"{name}: {err}")
            st.divider()

        st.markdown(
            f"""
            <div style="background:#f1f5f9;border:1px solid #cbd5e1;border-left:4px solid {GOV_BLUE};padding:10px 12px;border-radius:4px;">
              <div style="font-weight:700;color:{GOV_BLUE};font-size:0.8em;text-transform:uppercase;letter-spacing:0.04em;">
                If money was taken recently
              </div>
              <div style="font-size:1.2em;font-weight:800;color:#1e40af;margin-top:2px;">
                1930
              </div>
              <div style="font-size:0.75em;color:#64748b;margin-top:2px;">
                Call 1930 and contact your bank using its official number
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        if st.button("Switch workspace", width="stretch"):
            if "route" in st.query_params:
                del st.query_params["route"]
            st.rerun()


# =============================================================================
# PAGE - Landing Route (Root)
# =============================================================================

def page_landing():
    st.title("Get help preparing a cybercrime report")
    st.markdown(
        "CyberAssist helps you organize what happened and prepare a draft to review. "
        "It is an independent academic prototype. It does **not** submit a complaint to the police, your bank, or the National Cyber Crime Reporting Portal."
    )
    action_col, portal_col = st.columns([1, 1.25], vertical_alignment="center")
    with action_col:
        if st.button("Prepare a complaint draft", type="primary", width="stretch"):
            new_wizard()
            st.query_params["route"] = "user"
            st.session_state["nav_page"] = "Report Cyber Crime"
            st.rerun()
    with portal_col:
        st.link_button("Report on the official portal", "https://www.cybercrime.gov.in/", width="stretch")

    image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "assets", "cyberassist-home.png")
    if os.path.isfile(image_path):
        st.image(image_path, width="stretch", caption="Use the official portal or helpline for real incidents. This project is for demonstration only.")

    helpline_items = "".join(
        f'<div class="ca-help-item"><a href="tel:{html.escape(number)}"><strong>{html.escape(number)}</strong></a>'
        f'<span>{html.escape(label)}</span></div>'
        for number, label, _ in HELPLINES
    )
    st.markdown(
        f'<section class="ca-helpline-band" aria-label="Emergency and cybercrime helplines">'
        f'<h2>Need help now?</h2>{helpline_items}</section>',
        unsafe_allow_html=True,
    )

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Examples of cybercrime in India")
        st.markdown(
            "- **Payment fraud:** money taken through a deceptive link, UPI request, or bank transaction.\n"
            "- **Impersonation:** someone pretends to be a trusted person or organization.\n"
            "- **Account access:** someone gets into your email, social media, or other account.\n"
            "- **Online harassment:** threats, stalking, or repeated abusive messages online."
        )
    with right:
        st.subheader("What may help when reporting")
        st.markdown(
            "- When the incident happened, even approximately.\n"
            "- Payment amount and transaction reference, if money was involved.\n"
            "- Relevant screenshots, messages, emails, or links.\n"
            "- The bank, payment app, website, or social platform involved."
        )
        st.caption("Do not share passwords, PINs, one-time codes, or full card details in this prototype.")

    st.markdown(
        "**For real incidents:** report through the official portal or contact the appropriate helpline. "
        "For a recent cyber financial fraud, call 1930 promptly and contact your bank using its official number."
    )
    st.caption(
        "CyberAssist is an academic prototype. It is not affiliated with the Government of India. "
        "Records are stored in this project workspace; the app has no sign-in or access controls. "
        "Depending on configuration, complaint text may be processed by an external AI provider. Use fictional details only. "
        "Project: Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP."
    )

    if not st.query_params.get("route"):
        with st.expander("Project demonstration workspace"):
            st.warning("The local review workspace is for demonstration only and has no login or access controls.")
            if st.button("Open local review workspace"):
                st.query_params["route"] = "investigator"
                st.session_state["nav_page"] = "Case Queue"
                st.rerun()


# =============================================================================
# PAGE - Home (Citizen)
# =============================================================================

def page_home():
    page_landing()


# =============================================================================
# PAGE - Report Cyber Crime (Wizard)
# =============================================================================

def pre_filing_checklist():
    with st.expander("Before you start (optional)", expanded=False):
        st.markdown(
            "Describe events in your own words. If available, keep the approximate date, transaction reference, and relevant screenshots nearby. "
            "You can skip details you do not know. Never share a password, PIN, one-time code, or full card details. Use fictional information in this academic prototype."
        )


def _run_evidence_review(wiz):
    try:
        import pipeline
        from modules.reconcile import reconcile

        image_paths = [e.get("path") for e in wiz.get("evidence", []) if e.get("path")]
        ocr_result = pipeline.extract_entities_detailed(image_paths)
        entities = ocr_result.get("entities", {})
        wiz["evidence_review"] = {
            "typed_text": wiz.get("incident_text", ""),
            "ocr_result": ocr_result,
            "entities": entities,
            "reconciliation": reconcile(wiz.get("incident_text", ""), entities),
            "confirmed": False,
        }
        _apply_ocr_to_guided_intake(wiz, ocr_result)
    except Exception as exc:
        st.error(f"Evidence extraction could not run: {exc}")


def _confident_ocr_value(ocr_result, key, minimum_confidence=0.75):
    """Return one unambiguous OCR value; skip missing or competing readings."""
    matches = (ocr_result or {}).get("detailed", {}).get(key, [])
    matches = [item for item in matches if item.get("value") not in (None, "")]
    if len(matches) != 1 or float(matches[0].get("confidence", 0)) < minimum_confidence:
        return None
    return str(matches[0]["value"]).strip()


def _apply_ocr_to_guided_intake(wiz, ocr_result):
    """Use clear OCR reads to fill missing intake slots and advance the prompt."""
    intake = wiz.get("guided_intake", {})
    if not intake.get("started"):
        return
    docket = intake.setdefault("docket", {})
    filled = []
    safe_entities = {
        key: value
        for key in ("amount", "transaction_ref", "upi_id", "phone", "platform", "date", "time")
        if (value := _confident_ocr_value(ocr_result, key)) is not None
    }
    if safe_entities:
        # Prefill the structured transaction placeholders too. The evidence
        # review below still lets the person verify every OCR reading.
        _apply_reviewed_entities_to_wizard(wiz, safe_entities)

    def fill(slot, value):
        if value not in (None, "") and docket.get(slot) in (None, ""):
            docket[slot] = value
            filled.append(slot)

    amount_raw = _confident_ocr_value(ocr_result, "amount")
    if amount_raw:
        try:
            fill("financial_loss_amount", float(re.sub(r"[^\d.]", "", amount_raw.replace(",", ""))))
            if "financial_loss_amount" in filled:
                docket["has_financial"] = True
        except ValueError:
            pass

    fill("utr_number", safe_entities.get("transaction_ref"))
    fill("suspect_details", safe_entities.get("upi_id") or safe_entities.get("phone"))
    fill("platform_involved", safe_entities.get("platform"))
    fill("date_time_of_incident", safe_entities.get("date"))
    if not filled:
        return

    docket["evidence_available"] = True
    retry_counts = dict(docket.get("retry_counts", {}))
    from modules.conversational_agent import select_next_question

    language = intake.get("language", "en")
    question, _question_en, next_field = select_next_question(docket, language, retry_counts)
    if next_field:
        retry_counts[next_field] = retry_counts.get(next_field, 0) + 1
    docket["retry_counts"] = retry_counts
    docket["pending_field"] = next_field
    docket["is_complete"] = next_field is None
    intake["complete"] = next_field is None

    if intake.get("messages"):
        latest = intake["messages"][-1]
        if latest.get("role") == "assistant":
            if language == "hi":
                acknowledgement = "मैंने स्क्रीनशॉट से पढ़ी जा सकने वाली जानकारी दर्ज कर दी है। "
            elif language == "mr":
                acknowledgement = "स्क्रीनशॉटमधून वाचता आलेली माहिती मी नोंदवली आहे. "
            else:
                acknowledgement = "I read the available details from your screenshot and added them. "
            latest["content"] = acknowledgement + question


def _clear_evidence_conflict_choices():
    for key in list(st.session_state.keys()):
        if key.startswith("evidence_conflict_"):
            del st.session_state[key]


def _first_evidence_value(entities, *keys):
    for key in keys:
        value = (entities or {}).get(key)
        if isinstance(value, list):
            candidates = list(dict.fromkeys(item for item in value if item not in (None, "")))
            if len(candidates) != 1:
                continue
            value = candidates[0]
        if value not in (None, ""):
            return value
    return None


def _parse_evidence_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%m-%Y", "%d/%m/%Y",
                "%d-%m-%y", "%d/%m/%y", "%Y-%m-%d", "%d %b %y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _apply_reviewed_entities_to_wizard(wiz, entities):
    """Put victim-confirmed OCR values into the structured form fields."""
    amount_raw = _first_evidence_value(entities, "amount")
    amount = None
    if amount_raw:
        try:
            amount = float(re.sub(r"[^\d.]", "", str(amount_raw).replace(",", "")))
        except ValueError:
            amount = None

    transaction_ref = _first_evidence_value(entities, "transaction_ref", "utr", "rrn")
    upi_id = _first_evidence_value(entities, "upi_id")
    account_last4 = _first_evidence_value(entities, "account_last4", "card_last4")
    raw_date = _first_evidence_value(entities, "date")
    evidence_date = _parse_evidence_date(raw_date)
    raw_time = _first_evidence_value(entities, "time")
    evidence_time = None
    if raw_time:
        for time_format in ("%I:%M %p", "%I:%M%p", "%H:%M:%S", "%H:%M"):
            try:
                evidence_time = datetime.strptime(str(raw_time).strip(), time_format).time()
                break
            except ValueError:
                continue
    platforms = entities.get("platform", []) if entities else []
    if not isinstance(platforms, list):
        platforms = [platforms]
    platform = next((str(item).strip() for item in platforms if item), None)
    payment_apps = {
        "phonepe", "google pay", "gpay", "paytm", "bhim", "amazon pay", "mobikwik",
        "sbi", "hdfc", "icici", "axis", "kotak", "pnb", "bank of baroda", "canara",
    }
    payment_platforms = list(dict.fromkeys(
        str(item).strip() for item in platforms
        if str(item).strip().casefold() in payment_apps
    ))
    payment_platform = payment_platforms[0] if len(payment_platforms) == 1 else None

    if amount is not None or transaction_ref or account_last4 or payment_platform:
        wiz["lost_money"] = "Yes" if amount is not None or transaction_ref else wiz.get("lost_money", "No")
        rows = wiz.setdefault("transactions", [])
        row = rows[0] if rows else {}
        if payment_platform:
            row["bank"] = row.get("bank") or payment_platform
        if amount is not None:
            row["amount"] = amount
        if transaction_ref:
            row["transaction_id"] = str(transaction_ref)
            row["reference_no"] = str(transaction_ref)
        if account_last4:
            row["account_no"] = f"Account ending {account_last4}"
        if raw_date:
            row["transaction_date"] = evidence_date.isoformat() if evidence_date else str(raw_date)
        if not rows:
            rows.append(row)
        if wiz["lost_money"] == "Yes":
            st.session_state["lost_money_form"] = "Yes"
            st.session_state["txn_bank_input"] = row.get("bank", "")
            st.session_state["txn_amount_input"] = float(row.get("amount") or 0)
            st.session_state["txn_utr_input"] = row.get("transaction_id", "")
            if evidence_date:
                st.session_state["txn_date_input"] = evidence_date
                st.session_state["txn_date_confirmed"] = True

    if upi_id:
        wiz["has_suspect_txn"] = "Yes"
        rows = wiz.setdefault("suspect_transactions", [])
        row = rows[0] if rows else {}
        row.update({
            "method": "UPI",
            "bank": row.get("bank") or str(upi_id).split("@")[-1].upper(),
            "account_no": str(upi_id),
        })
        if transaction_ref:
            row["transaction_id"] = str(transaction_ref)
        if amount is not None:
            row["amount"] = amount
        if raw_date:
            row["transaction_date"] = evidence_date.isoformat() if evidence_date else str(raw_date)
        if not rows:
            rows.append(row)
        st.session_state["has_suspect_txn_form"] = "Yes"
        st.session_state["suspect_method_input"] = "UPI"
        st.session_state["suspect_bank_input"] = row["bank"]
        st.session_state["suspect_identifier_input"] = row["account_no"]
        st.session_state["suspect_utr_input"] = row.get("transaction_id", "")
        st.session_state["suspect_amount_input"] = float(row.get("amount") or 0)
        if evidence_date:
            st.session_state["suspect_date_input"] = evidence_date

    mapped_locations = [
        location for location in INCIDENT_LOCATIONS
        if any(location.casefold() == str(item).casefold() for item in platforms)
    ]
    if mapped_locations:
        current = wiz.get("incident_location", [])
        wiz["incident_location"] = list(dict.fromkeys(current + mapped_locations))

    if evidence_date and evidence_date <= date.today():
        wiz["incident_date"] = evidence_date
        st.session_state["occurrence_date_input"] = evidence_date
        st.session_state["occurrence_date_confirmed"] = True
    if evidence_time:
        wiz["incident_time"] = evidence_time
        st.session_state["occurrence_time_input"] = evidence_time
        st.session_state["occurrence_time_confirmed"] = True

    wiz["ocr_prefill_summary"] = {
        key: value for key, value in {
            "Amount": amount,
            "Reference": transaction_ref,
            "Recipient UPI ID": upi_id,
            "Masked account/card ending": account_last4,
            "Date": evidence_date.isoformat() if evidence_date else raw_date,
            "Time": evidence_time.strftime("%H:%M") if evidence_time else raw_time,
            "Payment app / platform": platform,
        }.items() if value not in (None, "")
    }
    if "lost_money_form" not in st.session_state:
        st.session_state["lost_money_form"] = wiz.get("lost_money", "No")
    if "has_suspect_txn_form" not in st.session_state:
        st.session_state["has_suspect_txn_form"] = wiz.get("has_suspect_txn", "No")


def _run_full_triage(wiz):
    with st.spinner("Reviewing your description and any confirmed file details..."):
        try:
            guided_docket = wiz.get("guided_intake", {}).get("docket", {})
            if guided_docket.get("complainant_age") is not None and not wiz.get("age"):
                wiz["age"] = int(guided_docket["complainant_age"])
            import pipeline
            image_paths = [e.get("path") for e in wiz.get("evidence", []) if e.get("path")]
            evidence_review = wiz.get("evidence_review") or {}
            triage_res = pipeline.triage_complaint(
                wiz["incident_text"],
                attachments=image_paths,
                verbose=False,
                ocr_result_override=evidence_review.get("ocr_result"),
                reviewed_entities=evidence_review.get("reviewed_entities"),
                reviewed_evidence_summary=evidence_review.get("summary"),
            )
            wiz["triage"] = triage_res
            wiz["sentiment"] = triage_res.get("sentiment") or wiz.get("sentiment")

            # Enhanced with v2 Auto-Fill & MO-KB
            if _v2_modules_available:
                try:
                    af_payload = generate_autofill_payload(
                        wiz["incident_text"],
                        ocr_entities=triage_res.get("entities", {})
                    )
                    wiz["autofill_payload"] = af_payload
                    if af_payload.get("matched_mo"):
                        wiz["mo_match"] = af_payload["matched_mo"]
                        wiz["modus_operandi"] = af_payload["matched_mo"]["name"]
                    
                    if af_payload.get("transactions") and not wiz.get("transactions"):
                        wiz["lost_money"] = "Yes"
                        wiz["transactions"] = af_payload["transactions"]
                    if af_payload.get("suspect_transactions") and not wiz.get("suspect_transactions"):
                        wiz["has_suspect_txn"] = "Yes"
                        wiz["suspect_transactions"] = af_payload["suspect_transactions"]
                    if af_payload.get("suspects") and not wiz.get("suspects"):
                        wiz["suspects"] = af_payload["suspects"]
                except Exception:
                    pass

            sub_cat = triage_res.get("sub_category")
            conf = triage_res.get("confidence", 0.0)
            if sub_cat and sub_cat != "UNCLASSIFIED":
                wiz["ai_sub_category"] = sub_cat
                wiz["ai_confidence"] = conf
                wiz["sub_category"] = sub_cat
                wiz["category"] = SUB_TO_MAIN_CATEGORY.get(sub_cat, MAIN_CATEGORIES[-1])
                wiz["modus_operandi"] = MODUS_OPERANDI_HINTS.get(sub_cat, "")

            ext = dict(triage_res.get("extracted_fields", {}))
            qa = wiz.get("qa_answers", {})
            for k, v in qa.items():
                if v and not ext.get(k):
                    ext[k] = v

            amt_raw = ext.get("amount") or qa.get("amount")
            if amt_raw and not wiz.get("transactions"):
                amt_clean = re.sub(r"[^\d.]", "", str(amt_raw).split(",")[0])
                try:
                    amt_val = float(amt_clean)
                    if amt_val > 0:
                        wiz["lost_money"] = "Yes"
                        utr_val = re.sub(r"\D", "", str(ext.get("transaction_ref") or qa.get("transaction_ref") or ""))
                        wiz["transactions"].append({
                            "bank": ext.get("platform") or qa.get("platform") or "Bank/Wallet",
                            "account_no": ext.get("account_last4") or ext.get("card_last4") or "UPI / Debit",
                            "transaction_id": utr_val[:12] if len(utr_val) >= 12 else utr_val,
                            "amount": amt_val,
                            "transaction_date": ext.get("date") or qa.get("date"),
                            "reference_no": ext.get("transaction_ref") or qa.get("transaction_ref") or "",
                        })
                except Exception:
                    pass

            suspect_ident = ext.get("upi_id") or ext.get("phone") or qa.get("upi_id") or qa.get("phone")
            if suspect_ident and not wiz.get("suspect_transactions"):
                wiz["has_suspect_txn"] = "Yes"
                wiz["suspect_transactions"].append({
                    "method": "UPI" if ("@" in str(suspect_ident) or ext.get("upi_id")) else "Mobile / Call",
                    "bank": "Suspect Account / Platform",
                    "account_no": str(suspect_ident),
                    "transaction_id": re.sub(r"\D", "", str(ext.get("transaction_ref") or qa.get("transaction_ref") or "")),
                    "amount": 0.0,
                    "transaction_date": ext.get("date"),
                })

            plat = ext.get("platform") or qa.get("platform")
            if plat and not wiz.get("incident_location"):
                matched = [p for p in INCIDENT_LOCATIONS if p.lower() in plat.lower() or plat.lower() in p.lower()]
                if matched:
                    wiz["incident_location"] = matched

            st.session_state["wizard_step"] = 2
            st.rerun()

        except Exception as e:
            st.error(f"Intake Triage Notice: {e}")
            st.session_state["wizard_step"] = 2
            st.rerun()


def page_report_wizard():
    st.title("Prepare a complaint draft")
    st.caption("Use everyday language. You can review and change the draft before saving it on this computer.")
    progress_steps(st.session_state["wizard_step"])
    pre_filing_checklist()
    st.link_button("Go to the official cybercrime portal", "https://www.cybercrime.gov.in/")
    step = st.session_state["wizard_step"]
    if step == 1:
        render_step1()
    elif step == 2:
        render_step2()
    else:
        render_step3()


def render_step1():
    wiz = st.session_state["wiz"]
    intake = wiz.setdefault("guided_intake", {"started": False, "complete": False, "messages": [], "docket": {}, "language": "en", "initial_statement": ""})

    section_header("Start a complaint draft")
    st.markdown(
        "Start with what you remember. You do not need legal terms or exact dates. The assistant may ask a few questions; it is okay to answer “I don’t know.”"
    )

    # Voice Input Feature (English priority with offline Whisper)
    if _stt_available:
        with st.expander("Prefer to speak? Record or upload a voice note (optional)", expanded=False):
            st.markdown(
                """
                <div style="background:#f1f5f9; border-left:4px solid #1d4ed8; padding:10px 14px; border-radius:4px; margin-bottom:12px;">
                    <div style="font-weight:600; color:#0f172a; font-size:0.92rem;">
                        Speak your complaint (optional)
                    </div>
                    <div style="font-size:0.82rem; color:#475569; margin-top:2px;">
                        Record a voice note and the app will try to transcribe it on this computer, then start the assistant. Review the transcript in the conversation and correct anything that is wrong.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_lang, col_mode = st.columns([2, 2])
            with col_lang:
                lang_mode = st.radio(
                    "Choose spoken language",
                    options=["English (en)", "Detect language automatically"],
                    index=0,
                    horizontal=True,
                    key="voice_lang_choice",
                )
            with col_mode:
                text_action = st.radio(
                    "If text is already entered",
                    options=["Add spoken words after it", "Replace it with spoken words"],
                    index=0,
                    horizontal=True,
                    key="voice_text_action",
                )

            live_mic = st.audio_input(
                "Record a voice note",
                key="live_voice_dictate",
            )

            target_lang = "en" if "English" in lang_mode else None

            if live_mic is not None:
                audio_hash = f"{getattr(live_mic, 'name', 'voice')}_{live_mic.size}_{target_lang}"
                if st.session_state.get("_last_transcribed_audio_id") != audio_hash:
                    with st.spinner("🎙️ Transcribing voice using offline speech recognition..."):
                        res = transcribe_audio_bytes(
                            live_mic,
                            filename="live_mic.wav",
                            language=target_lang,
                            model_name="base",
                        )
                        if res.get("ok") and res.get("text", "").strip():
                            spoken = res["text"].strip()
                            current_val = wiz.get("incident_text", "").strip()
                            if text_action == "Replace it with spoken words" or not current_val:
                                new_val = spoken
                            else:
                                new_val = f"{current_val}\n\n{spoken}".strip()

                            wiz["incident_text"] = new_val
                            st.session_state["_last_wiz_text_seen"] = new_val
                            st.session_state["_pending_voice_intake_text"] = spoken
                            wiz["stt_metadata"] = {
                                "transcribed": True,
                                "language": res.get("language", "en"),
                                "language_name": res.get("language_name", "English"),
                                "language_confidence": res.get("language_prob", 1.0),
                                "audio_duration_seconds": res.get("duration_seconds", 0.0),
                                "transcription_latency_seconds": res.get("latency_seconds", 0.0),
                                "model_used": "base",
                            }
                            st.session_state["_last_transcribed_audio_id"] = audio_hash
                            st.success(f"✓ Transcribed [{res.get('language_name', 'English')}]: \"{spoken[:120]}{'...' if len(spoken) > 120 else ''}\"")
                            st.rerun()
                        elif not res.get("ok"):
                            st.error(f"Voice transcription error: {res.get('error', 'Unknown error')}")

            with st.expander("📁 Or upload pre-recorded audio file (.wav, .mp3, .m4a)", expanded=False):
                uploaded_voice = st.file_uploader(
                    "Upload Voice Note",
                    type=["wav", "mp3", "m4a", "ogg", "flac"],
                    key="voice_file_upload",
                )
                if uploaded_voice is not None:
                    up_audio_hash = f"{uploaded_voice.name}_{uploaded_voice.size}_{target_lang}"
                    if st.session_state.get("_last_transcribed_file_id") != up_audio_hash:
                        with st.spinner("Transcribing uploaded audio..."):
                            res = transcribe_audio_bytes(
                                uploaded_voice,
                                filename=uploaded_voice.name,
                                language=target_lang,
                                model_name="base",
                            )
                            if res.get("ok") and res.get("text", "").strip():
                                spoken = res["text"].strip()
                                current_val = wiz.get("incident_text", "").strip()
                                if text_action == "Replace it with spoken words" or not current_val:
                                    new_val = spoken
                                else:
                                    new_val = f"{current_val}\n\n{spoken}".strip()
                                wiz["incident_text"] = new_val
                                st.session_state["_last_wiz_text_seen"] = new_val
                                st.session_state["_pending_voice_intake_text"] = spoken
                                st.session_state["_last_transcribed_file_id"] = up_audio_hash
                                st.success(f"✓ Transcribed from file: \"{spoken[:120]}...\"")
                                st.rerun()
                            elif not res.get("ok"):
                                st.error(f"Failed to transcribe audio file: {res.get('error')}")

    else:
        with st.expander("Prefer to speak? Voice transcription is not set up", expanded=True):
            st.warning(
                "Voice input is unavailable because the Whisper speech-recognition package "
                "is not installed in the Python environment running this app."
            )
            st.code("python -m pip install -r requirements.txt\n# Then restart Streamlit", language="powershell")
            st.caption(
                "The microphone control appears after Whisper is installed. "
                "The first transcription may download the local model."
            )

    st.caption("The assistant will ask one question at a time if it needs more detail.")
    if not intake.get("started"):
        language = st.selectbox(
            "Conversation language",
            options=[("English", "en"), ("हिन्दी", "hi"), ("मराठी", "mr")],
            format_func=lambda option: option[0],
            key="guided_intake_language",
        )[1]
    else:
        language = intake.get("language", "en")

    for message in intake.get("messages", []):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    last_docket = intake.get("docket", {})
    if intake.get("started") and last_docket.get("llm_error"):
        st.warning(
            f"The {last_docket.get('llm_provider', 'AI')} response could not be used after a retry; "
            f"the intake's approved response was used instead. Details: {last_docket['llm_error']}"
        )

    voice_message = st.session_state.pop("_pending_voice_intake_text", None)
    typed_message = ""
    submitted = False
    with st.form("guided_intake_message_form", clear_on_submit=True):
        typed_message = st.text_area(
            "What happened?" if not intake.get("started") else (
                "Add details or correct an answer" if intake.get("complete") else "Your answer"
            ),
            height=130,
            key="guided_intake_message_box",
            placeholder=(
                "For example: what happened, when it began, how you were contacted, and whether money or an account was affected. Share only details you are comfortable providing."
                if not intake.get("started")
                else "Type your answer, add a detail, or correct something in the draft."
            ),
        )
        submitted = st.form_submit_button(
            "Continue" if not intake.get("started") else (
                "Update intake" if intake.get("complete") else "Send answer"
            ),
            type="primary",
        )
    user_message = voice_message or (typed_message if submitted else "")
    if user_message:
        try:
            from modules.conversational_agent import conduct_counselor_turn
            is_first_turn = not intake.get("started")
            history = list(intake.get("messages", [])) if not is_first_turn else []
            with st.spinner("The AI assistant is preparing a response..."):
                result = conduct_counselor_turn(
                    user_message=user_message.strip(),
                    conversation_history=history,
                    current_docket=intake.get("docket", {}) if not is_first_turn else {},
                    language=language,
                )
            if is_first_turn:
                intake["started"] = True
                intake["language"] = language
                intake["initial_statement"] = user_message.strip()
            intake["docket"] = result
            intake["complete"] = result.get("is_complete", False)
            intake.setdefault("messages", []).extend([
                {"role": "user", "content": user_message.strip()},
                {"role": "assistant", "content": result.get("spoken_response", "")},
            ])
            st.rerun()
        except Exception as exc:
            st.error(f"Could not process your message: {exc}")

    if intake.get("started"):
        if not intake.get("complete"):
            if st.button("Finish intake with details provided", key="finish_guided_intake"):
                intake["complete"] = True
                st.rerun()
        else:
            st.success("Follow-up questions are complete. You can still edit your description and review any evidence before continuing.")
            if st.button("Restart guided intake", key="restart_guided_intake"):
                initial_statement = intake.get("initial_statement", "")
                wiz["guided_intake"] = {
                    "started": False, "complete": False, "messages": [], "docket": {},
                    "language": "en", "initial_statement": "",
                }
                wiz["incident_text"] = initial_statement
                st.session_state["_last_wiz_text_seen"] = None
                st.rerun()

        user_turns = [m["content"] for m in intake.get("messages", []) if m.get("role") == "user"]
        if user_turns:
            wiz["incident_text"] = "\n\n".join(user_turns)

    text = wiz.get("incident_text", "")
    n = len(text.strip())
    if n > 0:
        st.caption(f"{n} characters entered. A little more detail can help the assistant understand what happened.")

    show_evidence_inline = (
        last_docket.get("pending_field") == "evidence"
        or last_docket.get("evidence_available") is True
    )
    # Render evidence controls after the message box so the response field is
    # always visible above the uploader, including when evidence was requested.
    evidence_ui = st.container()
    with evidence_ui:
        section_header("Add screenshots or documents" if show_evidence_inline else "Add screenshots or documents (optional)")
        if show_evidence_inline:
            st.info("Attach the screenshot here. The app will read it with OCR, show the values it found, and prefill the matching complaint fields after you confirm them.")
        st.caption("You may add a payment receipt, message, or profile screenshot so the app can try to read relevant details. "
                   f"Accepted files: JPG, PNG, PDF (up to {MAX_UPLOAD_MB} MB each). Never upload a PIN, password, or one-time code.")

        uploads = st.file_uploader("Choose screenshots or documents", type=["jpg", "jpeg", "png", "pdf"],
                                    accept_multiple_files=True, key="evidence_files_upload")
        desc = st.text_input("What does this file show? (optional)", placeholder="For example: payment receipt", key="evidence_description")
        if st.button("Upload files and read details" if show_evidence_inline else "Add selected files", key="add_evidence_files"):
            if not uploads:
                st.warning("Select files to upload first.")
            else:
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                added, skipped = 0, []
                for uf in uploads:
                    if uf.size > MAX_UPLOAD_MB * 1024 * 1024:
                        skipped.append(uf.name)
                        continue
                    dest = os.path.join(UPLOAD_DIR, f"{len(wiz['evidence'])}_{uf.name}")
                    with open(dest, "wb") as out:
                        out.write(uf.getbuffer())
                    wiz["evidence"].append({"description": desc.strip(), "text_information": "",
                                            "filename": uf.name, "path": dest})
                    wiz["evidence_review"] = None
                    _clear_evidence_conflict_choices()
                    added += 1
                if skipped:
                    st.error(f"Skipped files exceeding {MAX_UPLOAD_MB}MB limit: {', '.join(skipped)}")
                if added:
                    st.success(f"Successfully attached {added} document(s). Running OCR now...")
                    _run_evidence_review(wiz)
                    st.rerun()

        if wiz["evidence"]:
            st.markdown("**Files added**")
            for i, e in enumerate(wiz["evidence"]):
                cols = st.columns([0.5, 3, 3, 1])
                cols[0].write(f"#{i+1}")
                cols[1].write(f"File: **{e['filename']}**")
                cols[2].write(e.get("description") or "—")
                if cols[3].button("Remove", key=f"del_ev1_{i}"):
                    wiz["evidence"].pop(i)
                    wiz["evidence_review"] = None
                    _clear_evidence_conflict_choices()
                    st.rerun()

            st.divider()
            section_header("Check what the app read")
            if st.button("Read details from my files again", key="extract_evidence_text"):
                _clear_evidence_conflict_choices()
                _run_evidence_review(wiz)
                st.rerun()

            evidence_review = wiz.get("evidence_review")
            if evidence_review:
                ocr_result = evidence_review.get("ocr_result", {})
                entities = evidence_review.get("entities", {})
                reconciliation = evidence_review.get("reconciliation", {})
                for image_result in ocr_result.get("per_image", []):
                    with st.expander(f"Text read from: {image_result.get('file', 'evidence file')}"):
                        st.text(image_result.get("raw_text") or "No readable text was extracted from this file.")
                if ocr_result.get("errors"):
                    for error in ocr_result["errors"]:
                        st.warning(f"{error.get('file', 'Evidence')}: {error.get('error', 'OCR could not read this file.')}")
                if entities:
                    st.markdown("**Details the app found**")
                    st.dataframe(
                        pd.DataFrame([
                            {"Field": key.replace("_", " ").title(),
                             "OCR reading": format_entity_reading(value)}
                            for key, value in entities.items()
                        ], columns=["Field", "OCR reading"]),
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info("OCR did not extract structured details. You can continue using the complaint text and manually confirm details in the next step.")

                conflicts = reconciliation.get("conflicts", [])
                conflict_choices = {}
                for index, conflict in enumerate(conflicts):
                    field_name = conflict.get("field", "detail")
                    typed_values = ", ".join(str(value) for value in conflict.get("typed_mentions", [])) or "the complaint text"
                    choice = st.selectbox(
                        f"These details differ. Your description says {typed_values}; the file appears to show {conflict.get('ocr_value', '')}. Which is correct?",
                        options=["Select the confirmed value", "Use the complaint value", "Use the evidence reading"],
                        key=f"evidence_conflict_{index}_{field_name}",
                    )
                    conflict_choices[field_name] = (choice, conflict)

                facts = []
                reviewed_entities = dict(entities)
                unresolved = False
                for field_name, (choice, conflict) in conflict_choices.items():
                    if choice == "Select the confirmed value":
                        unresolved = True
                    elif choice == "Use the complaint value":
                        reviewed_entities.pop(field_name, None)
                        typed_values = ", ".join(str(value) for value in conflict.get("typed_mentions", []))
                        facts.append(f"Victim-confirmed {field_name.replace('_', ' ')}: {typed_values}")
                    else:
                        facts.append(f"Victim-confirmed {field_name.replace('_', ' ')}: {conflict.get('ocr_value', '')}")
                for field_name, value in reviewed_entities.items():
                    if field_name not in conflict_choices:
                        facts.append(f"{field_name.replace('_', ' ').title()}: {value}")
                summary = "\n".join(facts)
                if summary:
                    st.markdown("**Summary for you to check**")
                    st.text(summary)
                if reconciliation.get("agreements"):
                    st.caption(f"{len(reconciliation['agreements'])} detail(s) match the complaint text.")

                if st.button("Confirm these details", type="primary", key="confirm_evidence_review"):
                    if unresolved:
                        st.warning("Choose which value is correct for each flagged difference before continuing.")
                    elif evidence_review.get("typed_text") != wiz.get("incident_text", ""):
                        st.warning("The complaint text changed after OCR. Extract it again before confirming.")
                    else:
                        evidence_review["reviewed_entities"] = reviewed_entities
                        evidence_review["summary"] = summary
                        evidence_review["confirmed"] = True
                        _apply_reviewed_entities_to_wizard(wiz, reviewed_entities)
                        st.rerun()
                if ocr_result.get("errors") and st.button(
                    "Continue with detected OCR details",
                    key="continue_with_detected_ocr",
                    disabled=(
                        unresolved
                        or evidence_review.get("typed_text") != wiz.get("incident_text", "")
                    ),
                ):
                    evidence_review["reviewed_entities"] = reviewed_entities
                    evidence_review["summary"] = summary
                    evidence_review["confirmed"] = True
                    _apply_reviewed_entities_to_wizard(wiz, reviewed_entities)
                    st.rerun()
                if evidence_review.get("confirmed"):
                    st.success("Thanks. The confirmed details can now be used in the assessment.")

    st.divider()

    col_act1, col_act2 = st.columns([1, 1.2])
    evidence_review = wiz.get("evidence_review") or {}
    evidence_ready = not wiz.get("evidence") or (
        evidence_review.get("confirmed")
        and evidence_review.get("typed_text") == wiz.get("incident_text", "")
    )
    if wiz.get("evidence") and not evidence_ready:
        if evidence_review and evidence_review.get("typed_text") != wiz.get("incident_text", ""):
            st.warning("The complaint text changed after evidence extraction. Extract and review the evidence again before classification.")
        else:
            st.info("Extract and review the attached evidence before classification.")
    guided_ready = (not intake.get("started") or intake.get("complete")) and evidence_ready
    with col_act1:
        if st.button("Check what details may be missing", type="secondary", width="stretch"):
            if not text.strip() and not wiz["evidence"]:
                st.error("Please enter an incident statement or attach evidence documentation first.")
            else:
                with st.spinner("Checking the details you provided..."):
                    gaps_res = detect_gaps(text) if detect_gaps else {}
                    sent_res = analyze_sentiment_and_urgency(text) if analyze_sentiment_and_urgency else {}
                    wiz["intake_analysis"] = {"gaps": gaps_res, "sentiment": sent_res}
                    wiz["sentiment"] = sent_res
                    if _v2_modules_available:
                        mo_res = match_mo(text)
                        if mo_res:
                            wiz["mo_match"] = mo_res
                    st.rerun()
    with col_act2:
        if st.button("Review details and suggest a category", type="primary", width="stretch", disabled=not guided_ready):
            if not text.strip() and not wiz["evidence"]:
                st.error("Please enter an incident narrative or speak into the mic first.")
            else:
                _run_full_triage(wiz)
    # -------------------------------------------------------------------------
    # INTAKE COMPLETENESS & ADVISORY DISPLAY
    # -------------------------------------------------------------------------
    analysis = wiz.get("intake_analysis")
    if analysis:
        sent = analysis.get("sentiment") or {}
        gaps = analysis.get("gaps") or {}
        comp = sent.get("comprehension") or {}
        score = gaps.get("completeness_score", 0.5)
        is_gold = sent.get("is_golden_hour", False)
        urg_lvl = sent.get("urgency_level")

        st.write("")
        st.markdown("---")
        section_header("Information check")

        if wiz.get("mo_match"):
            mo = wiz["mo_match"]
            st.markdown(
                f"""<div style="background:#eef4fa;border:1px solid #93c5fd;border-left:5px solid {SEQ_BLUE};padding:14px 18px;border-radius:4px;margin-bottom:14px;">
                      <div style="font-weight:800;color:{GOV_BLUE};font-size:0.95em;letter-spacing:0.02em;">
                        IDENTIFIED MODUS OPERANDI: {mo['name'].upper()}
                      </div>
                      <div style="font-size:0.88em;color:#334155;margin-top:4px;">
                        <b>Primary Statutory Mapping:</b> {mo['primary_ncrp_subcategory']} &bull; <b>Confidence:</b> {int(mo.get('match_score', 0.9)*100)}%
                      </div>
                      <div style="font-size:0.85em;color:#475569;margin-top:4px;">
                        <b>Typical Attack Pattern:</b> {'; '.join(mo.get('attack_chain', [])[:2])}
                      </div>
                    </div>""",
                unsafe_allow_html=True
            )

        if _v2_modules_available:
            with st.expander("Bank and evidence guidance", expanded=False):
                try:
                    vg_res = generate_victim_guidance(
                        mo_id=wiz.get("mo_match", {}).get("mo_id"),
                        incident_date=wiz["incident_date"].isoformat() if wiz.get("incident_date") else None,
                    )
                    st.markdown(vg_res["advisory_markdown"])
                except Exception:
                    pass

        if is_gold:
            st.error("If money was taken recently, call 1930 promptly and contact your bank using its official contact details. This app cannot stop or recover a payment.")
        elif urg_lvl == "HIGH_URGENCY":
            st.warning("If someone is threatening you or you are in immediate danger, contact emergency services. Save messages or screenshots if it is safe to do so.")

        reassurance = sent.get("reassurance") or {}
        if reassurance.get("message"):
            st.markdown(
                f"""<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-left:5px solid #16a34a;padding:14px 18px;border-radius:4px;margin-bottom:14px;">
                      <div style="font-weight:800;color:#166534;font-size:0.95em;letter-spacing:0.03em;text-transform:uppercase;">
                        {html.escape(reassurance.get('title', 'Citizen Guidance & Protective Advisory'))}
                      </div>
                      <div style="font-size:0.88em;color:#374151;margin-top:5px;line-height:1.45;">
                        {html.escape(reassurance.get('message', ''))}
                      </div>
                    </div>""",
                unsafe_allow_html=True,
            )
            with st.expander("Helpful next steps", expanded=False):
                for step_text in reassurance.get("immediate_steps", []):
                    st.markdown(f"- {step_text}")

        c_comp1, c_comp2, c_comp3 = st.columns([1.5, 1.2, 1.1])
        c_comp1.markdown(f"**Possible incident type:** {comp.get('crime_vector', 'Cyber incident')}")
        c_comp2.markdown(f"**Money mentioned:** {comp.get('financial_impact', 'Not specified')}")
        c_comp3.markdown(f"**Priority estimate:** {urgency_badge(sent.get('urgency_level'), is_gold)}", unsafe_allow_html=True)

        if comp.get("summary"):
            st.caption(f"**Short summary:** {comp['summary']}")

        st.write("")
        st.markdown(f"**Information check (rough estimate):** `{int(score * 100)}%`")
        st.progress(score)
        st.caption("This estimate is only a guide. It does not decide whether a complaint can be made or guarantee a result.")

        if score < 0.75:
            st.caption("Some extra details may help make the draft clearer. You can skip anything you do not know.")

        questions = gaps.get("questions", [])
        qa_round = wiz.get("qa_round", 0)

        if questions and qa_round < 2 and score < 0.85 and not intake.get("started"):
            st.write("")
            st.markdown(
                f"""<div style="background:#f8fafc;border:1px solid #cbd5e1;border-left:4px solid {SEQ_BLUE};padding:14px 18px;border-radius:4px;margin-bottom:12px;">
                      <div style="font-weight:800;color:{GOV_BLUE_DARK};font-size:0.95em;letter-spacing:0.03em;text-transform:uppercase;">
                        A few optional questions ({qa_round + 1} of 2)
                      </div>
                      <div style="font-size:0.86em;color:#475569;margin-top:4px;">
                        Answer what you can. It is okay to skip a detail you do not know.
                      </div>
                    </div>""",
                unsafe_allow_html=True,
            )

            answers_given = {}
            for i, q in enumerate(questions[:3]):
                field_id = q.get("field", f"f_{i}")
                q_text = q.get("question", "Additional detail:")
                ans_val = st.text_input(q_text, key=f"qa_field_{field_id}",
                                        placeholder="Type an answer if you know it, or leave blank")
                if ans_val.strip():
                    answers_given[field_id] = ans_val.strip()

            c_qabtn1, c_qabtn2 = st.columns([1.2, 1])
            with c_qabtn1:
                if st.button("Add details and check again", type="primary", width="stretch"):
                    if not answers_given:
                        st.warning("Please fill in at least one field above or proceed directly to Step 2.")
                    else:
                        addendum_lines = [f"{k.replace('_', ' ').title()}: {v}" for k, v in answers_given.items()]
                        new_story = wiz["incident_text"].strip() + "\n\n[Clarification Details Provided]: " + "; ".join(addendum_lines)
                        wiz["incident_text"] = new_story
                        wiz["qa_answers"].update(answers_given)
                        wiz["qa_round"] = qa_round + 1

                        new_gaps = detect_gaps(new_story) if detect_gaps else {}
                        new_sent = analyze_sentiment_and_urgency(new_story) if analyze_sentiment_and_urgency else {}
                        wiz["intake_analysis"] = {"gaps": new_gaps, "sentiment": new_sent}
                        wiz["sentiment"] = new_sent
                        st.success("Your answers were added to the draft.")
                        st.rerun()

            with c_qabtn2:
                if st.button("Continue to your details →", width="stretch"):
                    _run_full_triage(wiz)
        elif score >= 0.85 or qa_round >= 2:
            st.success("Your description is ready for review. You can still add or correct details in the next step.")
            if st.button("Continue to your details →", type="primary"):
                _run_full_triage(wiz)


def _render_delete_table(rows, list_name, fields, headers):
    if not rows:
        st.caption("No records entered.")
        return
    cols = st.columns([2] * len(fields) + [1])
    for col, h in zip(cols, headers + ["Action"]):
        col.markdown(f"**{h}**")
    for i, row in enumerate(rows):
        cols = st.columns([2] * len(fields) + [1])
        for col, f in zip(cols, fields):
            val = row.get(f, "")
            col.write(f"{val:,}" if isinstance(val, (int, float)) else str(val))
        if cols[-1].button("Remove", key=f"del_{list_name}_{i}"):
            rows.pop(i)
            st.rerun()


def render_step2():
    wiz = st.session_state["wiz"]
    triage = wiz.get("triage", {})
    section_header("Review and add details")

    ocr_prefill = wiz.get("ocr_prefill_summary") or {}
    if ocr_prefill:
        st.success("The details below were filled from the screenshot you reviewed. Check each value and correct anything OCR read incorrectly.")
        st.dataframe(
            pd.DataFrame([{"Form field": key, "Read from evidence": value} for key, value in ocr_prefill.items()]),
            hide_index=True,
            width="stretch",
        )

    if wiz.get("ai_sub_category"):
        st.markdown(
            f"""<div style="background:#f8fafc;border:1px solid #cbd5e1;border-left:4px solid {GOV_BLUE};
                            padding:14px 18px;border-radius:4px;margin-bottom:16px;">
                  <div style="font-weight:800;color:{GOV_BLUE};font-size:0.98em;">
                    AI-assisted category suggestion: {html.escape(wiz['ai_sub_category'])}
                  </div>
                  <div style="font-size:0.86em;color:#475569;margin-top:4px;">
                    This is an estimate, not a legal decision. Check the details below and change the suggestion if needed.
                  </div>
                </div>""",
            unsafe_allow_html=True,
        )

    sent = triage.get("sentiment") or wiz.get("sentiment")
    if sent and isinstance(sent, dict):
        urg_badge_html = urgency_badge(sent.get("urgency_level"), is_golden_hour=sent.get("is_golden_hour", False))
        st.markdown(
            f"""<div style="background:#ffffff;border:1px solid #cbd5e1;border-left:4px solid {GOV_BLUE};
                            padding:12px 16px;border-radius:4px;margin-bottom:16px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                    <div><b>Priority estimate:</b> &nbsp; {urg_badge_html}</div>
                  </div>
                  <div style="font-size:0.86em;color:#475569;margin-top:6px;">
                    <b>Possible incident type:</b> {html.escape(str(sent.get('comprehension', {}).get('crime_vector', 'Cyber incident')))} &nbsp;|&nbsp;
                    <b>Money mentioned:</b> {html.escape(str(sent.get('comprehension', {}).get('financial_impact', 'Not specified')))}
                  </div>
                </div>""",
            unsafe_allow_html=True,
        )

    recon = triage.get("reconciliation") or {}
    if recon.get("has_conflicts"):
        st.warning(
            f"**Please check these differences**: Your description and uploaded files show different values for "
            f"{', '.join(c.get('field', '') for c in recon.get('conflicts', []))}. "
            f"Please confirm which value is correct. The app does not choose for you."
        )
        with st.expander("View the different values", expanded=False):
            for c in recon.get("conflicts", []):
                st.markdown(f"- **{c.get('field', '').title()}**: Evidence shows `{c.get('ocr_value', '')}`, statement claims `{', '.join(str(m) for m in c.get('typed_mentions', []))}` ({c.get('resolution', '')})")
    elif recon.get("agreements"):
        st.success(f"The description and uploaded files appear to match on {len(recon['agreements'])} detail(s). Please still check them yourself.")

    missing_items = triage.get("missing_critical_info", [])
    if missing_items:
        with st.expander(f"Details you may want to add ({len(missing_items)})", expanded=False):
            for item in missing_items:
                st.markdown(f"- **{item.get('label')}**: {item.get('hint')}")

    section_header("Your details (optional in this prototype)")
    st.caption("Use fictional details for the project demonstration. You do not need to upload an identity document.")
    wiz["relationship_with_victim"] = st.radio("Are you the person affected?", ["Self", "Other"], horizontal=True,
                                                index=["Self", "Other"].index(wiz.get("relationship_with_victim", "Self")))
    c1, c2 = st.columns(2)
    with c1:
        wiz["name"] = st.text_input("Name or preferred name (optional)", value=wiz.get("name", ""))
        wiz["age"] = st.number_input("Your age (optional; leave 0 if unsure)", min_value=0, max_value=120, value=int(wiz.get("age") or 0), step=1)
        wiz["phone"] = st.text_input("Phone number (optional)", value=wiz.get("phone", ""))
    with c2:
        wiz["city"] = st.text_input("City or district (optional)", value=wiz.get("city", ""))
        wiz["state"] = st.text_input("State or union territory (optional)", value=wiz.get("state", ""))
        wiz["email"] = st.text_input("Email address (optional)", value=wiz.get("email", ""))
    with st.expander("ID document type (optional)", expanded=False):
        id_idx = COMPLAINANT_ID_TYPES.index(wiz["id_type"]) if wiz.get("id_type") in COMPLAINANT_ID_TYPES else 0
        wiz["id_type"] = st.selectbox("Choose only if useful for this record", COMPLAINANT_ID_TYPES, index=id_idx)

    section_header("Incident type")
    st.caption("The suggested type is only an estimate. Keep it or choose a closer match if one is clear.")
    c1, c2 = st.columns(2)
    with c1:
        cat_idx = MAIN_CATEGORIES.index(wiz["category"]) if wiz.get("category") in MAIN_CATEGORIES else len(MAIN_CATEGORIES) - 1
        wiz["category"] = st.selectbox(req("Broad category"), MAIN_CATEGORIES, index=cat_idx)
    with c2:
        sub_idx = KNOWN_CATEGORIES.index(wiz["sub_category"]) if wiz.get("sub_category") in KNOWN_CATEGORIES else 0
        wiz["sub_category"] = st.selectbox(req("More specific type"), KNOWN_CATEGORIES, index=sub_idx)
    wiz["modus_operandi"] = st.text_input("What happened? (optional short summary)", value=wiz.get("modus_operandi", ""))

    section_header("When did it happen? (optional)")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.setdefault("occurrence_date_input", wiz.get("incident_date") or date.today())
        st.session_state.setdefault("occurrence_date_confirmed", bool(wiz.get("incident_date")))
        selected_date = st.date_input("Approximate date", max_value=date.today(), key="occurrence_date_input")
        date_confirmed = st.checkbox("Use this date in the draft", key="occurrence_date_confirmed")
        wiz["incident_date"] = selected_date if date_confirmed else None
    with c2:
        st.session_state.setdefault("occurrence_time_input", wiz.get("incident_time") or dtime(12, 0))
        st.session_state.setdefault("occurrence_time_confirmed", bool(wiz.get("incident_time")))
        selected_time = st.time_input("Approximate time", key="occurrence_time_input")
        time_confirmed = st.checkbox("Use this time in the draft", key="occurrence_time_confirmed")
        wiz["incident_time"] = selected_time if time_confirmed else None

    section_header("If money was taken (optional)")
    st.caption("Share only details you are comfortable including. Do not enter an account number, card number, PIN, password, or one-time code.")
    st.session_state.setdefault("lost_money_form", wiz.get("lost_money", "No"))
    wiz["lost_money"] = st.radio("Was money taken from you?", ["No", "Yes"],
                                 horizontal=True, key="lost_money_form")
    if wiz["lost_money"] == "Yes":
        txn_prefill = wiz["transactions"][0] if wiz.get("transactions") else {}
        st.session_state.setdefault("txn_bank_input", txn_prefill.get("bank", ""))
        st.session_state.setdefault("txn_amount_input", float(txn_prefill.get("amount") or 0))
        st.session_state.setdefault("txn_utr_input", txn_prefill.get("transaction_id", ""))
        txn_prefill_date = _parse_evidence_date(txn_prefill.get("transaction_date"))
        if txn_prefill_date and txn_prefill_date <= date.today():
            st.session_state.setdefault("txn_date_input", txn_prefill_date)
            st.session_state.setdefault("txn_date_confirmed", True)
        with st.form("txn_form"):
            c1, c2 = st.columns(2)
            bank = c1.text_input("Bank or payment app (optional)", key="txn_bank_input")
            amount = c2.number_input("Amount lost (INR, if known)", min_value=0.0, step=100.0, key="txn_amount_input")
            utr = st.text_input("Transaction reference (optional)", key="txn_utr_input")
            txn_date = st.date_input("Transaction date (optional)", max_value=date.today(), key="txn_date_input")
            date_known = st.checkbox("I know this date is correct", key="txn_date_confirmed")
            save_txn = st.form_submit_button("Save payment details", type="primary")
        if save_txn:
            if not bank.strip() and not utr.strip() and amount <= 0:
                st.warning("Add at least one detail you know, or leave this section blank and continue.")
            else:
                updated_transaction = {
                    "bank": bank.strip(), "account_no": txn_prefill.get("account_no", ""), "transaction_id": utr.strip(),
                    "amount": amount or None, "transaction_date": txn_date.isoformat() if date_known else None,
                    "reference_no": txn_prefill.get("reference_no", ""),
                }
                if wiz.get("transactions"):
                    wiz["transactions"][0].update(updated_transaction)
                else:
                    wiz["transactions"].append(updated_transaction)
                st.success("Payment details added to the draft.")
                st.rerun()
        _render_delete_table(wiz["transactions"], "transactions",
                             ["bank", "transaction_id", "amount", "transaction_date"],
                             ["Bank/App", "Reference", "Amount (INR)", "Date"])

    section_header("Payment destination details (optional)")
    st.caption("Only add information shown in your evidence. Do not guess who received the payment.")
    st.session_state.setdefault("has_suspect_txn_form", wiz.get("has_suspect_txn", "No"))
    wiz["has_suspect_txn"] = st.radio("Do you have details about where the payment went?", ["No", "Yes"],
                                      horizontal=True, key="has_suspect_txn_form")
    if wiz["has_suspect_txn"] == "Yes":
        suspect_prefill = wiz["suspect_transactions"][0] if wiz.get("suspect_transactions") else {}
        st.session_state.setdefault("suspect_method_input", suspect_prefill.get("method", "UPI"))
        st.session_state.setdefault("suspect_bank_input", suspect_prefill.get("bank", ""))
        st.session_state.setdefault("suspect_identifier_input", suspect_prefill.get("account_no", ""))
        st.session_state.setdefault("suspect_utr_input", suspect_prefill.get("transaction_id", ""))
        st.session_state.setdefault("suspect_amount_input", float(suspect_prefill.get("amount") or 0))
        suspect_prefill_date = _parse_evidence_date(suspect_prefill.get("transaction_date"))
        if suspect_prefill_date and suspect_prefill_date <= date.today():
            st.session_state.setdefault("suspect_date_input", suspect_prefill_date)
        with st.form("suspect_txn_form"):
            c1, c2, c3 = st.columns(3)
            method = c1.selectbox("Payment method", MONEY_TRANSFER_METHODS, key="suspect_method_input")
            s_bank = c2.text_input("Recipient bank or app (if known)", key="suspect_bank_input")
            s_acct = c3.text_input("Recipient identifier shown on your evidence", key="suspect_identifier_input")
            c4, c5, c6 = st.columns(3)
            s_utr = c4.text_input("Transaction UTR", key="suspect_utr_input")
            s_amount = c5.number_input("Transferred Amount (INR)", min_value=0.0, step=100.0, key="suspect_amount_input")
            s_date = c6.date_input("Transaction Date", max_value=date.today(), key="suspect_date_input")
            save_s_txn = st.form_submit_button("Save recipient details", type="primary")
        if save_s_txn:
            if not (s_bank.strip() or s_acct.strip() or s_utr.strip()):
                st.error("Add a recipient detail shown in your evidence, or select No and continue.")
            else:
                updated_suspect_transaction = {
                    "method": method, "bank": s_bank.strip(), "account_no": s_acct.strip(),
                    "transaction_id": s_utr.strip(), "amount": s_amount, "transaction_date": s_date.isoformat(),
                }
                if wiz.get("suspect_transactions"):
                    wiz["suspect_transactions"][0].update(updated_suspect_transaction)
                else:
                    wiz["suspect_transactions"].append(updated_suspect_transaction)
                st.success("Recipient details added to the draft.")
                st.rerun()
        _render_delete_table(wiz["suspect_transactions"], "suspect_transactions",
                             ["method", "bank", "account_no", "transaction_id", "amount", "transaction_date"],
                             ["Method", "Beneficiary Bank", "Suspect Identifier", "UTR", "Amount", "Date"])

    section_header("Where did it happen? (optional)")
    wiz["incident_location"] = st.multiselect("Apps, websites, or other channels involved",
                                              INCIDENT_LOCATIONS, default=wiz.get("incident_location", []))

    section_header("Person or account involved (optional)")
    st.caption("You do not need to identify anyone. Only include details you already have; do not investigate or guess.")
    with st.form("suspect_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        s_name = c1.text_input("Name or nickname (if known)")
        id_type = c2.selectbox("Type of detail", SUSPECT_ID_TYPES)
        id_number = c3.text_input("Phone, username, or payment ID (if known)")
        add_suspect = st.form_submit_button("Add these details", type="primary")
    if add_suspect:
        if not (s_name.strip() or id_number.strip()):
            st.warning("Enter a detail you already know, or leave this section blank.")
        else:
            wiz["suspects"].append({"name": s_name.strip() or "unknown", "id_type": id_type,
                                    "id_number": id_number.strip(), "address": ""})
            st.success("Details added to the draft.")
            st.rerun()
    _render_delete_table(wiz["suspects"], "suspects", ["name", "id_type", "id_number"],
                         ["Suspect Name", "Identifier Type", "Identifier Number / Handle"])

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Back to my description", width="stretch"):
            st.session_state["wizard_step"] = 1
            st.rerun()
    with c2:
        if st.button("Review complaint record →", type="primary", width="stretch"):
            errors = []
            if not wiz["sub_category"]:
                errors.append("Choose the closest incident type, or keep the suggested type.")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                st.session_state["wizard_step"] = 3
                st.rerun()


def render_step3():
    wiz = st.session_state["wiz"]

    if st.session_state.get("last_submitted_case"):
        _render_submission_success(st.session_state["last_submitted_case"])
        return

    section_header("Review the draft")
    st.markdown(f"**What you told us:**\n\n{wiz['incident_text']}")
    
    triage = wiz.get("triage", {})
    if triage.get("standardised_narrative"):
        st.info(f"**Draft summary prepared by the assistant:**\n\n{triage['standardised_narrative']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Suggested broad category", wiz.get("category") or "—")
    c2.metric("Suggested incident type", wiz.get("sub_category") or "—")
    incident_date_label = wiz.get("incident_date") or "Date not supplied"
    incident_time_label = wiz.get("incident_time") or "time not supplied"
    c3.metric("Date and time provided", f"{incident_date_label} {incident_time_label}")
    if wiz.get("modus_operandi"):
        st.caption(f"Modus operandi: {wiz['modus_operandi']}")
    if wiz.get("incident_location"):
        st.caption(f"Platforms involved: {', '.join(wiz['incident_location'])}")

    if wiz.get("ai_sub_category"):
        confirmation_banner()
        st.markdown(
            f"Assistant suggestion: **{wiz['ai_sub_category']}**",
            unsafe_allow_html=True,
        )

    st.markdown(f"**Complainant:** {wiz.get('name') or '—'}  &bull;  {wiz.get('phone') or '—'}  &bull;  "
               f"{wiz.get('city') or '—'}, {wiz.get('state') or '—'}  &bull;  "
               f"Relationship: {wiz.get('relationship_with_victim')}")

    if wiz.get("transactions"):
        section_header("Payment details")
        st.dataframe(pd.DataFrame(wiz["transactions"]), hide_index=True, width="stretch")
    if wiz.get("suspect_transactions"):
        section_header("Possible recipient details")
        st.dataframe(pd.DataFrame(wiz["suspect_transactions"]), hide_index=True, width="stretch")
    if wiz.get("suspects"):
        section_header("Details about the person or account (if known)")
        st.dataframe(pd.DataFrame(wiz["suspects"]), hide_index=True, width="stretch")
    if wiz.get("evidence"):
        section_header("Evidence files")
        st.dataframe(pd.DataFrame([{"Description": e.get("description", ""), "Filename": e["filename"]} for e in wiz["evidence"]]),
                    hide_index=True, width="stretch")

    section_header("Possible legal references (optional to review)")
    st.caption("These are automatically matched to the suggested incident type and may be incomplete or incorrect. They are not legal advice.")
    try:
        from modules.legal_mapping import map_sections, UnknownCategory
        try:
            legal_preview = map_sections(wiz["sub_category"], complainant_age=int(wiz["age"]) if wiz.get("age") else None)
            with st.expander("View possible legal references", expanded=False):
                render_legal_sections(legal_preview)
        except UnknownCategory as e:
            st.info(str(e))
    except Exception as e:
        st.caption(f"Statutory mapping lookup notice: {e}")

    section_header("Before you save")
    st.warning(
        "This is a project draft, not an official complaint or police acknowledgement. Saving stores the draft and attached evidence in this computer's project workspace, where anyone with access to this app may view them. Depending on configuration, text may also be processed by an external AI provider."
    )
    st.markdown(
        "Please check the details and any assistant or OCR suggestions. Do not include passwords, PINs, one-time codes, or full card details. "
        "For a real incident, use the official cybercrime portal or call the appropriate helpline."
    )
    wiz["consent"] = st.checkbox(
        "I have reviewed this draft, confirm the details are accurate to the best of my knowledge, and understand that saving creates a local project record only.",
        key="local_record_consent",
    )

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Go back and edit", width="stretch"):
            st.session_state["wizard_step"] = 2
            st.rerun()
    with c2:
        if st.button("Save complaint record", type="primary", width="stretch"):
            if not wiz["consent"]:
                st.error("Please confirm the declaration before saving this local draft.")
            else:
                _submit_complaint(wiz)


def _submit_complaint(wiz):
    if not wiz.get("consent"):
        st.error("Please confirm the declaration before saving this local draft.")
        return

    complainant = {
        "name": wiz["name"].strip() or None, "age": int(wiz["age"]) if wiz.get("age") else None,
        "phone": wiz["phone"].strip() or None, "email": wiz["email"].strip() or None,
        "city": wiz["city"].strip() or None, "state": wiz["state"].strip() or None,
        "relationship_with_victim": wiz.get("relationship_with_victim"), "id_type": wiz.get("id_type"),
    }
    complainant = {k: v for k, v in complainant.items() if v is not None}
    attachments = [e.get("path", e["filename"]) for e in wiz["evidence"]]
    evidence_table = [{"description": e.get("description", ""), "text_information": e.get("text_information", ""),
                       "filename": e["filename"]} for e in wiz["evidence"]]
    evidence_review = wiz.get("evidence_review") or {}
    reviewed_summary = evidence_review.get("summary") if evidence_review.get("confirmed") else None
    reviewed_entities = evidence_review.get("reviewed_entities") if evidence_review.get("confirmed") else None
    if reviewed_summary:
        evidence_table.append({
            "description": "Victim-reviewed OCR summary",
            "text_information": reviewed_summary,
            "filename": "",
        })
    incident_dt_parts = []
    if wiz.get("incident_date"):
        incident_dt_parts.append(wiz["incident_date"].isoformat())
    if wiz.get("incident_time"):
        incident_dt_parts.append(wiz["incident_time"].strftime("%H:%M"))
    incident_dt = " ".join(incident_dt_parts) or None
    
    triage = wiz.get("triage", {})
    gaps = triage.get("missing_critical_info", [])

    with st.spinner("Saving the complaint record and preparing the PDF..."):
        try:
            import pipeline
            case = pipeline.run(
                wiz["incident_text"], complainant=complainant, attachments=attachments,
                verbose=False, incident_datetime=incident_dt, category=wiz.get("category"),
                modus_operandi=wiz.get("modus_operandi"), incident_location=wiz.get("incident_location"),
                transactions=wiz.get("transactions"), suspect_transactions=wiz.get("suspect_transactions"),
                suspects=wiz.get("suspects"), evidence_table=evidence_table,
                entities=reviewed_entities,
                reviewed_evidence_summary=reviewed_summary,
            )
            if gaps:
                case["intake_gaps_identified"] = gaps
            if wiz.get("sentiment"):
                case["sentiment"] = wiz["sentiment"]
            if wiz.get("stt_metadata"):
                case["voice_transcription"] = wiz["stt_metadata"]
            pipeline.write_json(case)

            received_evidence = []
            for evidence in wiz.get("evidence", []):
                evidence_path = evidence.get("path")
                if evidence_path and os.path.isfile(evidence_path):
                    with open(evidence_path, "rb") as evidence_file:
                        received_evidence.append((evidence.get("filename") or os.path.basename(evidence_path), evidence_file.read()))

            if len(received_evidence) > 20 or sum(len(content) for _, content in received_evidence) > investigator_store.MAX_TOTAL_EVIDENCE_BYTES:
                raise ValueError("The investigator inbox can receive up to 20 evidence files and 100 MB total per case.")
            if any(len(content) > investigator_store.MAX_EVIDENCE_FILE_BYTES for _, content in received_evidence):
                raise ValueError("Each evidence file must be 25 MB or smaller to be added to the investigator inbox.")

            received_case = investigator_store.import_case_file(
                json.dumps(case, ensure_ascii=False).encode("utf-8"),
                INVESTIGATOR_INBOX_DIR,
            )
            investigator_store.save_received_evidence(received_case, received_evidence, INVESTIGATOR_INBOX_DIR)
            investigator_store.save_case(received_case, INVESTIGATOR_INBOX_DIR)
        except Exception as e:
            st.error(
                "The complaint could not be fully saved to the local record and investigator inbox.\n\n"
                f"**{type(e).__name__}:** {e}"
            )
            return

    load_case_files.clear()
    load_investigator_cases.clear()
    case["_investigator_received_at"] = received_case.get("_investigator_received_at")
    case["_activity_log"] = received_case.get("_activity_log", [])
    st.session_state["last_submitted_case"] = case
    st.rerun()


def _render_submission_success(case):
    band = band_of(case)
    st.markdown(
        f"""<div style="background:#f0fdf4;border:2px solid #16a34a;border-radius:4px;padding:26px;text-align:center;">
              <div style="font-size:1.1em;color:#166534;font-weight:800;letter-spacing:0.04em;text-transform:uppercase;">
                Complaint record prepared
              </div>
              <div style="font-size:1.8em;font-weight:800;color:{GOV_BLUE_DARK};margin-top:8px;letter-spacing:0.02em;">
                {case['reference']}
              </div>
              <div style="color:#475569;font-size:0.9em;margin-top:6px;">
                Use this reference to find the saved record on this computer.
              </div>
            </div>""",
        unsafe_allow_html=True,
    )
    st.write("")
    cl = case.get("classification", {})
    st.metric("AI-suggested incident type", g(cl, "sub_category", default="UNCLASSIFIED"))

    pdf_path = pdf_path_for(case)
    if pdf_path:
        with open(pdf_path, "rb") as f:
            st.download_button(
        "Download complaint record PDF",
                data=f.read(),
                file_name=os.path.basename(pdf_path),
                mime="application/pdf",
                type="primary",
            )

    st.success("This record is now available in the local investigator case queue, along with the evidence files you attached.")
    st.warning("This is not an official complaint filing or acknowledgement. The investigator workspace has no login or access controls; anyone who can open this app on this computer may view the record.")

    if st.button("Open investigator case queue"):
        st.query_params["route"] = "investigator"
        st.session_state["nav_page"] = "Case Queue"
        st.rerun()

    if st.button("Prepare another complaint"):
        st.session_state["last_submitted_case"] = None
        new_wizard()
        st.rerun()


# =============================================================================
# PAGE - Check Status (Citizen)
# =============================================================================

def page_check_status():
    st.title("Find a saved record")
    st.caption("Searches complaint records saved on this computer. It does not check an official police or NCRP report status.")
    ack = st.text_input("Complaint reference", placeholder="Enter the reference shown after saving")
    if not st.button("Find record", type="primary"):
        return
    if not ack.strip():
        st.warning("Enter the complaint reference first.")
        return
    target = re.sub(r"[^A-Za-z0-9]", "", ack).upper()
    cases, _ = load_case_files()
    match = next((c for c in cases if re.sub(r"[^A-Za-z0-9]", "", str(c.get("reference", ""))).upper() == target), None)
    if not match:
        st.error("No saved record matches that reference. Check it and try again.")
        return
    st.success("Saved complaint record found on this computer. This app does not receive updates from police or NCRP.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Complaint reference", match.get("reference", "—"))
    c2.metric("Suggested incident type", g(match, "classification", "sub_category", default="Not available"))
    c3.metric("Saved at", g(match, "generated_at", default="Unknown"))


# =============================================================================
# PAGE - Cases (Investigator)
# =============================================================================

def page_cases():
    st.title("Case register")
    st.caption("Open saved complaint records, check their details and evidence, and record the next review step.")

    with st.expander("Import an external case record", expanded=False):
        st.write("Use this for a structured JSON record created outside the intake flow. New completed intake records appear here automatically.")
        with st.form("investigator_case_import_form", clear_on_submit=True):
            uploaded_case = st.file_uploader("Structured case record (.json)", type=["json"], key="investigator_case_upload")
            uploaded_evidence = st.file_uploader(
                "Original evidence files (optional)",
                type=["pdf", "png", "jpg", "jpeg", "webp", "txt", "mp4", "wav", "docx", "xlsx", "csv"],
                accept_multiple_files=True,
                key="investigator_evidence_uploads",
            )
            import_submitted = st.form_submit_button("Import into case register", type="primary")
        if import_submitted:
            if uploaded_case is None:
                st.error("Choose a structured JSON case record to import.")
            else:
                try:
                    case = investigator_store.import_case_file(uploaded_case.getvalue(), INVESTIGATOR_INBOX_DIR)
                    evidence_payloads = [(item.name, item.getvalue()) for item in (uploaded_evidence or [])]
                    investigator_store.save_received_evidence(case, evidence_payloads, INVESTIGATOR_INBOX_DIR)
                    investigator_store.save_case(case, INVESTIGATOR_INBOX_DIR)
                    load_investigator_cases.clear()
                    st.session_state["selected_case_path"] = case["_path"]
                    st.session_state["nav_page"] = "Case Review"
                    st.success(f"Case {case.get('reference')} added to the local investigator inbox.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    cases, errors = load_investigator_cases()
    if errors:
        st.warning(f"{len(errors)} unreadable record(s) were skipped. Check the local inbox files.")
    awaiting_statuses = {"RECEIVED - AWAITING REVIEW", "IN REVIEW", "AWAITING INFORMATION"}
    awaiting = sum(g(case, "status", default="") in awaiting_statuses for case in cases)
    urgent = sum(bool(g(case, "sentiment", "is_golden_hour", default=False)) for case in cases)
    conflicts = sum(bool(g(case, "reconciliation", "has_conflicts", default=False)) for case in cases)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Cases in register", len(cases))
    metric_cols[1].metric("Awaiting action", awaiting)
    metric_cols[2].metric("Urgent cases to review", urgent)
    metric_cols[3].metric("Evidence details to check", conflicts)

    if not cases:
        st.info("No complaint records yet. Saved records will appear here after intake is completed.")
        return

    st.markdown("### Find a complaint")
    filter_cols = st.columns([1.5, 1.2, 1.3])
    search = filter_cols[0].text_input("Search register", placeholder="Reference, category, or location")
    all_statuses = sorted({str(g(case, "status", default="RECEIVED - AWAITING REVIEW")) for case in cases})
    statuses = filter_cols[1].multiselect("Case status", all_statuses, default=all_statuses)
    categories = sorted({str(g(case, "classification", "sub_category", default="Not classified")) for case in cases})
    chosen_categories = filter_cols[2].multiselect("Suggested incident type", categories)
    query = search.strip().casefold()

    filtered = []
    for case in cases:
        status = str(g(case, "status", default="RECEIVED - AWAITING REVIEW"))
        category = str(g(case, "classification", "sub_category", default="Not classified"))
        search_blob = " ".join((
            str(case.get("reference", "")), category, status,
            str(g(case, "complainant", "city", default="")),
        )).casefold()
        if status not in statuses or (chosen_categories and category not in chosen_categories):
            continue
        if query and query not in search_blob:
            continue
        filtered.append(case)

    filtered.sort(key=lambda case: (
        not bool(g(case, "sentiment", "is_golden_hour", default=False)),
        str(case.get("_investigator_received_at", case.get("generated_at", ""))),
    ))
    st.caption(f"Showing {len(filtered)} of {len(cases)} records. Check suggested priorities and incident types before acting.")
    if not filtered:
        st.info("No cases match these filters.")
        return

    for index, case in enumerate(filtered):
        sent = case.get("sentiment") if isinstance(case.get("sentiment"), dict) else {}
        classification = case.get("classification") if isinstance(case.get("classification"), dict) else {}
        with st.container(border=True):
            main_cols = st.columns([1.2, 2.2, 1.2, 1.2, 1])
            main_cols[0].caption("CASE REFERENCE")
            main_cols[0].markdown(f"**{case.get('reference', 'No reference')}**")
            main_cols[1].caption("SUGGESTED INCIDENT TYPE")
            main_cols[1].markdown(f"**{classification.get('sub_category', 'Not classified')}**")
            main_cols[2].caption("REVIEW PRIORITY")
            main_cols[2].markdown(urgency_badge(sent.get("urgency_level"), sent.get("is_golden_hour", False)), unsafe_allow_html=True)
            main_cols[3].caption("STATUS")
            main_cols[3].write(display_case_status(g(case, "status", default="RECEIVED - AWAITING REVIEW")))
            main_cols[4].caption("RECEIVED")
            main_cols[4].write(str(case.get("_investigator_received_at", case.get("generated_at", "Date not supplied")))[:10])
            detail_cols = st.columns([1, 2, 1, 1])
            detail_cols[0].caption(f"Location: {g(case, 'complainant', 'city', default='Not supplied')}")
            detail_cols[1].caption("Review category, narrative, evidence, and OCR findings before recording action.")
            if detail_cols[3].button("Review case", key=f"open_inbox_case_{index}", type="primary"):
                st.session_state["selected_case_path"] = case["_path"]
                st.session_state["nav_page"] = "Case Review"
                st.rerun()


# =============================================================================
# PAGE - Case Detail (Investigator)
# =============================================================================

def page_case_detail():
    st.title("Review complaint")
    cases, errors = load_investigator_cases()
    if not cases:
        st.info("No case is available to review. New intake records will appear in the case register after saving.")
        return

    by_path = {c["_path"]: c for c in cases}
    options = sorted(by_path.keys(), key=lambda p: by_path[p].get("reference", ""))
    current = st.session_state.get("selected_case_path")
    if current not in options:
        current = options[0] if options else None

    picked = st.selectbox("Choose a complaint record", options, index=options.index(current) if current in options else 0,
                          format_func=lambda p: by_path[p].get("reference", os.path.basename(p)))
    st.session_state["selected_case_path"] = picked
    case = by_path[picked]
    cl = case.get("classification") if isinstance(case.get("classification"), dict) else {}

    band = band_of(case)
    confirmation_banner()
    status = str(case.get("status", "RECEIVED - AWAITING REVIEW"))

    st.subheader(f"{case.get('reference', 'Case record')}")
    st.caption(f"Received: {case.get('_investigator_received_at', g(case, 'generated_at'))}  ·  Status: **{display_case_status(status)}**  ·  Assigned to: **{case.get('assigned_to', 'Unassigned')}**")

    sent_summary = case.get("sentiment") if isinstance(case.get("sentiment"), dict) else {}
    urgency_summary = st.columns(4)
    urgency_summary[0].metric("Review priority", sent_summary.get("urgency_level", "Not assessed"))
    suggested_subcategory = cl.get("sub_category", "Not classified")
    urgency_summary[1].metric("Suggested main category", SUB_TO_MAIN_CATEGORY.get(suggested_subcategory, "Not classified"))
    urgency_summary[2].metric("Suggested type match", fmt_confidence(cl.get("confidence")), help="A rough model estimate. Review the complaint and evidence before relying on it.")
    urgency_summary[3].metric("Evidence details to check", len(g(case, "reconciliation", "conflicts", default=[])))
    st.caption(f"Suggested subcategory: **{suggested_subcategory}** · Source: {cl.get('source', 'Not recorded')} · Review before relying on this result.")

    with st.form(f"case_workflow_{os.path.basename(picked)}"):
        st.markdown("**Update case workflow**")
        action_cols = st.columns(3)
        status_options = [
            "RECEIVED - AWAITING REVIEW", "IN REVIEW", "AWAITING INFORMATION",
            "REFERRED FOR FOLLOW-UP", "REVIEW COMPLETE",
        ]
        if status not in status_options:
            status_options.insert(0, status)
        next_status = action_cols[0].selectbox("Status", status_options, index=status_options.index(status), format_func=display_case_status)
        assignee = action_cols[1].text_input("Assigned investigator", value=str(case.get("assigned_to", "")))
        reviewer = action_cols[2].text_input("Reviewer initials", placeholder="Not authenticated")
        action_note = st.text_input("Next action or review note", placeholder="Record what was checked or what should happen next")
        workflow_submit = st.form_submit_button("Save workflow update", type="primary")
    if workflow_submit:
        if not reviewer.strip() or not action_note.strip():
            st.error("Enter reviewer initials and a brief note to record this update.")
        else:
            previous_status = status
            case["status"] = next_status
            case["assigned_to"] = assignee.strip() or None
            investigator_store.add_activity(
                case,
                reviewer.strip(),
                "Workflow updated",
                f"Status: {previous_status} → {next_status}. Assigned to: {assignee.strip() or 'Unassigned'}. {action_note.strip()}",
            )
            try:
                investigator_store.save_case(case, INVESTIGATOR_INBOX_DIR)
                load_investigator_cases.clear()
                st.success("Workflow update saved to the local case record.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save the case update: {exc}")

    inc = case.get("incident") or {}
    reported_sub = inc.get("sub_category_reported")
    actual_sub = g(case, "classification", "sub_category", default="UNCLASSIFIED")
    if reported_sub and reported_sub != "not supplied" and reported_sub != actual_sub:
        st.warning(f"**Category differs:** the complainant selected '{reported_sub}', while the model suggested '{actual_sub}'. Review the original statement and evidence before deciding.")

    c1, c2 = st.columns([1, 1])

    with c1:
        section_header("Complainant Information")
        comp = case.get("complainant") or {}
        st.table(pd.DataFrame({
            "Field": ["Full Name", "Age", "Phone", "Email", "City", "State", "Relationship"],
            "Value": [str(g(comp, "name", default="not supplied")), str(g(comp, "age", default="not supplied")),
                      str(g(comp, "phone", default="not supplied")), str(g(comp, "email", default="not supplied")),
                      str(g(comp, "city", default="not supplied")), str(g(comp, "state", default="not supplied")),
                      str(g(comp, "relationship_with_victim", default="Self"))],
        }).set_index("Field"))

        if any(v not in (None, "", "not supplied", []) for v in inc.values()):
            section_header("Incident Registration Metadata")
            st.table(pd.DataFrame({
                "Parameter": ["Occurrence Timestamp", "Broad Category", "Modus Operandi", "Platforms / Locations"],
                "Value": [str(inc.get("datetime", "not supplied")), str(inc.get("category", "not supplied")),
                          str(inc.get("modus_operandi", "not supplied")),
                          ", ".join(inc.get("location") or []) or "not supplied"],
            }).set_index("Parameter"))

        section_header("Incident summary")
        src = g(case, "complaint", "narrative_source", default="unavailable")
        if src == "Module A":
            st.write(g(case, "complaint", "standardised_narrative"))
        else:
            st.warning(f"Automated narrative translation not generated ({src}).")
            st.caption("Original statement:")
            st.write(g(case, "complaint", "raw_text"))

        section_header("Details extracted from evidence")
        ent = case.get("extracted_entities") or {}
        if "_status" in ent:
            st.caption(ent["_status"])
        elif ent:
            st.table(pd.DataFrame({"Entity Type": list(ent.keys()), "Extracted Value": [str(v) for v in ent.values()]}).set_index("Entity Type"))
        else:
            st.caption("No entities extracted from submitted evidence.")

        section_header("Evidence cross-check")
        recon = case.get("reconciliation") or {}
        if recon.get("has_conflicts") and recon.get("conflicts"):
            st.error("The complaint text and uploaded file show different values. Review the details before relying on them.")
            recon_rows = []
            for c in recon.get("conflicts", []):
                recon_rows.append({
                    "Parameter": c.get("field", "").upper(),
                    "Evidence reading": str(c.get("ocr_value", "")),
                    "Complaint statement": ", ".join(str(x) for x in c.get("typed_mentions", [])),
                    "Review note": c.get("resolution", ""),
                })
            st.dataframe(pd.DataFrame(recon_rows), hide_index=True, width="stretch")
        elif recon.get("agreements"):
            st.success(f"Statement verified against evidence: {len(recon['agreements'])} parameters matched. Note: {recon.get('confidence_note', '')}")
        elif recon.get("gaps"):
            st.caption(f"Unfilled parameters: {', '.join(recon['gaps'])}")
        else:
            st.caption("No discrepancy records filed.")

        section_header("Evidence files")
        ev = case.get("evidence") or {}
        atts = ev.get("attachments") or []
        if isinstance(atts, str):
            atts = [atts]
        if atts:
            for a in atts:
                st.markdown(f"- `{os.path.basename(str(a))}`")
        else:
            st.caption("No digital evidence files attached.")
        received_files = case.get("received_evidence_files") if isinstance(case.get("received_evidence_files"), list) else []
        for index, evidence_file in enumerate(received_files):
            try:
                evidence_path = investigator_store.resolve_evidence_path(
                    case, evidence_file.get("path", ""), INVESTIGATOR_INBOX_DIR
                )
                if evidence_path:
                    file_bytes = evidence_path.read_bytes()
                    file_cols = st.columns([2, 1])
                    file_cols[0].write(evidence_file.get("name", evidence_path.name))
                    file_cols[1].download_button(
                        "Download original",
                        data=file_bytes,
                        file_name=evidence_file.get("name", evidence_path.name),
                        mime="application/octet-stream",
                        key=f"download_case_evidence_{index}_{os.path.basename(picked)}",
                    )
                    if evidence_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                        st.image(file_bytes, caption=evidence_file.get("name", evidence_path.name), width="stretch")
            except Exception as exc:
                st.caption(f"Could not open an imported evidence file: {exc}")

    with c2:
        section_header("Suggested incident type")
        st.metric("Suggested incident type", g(cl, "sub_category", default="UNCLASSIFIED"))
        if cl.get("guidance"):
            st.caption(cl["guidance"])

        section_header("Urgency and support")
        sent = case.get("sentiment") or {}
        if sent and isinstance(sent, dict) and sent.get("tone"):
            urg_lvl = sent.get("urgency_level")
            is_gold = sent.get("is_golden_hour", False)
            urg_badge_html = urgency_badge(urg_lvl, is_gold)
            tone_badge_html = tone_badge(sent.get("tone"), sent.get("tone_label"))
            st.markdown(
                f"""<div style="background:#f8fafc;border:1px solid #cbd5e1;padding:12px 14px;border-radius:4px;margin-bottom:12px;">
                      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:8px;">
                        <div><b>Priority:</b> {urg_badge_html}</div>
                        <div><b>Message tone:</b> {tone_badge_html}</div>
                      </div>
                      <div style="font-size:0.86em;color:#475569;">
                        Suggested from the message wording. Check the original account and evidence.
                      </div>
                    </div>""",
                unsafe_allow_html=True,
            )
            if is_gold:
                st.warning("Possible recent financial loss. Contact 1930 and your bank promptly. This demo cannot block a payment or freeze an account.")
            elif sent.get("tone") == "ANXIOUS_THREATENED":
                st.warning("Possible threats were reported. Review the original messages and preserve evidence before changing the account.")
        else:
            st.caption("Urgency triage assessment not recorded for this file.")

        section_header("Possible laws to review")
        legal = case.get("legal_sections") or {}
        if "_status" in legal:
            st.info(legal["_status"])
        else:
            render_legal_sections(legal)

        section_header("Possible next steps")
        actions = case.get("suggested_actions") or []
        if actions:
            for i, a in enumerate(actions, 1):
                st.markdown(f"**{i}.** {a}")
        else:
            st.caption("No suggested actions are available.")

        txns = case.get("transactions") or []
        if txns:
            section_header("Financial Debit Trail")
            st.dataframe(pd.DataFrame(txns), hide_index=True, width="stretch")

        stxns = case.get("suspect_transactions") or []
        if stxns:
            section_header("Suspect Beneficiary Destination Trail")
            st.dataframe(pd.DataFrame(stxns), hide_index=True, width="stretch")

        suspects = case.get("suspects") or []
        if suspects:
            section_header("Suspect Identifiers")
            st.dataframe(pd.DataFrame(suspects), hide_index=True, width="stretch")

        pdf_path = pdf_path_for(case)
        if pdf_path:
            with open(pdf_path, "rb") as f:
                st.download_button("Download Formal Investigation Report (PDF)", data=f.read(),
                                   file_name=os.path.basename(pdf_path), mime="application/pdf")

    st.divider()
    section_header("Classification review")
    oc1, oc2, oc3 = st.columns([1.2, 1.2, 1.8])
    with oc1:
        with st.form(f"confirm_category_{os.path.basename(picked)}"):
            confirm_reviewer = st.text_input("Reviewer initials", key=f"confirm_reviewer_{os.path.basename(picked)}")
            confirm_note = st.text_input("Review note", key=f"confirm_note_{os.path.basename(picked)}")
            confirm_clicked = st.form_submit_button("Confirm suggested category", type="primary")
        if confirm_clicked:
            if not confirm_reviewer.strip() or not confirm_note.strip():
                st.error("Enter reviewer initials and a short review note.")
                st.stop()
            try:
                if isinstance(case.get("classification"), dict):
                    case["classification"]["requires_confirmation"] = False
                    case["classification"]["source"] = "Officer-reviewed suggestion"
                case["status"] = "CATEGORY REVIEWED"
                investigator_store.add_activity(case, confirm_reviewer.strip(), "Suggested category reviewed", confirm_note.strip())
                if investigator_store.save_case(case, INVESTIGATOR_INBOX_DIR):
                    load_investigator_cases.clear()
                    st.success("Category review saved to the local case record.")
                    st.rerun()
            except Exception as e:
                st.error(f"Confirmation failed: {e}")
    with oc2:
        reclassify_clicked = st.button("Reclassify Offence Category", width="stretch")

    if reclassify_clicked:
        st.session_state["reclassify_open"] = True

    if st.session_state.get("reclassify_open"):
        with st.form("reclassify_form"):
            current_cat = g(case, "classification", "sub_category", default=KNOWN_CATEGORIES[0])
            options_cat = KNOWN_CATEGORIES if current_cat in KNOWN_CATEGORIES else [current_cat] + KNOWN_CATEGORIES
            new_cat = st.selectbox("Correct the suggested category", options_cat, index=options_cat.index(current_cat))
            reviewer_name = st.text_input("Reviewer initials (not authenticated)")
            note = st.text_input("Reason for changing the suggested category (required)")
            save_clicked = st.form_submit_button("Commit Reclassification", type="primary")
        if save_clicked:
            if not reviewer_name.strip() or not note.strip():
                st.error("Enter reviewer initials and the reason for the classification change.")
                st.stop()
            try:
                old_cat = g(case, "classification", "sub_category", default="UNCLASSIFIED")
                if not isinstance(case.get("classification"), dict):
                    case["classification"] = {}
                case["classification"]["sub_category"] = new_cat
                case["classification"]["confidence"] = None
                case["classification"]["confidence_band"] = "NOT SUPPLIED"
                case["classification"]["guidance"] = "Reclassified manually following officer adjudication."
                case["classification"]["source"] = "Officer override"
                case["classification"]["requires_confirmation"] = False
                case["status"] = "RECLASSIFIED BY OFFICER"
                history = case.setdefault("_reclassification_history", [])
                if not isinstance(history, list):
                    history = case["_reclassification_history"] = []
                history.append({"from": old_cat, "to": new_cat, "note": note,
                                "at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                "reviewer": reviewer_name.strip()})
                investigator_store.add_activity(case, reviewer_name.strip(), "Suggested category changed",
                                                f"{old_cat} → {new_cat}. Reason: {note}")
                try:
                    from modules.legal_mapping import map_sections, UnknownCategory
                    age = comp.get("age") if isinstance(comp, dict) else None
                    age = age if isinstance(age, int) else None
                    try:
                        case["legal_sections"] = map_sections(new_cat, complainant_age=age)
                    except UnknownCategory as e:
                        case["legal_sections"] = {"_status": f"unresolved: {e}"}
                except Exception:
                    pass
                if investigator_store.save_case(case, INVESTIGATOR_INBOX_DIR):
                    load_investigator_cases.clear()
                    st.session_state["reclassify_open"] = False
                    st.success(f"Suggested category changed from '{old_cat}' to '{new_cat}' and recorded for review.")
                    st.rerun()
            except Exception as e:
                st.error(f"Reclassification failure: {e}")

    # =========================================================================
    section_header("Local activity history")
    activity_log = case.get("_activity_log") if isinstance(case.get("_activity_log"), list) else []
    if activity_log:
        activity_rows = [
            {"Time": item.get("at", ""), "Actor": item.get("actor", ""),
             "Action": item.get("action", ""), "Details": item.get("details", "")}
            for item in reversed(activity_log)
        ]
        st.dataframe(pd.DataFrame(activity_rows), hide_index=True, width="stretch")
        st.caption("This local JSON activity history is not tamper-proof and does not establish authenticated identity.")
    else:
        st.caption("No review actions have been recorded.")

    # MODULE L — Cross-Case Pattern & Criminal Syndicate Correlation
    # =========================================================================
    st.divider()
    section_header("Similar details in other records (check manually)")
    if _v2_modules_available:
        try:
            os.makedirs(INVESTIGATOR_INBOX_DIR, exist_ok=True)
            investigator_index = os.path.join(INVESTIGATOR_INBOX_DIR, "case_index.db")
            sync_all_case_files(INVESTIGATOR_INBOX_DIR, db_path=investigator_index)
            links = find_linked_cases(case, db_path=investigator_index)
            if links.get("total_cases_linked", 0) > 0:
                st.markdown(
                    f"""<div style="background:#fee2e2;border:1px solid #f87171;border-left:5px solid #dc2626;padding:16px 20px;border-radius:4px;margin-bottom:14px;">
                          <div style="font-weight:800;color:#991b1b;font-size:1.05em;letter-spacing:0.02em;">
                            POTENTIAL SHARED-INDICATOR LEADS ({links['total_cases_linked']} CASES)
                          </div>
                          <div style="font-size:0.92em;color:#374151;margin-top:6px;line-height:1.5;">
                            Possible identifier matches appear in <b>{links['total_cases_linked']}</b> other cases in this local inbox. Verify them independently.
                          </div>
                          <div style="font-size:0.95em;color:#991b1b;font-weight:700;margin-top:8px;">
                            Combined reported loss across linked cases: Rs. {links['total_amount_defrauded']:,.2f}
                          </div>
                          <div style="font-size:0.85em;color:#475569;margin-top:4px;">
                            Shared identifiers require verification before relying on a match.
                          </div>
                        </div>""",
                    unsafe_allow_html=True
                )

                # Show table of linked complaints
                lk_rows = []
                for lk in links.get("linked_cases", []):
                    lk_rows.append({
                        "Case Reference": lk["reference"],
                        "City": lk.get("citizen_city", "-"),
                        "Offence": lk.get("sub_category", "-"),
                        "Amount Lost": f"Rs. {lk.get('amount', 0):,}",
                        "Match Evidence": "; ".join(lk.get("match_reasons", [])),
                        "Link Confidence": f"{int(lk.get('confidence_score', 0.8) * 100)}%"
                    })
                st.dataframe(pd.DataFrame(lk_rows), hide_index=True, width="stretch")

                # Suspect Dossier Viewer
                with st.expander("Inspect possible linked-case leads", expanded=False):
                    primary_suspect_id = None
                    for sid in links.get("shared_identifiers", []):
                        if "PHONE:" in sid or "UPI:" in sid:
                            primary_suspect_id = sid.split(":", 1)[1].strip()
                            break
                    if primary_suspect_id:
                        dos = build_suspect_dossier(primary_suspect_id, db_path=investigator_index)
                        if dos.get("found"):
                            dc1, dc2, dc3 = st.columns(3)
                            dc1.metric("Linked inbox cases", dos.get("total_complaints", 1))
                            dc2.metric("Combined reported loss", dos.get("total_amount_formatted", "Not available"))
                            dc3.metric("Lead assessment", dos.get("threat_level", "Review required"))

                            st.markdown(f"**Associated Phone Numbers:** `{', '.join(dos.get('associated_phones', [])) or 'None'}`")
                            st.markdown(f"**Associated UPI Handles:** `{', '.join(dos.get('associated_upi_vpash', [])) or 'None'}`")
                            st.markdown(f"**Victim Geographies:** {', '.join(dos.get('victim_geographies', []))}")
                            st.caption("This profile is a lead aid only; it is not a verified suspect dossier or an instruction to take legal action.")
            else:
                st.info("No matching identifiers found among cases currently in this local inbox. This does not establish that the incident is isolated.")
        except Exception as e:
            st.caption(f"Pattern correlation note: {e}")
    else:
        st.caption("Cross-case correlation engine not loaded.")

    # =========================================================================
    # MODULE M — Statutory Investigation Document Generator
    # =========================================================================
    st.divider()
    section_header("Draft document tools")
    st.caption("Generated text is a local draft only. It is not approved to issue, serve, or file as an official document.")

    if _v2_modules_available:
        templates = list_available_templates()
        t_opts = {t["doc_type"]: f"{t['doc_type']} — {t['title']}" for t in templates}

        c_doc1, c_doc2 = st.columns([1.5, 1])
        with c_doc1:
            sel_doc_type = st.selectbox(
                "Choose a sample document template",
                list(t_opts.keys()),
                format_func=lambda k: t_opts[k],
                key=f"doc_type_sel_{case.get('reference')}"
            )
        with c_doc2:
            io_name_input = st.text_input("Reviewer / officer name", value="", key=f"io_name_{case.get('reference')}")

        c_doc3, c_doc4 = st.columns([1.5, 1])
        with c_doc3:
            io_desig_input = st.text_input("Designation / rank", value="", key=f"io_desig_{case.get('reference')}")
        with c_doc4:
            io_ps_input = st.text_input("Police station / jurisdiction", value=g(case, "complainant", "police_station", default=""), key=f"io_ps_{case.get('reference')}")

        if st.button("Create document draft", type="primary", key=f"btn_gen_doc_{case.get('reference')}"):
            try:
                gen_res = generate_investigation_document(
                    doc_type=sel_doc_type,
                    case_data=case,
                    io_name=io_name_input,
                    io_designation=io_desig_input,
                    police_station=io_ps_input
                )
                st.session_state["generated_doc_text"] = gen_res["document_text"]
                st.session_state["generated_doc_title"] = gen_res["title"]
                st.session_state["generated_doc_type"] = sel_doc_type
            except Exception as e:
                st.error(f"Document generation failed: {e}")

        if st.session_state.get("generated_doc_text"):
            st.markdown(f"#### {st.session_state.get('generated_doc_title', 'Statutory Document')}")
            st.text_area(
                "Draft document preview",
                st.session_state["generated_doc_text"],
                height=320,
                key=f"doc_preview_box_{case.get('reference')}"
            )
            c_d1, c_d2 = st.columns([1, 1])
            with c_d1:
                ref_slug = case.get("reference", "case").replace("/", "-")
                st.download_button(
                    "Download Notice (.txt)",
                    data=st.session_state["generated_doc_text"],
                    file_name=f"{st.session_state.get('generated_doc_type')}_{ref_slug}.txt",
                    mime="text/plain",
                    key=f"dl_doc_{case.get('reference')}"
                )
            with c_d2:
                st.caption("Do not issue this document as official without the required authorization and legal review.")



# =============================================================================
# PAGE - Statistics (Investigator)
# =============================================================================

def page_statistics():
    st.title("Overview")
    st.caption("Operational counts are calculated only from records received into the local investigator inbox. They are not national statistics.")
    cases, errors = load_investigator_cases()
    if errors:
        st.warning(f"System Notice: {len(errors)} case file(s) unreadable on disk.")

    tab1, tab2 = st.tabs(["Inbox workload", "Classifier validation"])

    with tab1:
        if not cases:
            st.info("No investigator cases have been received, so there is no workload data to chart.")
        else:
            pending = sum(1 for c in cases if g(c, "status", default="") in {"RECEIVED - AWAITING REVIEW", "IN REVIEW", "AWAITING INFORMATION"})
            urgent = sum(bool(g(c, "sentiment", "is_golden_hour", default=False)) for c in cases)
            conflicts = sum(bool(g(c, "reconciliation", "has_conflicts", default=False)) for c in cases)
            m1, m2, m3 = st.columns(3)
            m1.metric("Cases received", len(cases))
            m2.metric("Awaiting action", pending)
            m3.metric("Urgent flags / conflicts", f"{urgent} / {conflicts}")

            st.divider()
            left, right = st.columns([1.4, 1])

            with left:
                section_header("Suggested categories in the inbox")
                counts = pd.Series([g(c, "classification", "sub_category", default="UNCLASSIFIED") for c in cases]).value_counts()
                counts = counts.sort_values(ascending=True)
                fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", marker_color=GOV_BLUE_HEADER,
                                       hovertemplate="%{y}: %{x} complaint(s)<extra></extra>"))
                fig.update_layout(height=max(320, 28 * len(counts)), margin=dict(l=10, r=10, t=10, b=10),
                                   xaxis_title="Received cases", yaxis_title=None,
                                  xaxis=dict(gridcolor="#e2e8f0", zeroline=False))
                st.plotly_chart(fig, width="stretch", theme="streamlit")

            with right:
                section_header("Saved priority estimates")
                urg_counts = pd.Series([g(c, "sentiment", "urgency_level", default="STANDARD") for c in cases]).value_counts()
                fig2 = go.Figure(go.Bar(x=urg_counts.index, y=urg_counts.values,
                                        marker_color="#1a3d7c",
                                        text=urg_counts.values, textposition="outside",
                                        hovertemplate="%{x}: %{y} case(s)<extra></extra>"))
                fig2.update_layout(height=320, margin=dict(l=10, r=10, t=20, b=10), xaxis_title=None, yaxis_title="Cases",
                                   yaxis=dict(gridcolor="#e2e8f0", zeroline=False))
                st.plotly_chart(fig2, width="stretch", theme="streamlit")
                st.caption("Distribution across priority tiers (Immediate, High, Standard)")

    with tab2:
        bench = load_benchmark_metrics()
        if not bench:
            st.info("Benchmark metrics file not generated yet. Run scripts/benchmark_models.py to compile metrics.")
        else:
            st.info("Metrics are read from a project benchmark file. Review the dataset and evaluation method before using these numbers to make deployment decisions.")

            # Metric Cards
            ov = bench.get("overall_metrics", {})
            lat = bench.get("latency_profile", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Macro-Averaged F1", f"{ov.get('macro_f1', 0):.2%}")
            c2.metric("Overall Accuracy", f"{ov.get('accuracy', 0):.2%}")
            c3.metric("Mean Latency", f"{lat.get('mean_latency_ms', 0):.2f} ms", f"{lat.get('throughput_complaints_per_sec', 0):.0f} req/s")
            c4.metric("Test examples", f"{bench.get('_meta', {}).get('test_split_size', '—')}")

            st.divider()

            # Architecture Comparison Table
            section_header("Model comparison in the project benchmark")
            comp = bench.get("model_comparison", {})
            comp_rows = []
            for m_name, m_data in comp.items():
                acc = f"{m_data.get('accuracy', 0):.2%}"
                f1 = f"{m_data.get('macro_f1', 0):.4f}"
                t_time = f"{m_data.get('train_time_sec', 0):.2f}s"
                hardware = "GPU noted in benchmark" if "DistilBERT" in m_name else "CPU noted in benchmark"
                comp_rows.append({
                    "Model Architecture": m_name,
                    "Accuracy": acc,
                    "Macro-F1": f1,
                    "Training Latency": t_time,
                    "Hardware Target": hardware,
                })
            st.dataframe(pd.DataFrame(comp_rows), hide_index=True, width="stretch")

            # Interactive Plotly Confusion Matrix Heatmap
            section_header("Category prediction comparison")
            st.caption("Hover over cells to examine cross-category classification accuracy and misclassification counts.")
            classes = bench.get("classes", [])
            cm_data = bench.get("confusion_matrix", [])
            if classes and cm_data:
                fig_cm = go.Figure(data=go.Heatmap(
                    z=cm_data,
                    x=classes,
                    y=classes,
                    colorscale="Blues",
                    hoverongaps=False,
                    hovertemplate="Actual Offence: %{y}<br>Predicted Offence: %{x}<br>Count: %{z}<extra></extra>",
                ))
                fig_cm.update_layout(
                    height=650,
                    margin=dict(l=20, r=20, t=20, b=120),
                    xaxis=dict(tickangle=45, tickfont=dict(size=9)),
                    yaxis=dict(tickfont=dict(size=9), autorange="reversed"),
                    xaxis_title="Predicted Offence Category",
                    yaxis_title="True Ground-Truth Category",
                )
                st.plotly_chart(fig_cm, width="stretch", theme="streamlit")

            # Per-Category Performance Chart
            section_header("Per-category benchmark scores")
            pcm = bench.get("per_class_metrics", [])
            if pcm:
                df_pcm = pd.DataFrame(pcm)
                df_pcm_sorted = df_pcm.sort_values(by="f1_score", ascending=True)
                fig_f1 = go.Figure(go.Bar(
                    x=df_pcm_sorted["f1_score"],
                    y=df_pcm_sorted["category"],
                    orientation="h",
                    marker_color=GOV_ACCENT_GREEN,
                    text=[f"{f:.2%}" for f in df_pcm_sorted["f1_score"]],
                    textposition="inside",
                    hovertemplate="%{y}<br>F1-Score: %{x:.4f}<extra></extra>",
                ))
                fig_f1.update_layout(
                    height=600,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis=dict(range=[0.95, 1.005], tickformat=".2%", gridcolor="#e2e8f0"),
                    xaxis_title="F1-Score",
                    yaxis_title=None,
                )
                st.plotly_chart(fig_f1, width="stretch", theme="streamlit")

            # Top Confusion Pairs & Operational Safeguards
            section_header("Top Semantic Boundary Confusion Pairs & Officer Safeguards")
            conf_pairs = bench.get("top_confusion_pairs", [])
            if conf_pairs:
                cp_rows = []
                for cp in conf_pairs:
                    cp_rows.append({
                        "True Citizen Offence": cp.get("true_category"),
                        "Model Prediction": cp.get("predicted_category"),
                        "Misclassifications": cp.get("count"),
                        "Operational Safeguard & Legal Harmonisation": "Both categories map to BNS Sec 318(4) & IT Act 66D; Officer Review Alert flagged.",
                    })
                st.dataframe(pd.DataFrame(cp_rows), hide_index=True, width="stretch")

            # Edge Deployment Specs Box
            dep = bench.get("deployment_specs", {})
            st.markdown(
                f"""
                <div style="background:{GOV_GREY};border:1px solid {GOV_BORDER};border-radius:4px;padding:14px;margin-top:10px;">
                  <div style="font-weight:700;color:{GOV_BLUE_DARK};margin-bottom:6px;">Deployment notes recorded in the benchmark file</div>
                  <div style="font-size:0.85em;color:#475569;display:grid;grid-template-columns:1fr 1fr;gap:6px;">
                    <div>&bull; Model File Size: <b>{dep.get('model_file_size_mb', 1.2)} MB</b></div>
                    <div>&bull; Runtime Memory: <b>{dep.get('runtime_ram_mb', 18.5)} MB</b></div>
                    <div>&bull; Hardware Target: <b>{dep.get('hardware_target', 'Standard CPU')}</b></div>
                    <div>&bull; Security Posture: <b>{dep.get('offline_capability', 'Air-Gapped Operation')}</b></div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# =============================================================================
# Router Dispatcher
# =============================================================================

ROUTES = {
    "Home": page_home,
    "Report Cyber Crime": page_report_wizard,
    "Check Status": page_check_status,
    "Case Queue": page_cases,
    "Case Review": page_case_detail,
    "Operations": page_statistics,
}

if not current_route:
    page_landing()
else:
    ROUTES[st.session_state["nav_page"]]()
