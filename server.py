"""
National Cyber Crime Reporting Portal (NCRP) — Unified FastAPI Backend
Statutory Compliance: Bharatiya Nyaya Sanhita (BNS) 2023, IT Act 2000, BNSS 2023, BSA 2023.

Full REST API powering:
  - 3-Step Guided Citizen Filing Wizard (Voice, OCR, Auto-Fill, Reconciliation, PDF generation)
  - Citizen Grievance Tracking (Check Status by Acknowledgement Reference)
  - Police Investigation Queue & Detailed Adjudication Console
  - Module L: Cross-Case Pattern & Criminal Syndicate Correlation Engine
  - Module M: Statutory Investigation Document Generator (BNSS 91/94/106, 1930 Bank Freeze, BSA 63)
  - Scientific Model Benchmark & Intake Analytics
  - Interactive Voice Copilot / Intake Counselor
"""

import os
import sys
import time
import json
import glob
import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Core AI & Law Enforcement Modules
from modules.speech_to_text import transcribe_audio_bytes
from modules.conversational_agent import conduct_counselor_turn
from modules.classifier_service import classify_complaint_text, load_model
from modules.database import (
    init_db,
    create_or_get_session,
    save_message,
    get_session_history,
    save_complaint_draft,
    get_complaint_draft,
    confirm_and_classify_draft,
    reset_session
)
from modules.legal_mapping import map_sections, MAIN_CATEGORIES, get_main_category
from modules.routing import route_complaint

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
from modules.case_file import build_case_file, write_pdf
from modules.sentiment_analysis import analyze_sentiment_and_urgency
from modules.ocr_extract import extract_from_images, extract_entities
from modules.reconcile import reconcile
from modules.auto_fill import generate_autofill_payload
from modules.pattern_engine import find_linked_cases, build_suspect_dossier, sync_all_case_files
from modules.doc_generator import generate_investigation_document, list_available_templates

app = FastAPI(title="National Cyber Crime Reporting Portal API", version="3.5.0")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:8000,http://127.0.0.1:8000,"
    "http://localhost:8501,http://127.0.0.1:8501"
)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(BASE_DIR, "static")
CASE_DIR = os.path.join(BASE_DIR, "case_files")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(CASE_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

init_db()
load_model()
try:
    sync_all_case_files(CASE_DIR)
except Exception as _e:
    print(f"[SYNC] Index sync notice: {_e}")


# =============================================================================
# Request Schemas
# =============================================================================

class ChatRequest(BaseModel):
    session_id: str = "default_session"
    message: str
    history: List[Dict[str, str]] = []
    current_docket: Dict[str, Any] = {}
    language: str = "hi"


class ConfirmRequest(BaseModel):
    session_id: str
    confirmed_narrative: str
    confirmed_fields: Dict[str, Any] = {}


class GeneratePdfRequest(BaseModel):
    lost_amount: Optional[Any] = "5000"
    bank_name: Optional[str] = "SBI"
    utr_number: Optional[str] = ""
    suspect_identifier: Optional[str] = ""
    formal_narrative: str
    predicted_category: str = "UPI Related Frauds"
    confidence: float = 0.92
    state: Optional[str] = "Maharashtra"
    district: Optional[str] = "Mumbai Suburban"


class AgentSessionMessageRequest(BaseModel):
    message: str
    mode: Optional[str] = "text"
    language: Optional[str] = "hi"
    metadata: Optional[Dict[str, Any]] = None


class EvidenceReconcileRequest(BaseModel):
    typed_narrative: str
    ocr_entities: Optional[Dict[str, Any]] = None
    evidence_paths: Optional[List[str]] = None


class ResetRequest(BaseModel):
    session_id: str


class IntakeAnalyzeRequest(BaseModel):
    raw_text: str
    user_profile: Optional[Dict[str, Any]] = None
    evidence_paths: Optional[List[str]] = None


class AdjudicateRequest(BaseModel):
    reference: str
    action: str  # "CONFIRM" or "RECLASSIFY"
    new_category: Optional[str] = None
    officer_note: Optional[str] = None


class GenerateDocRequest(BaseModel):
    doc_type: str
    reference: str
    io_name: str = "Inspector R. K. Patil"
    io_designation: str = "Inspector of Police (Cyber Crime)"
    police_station: str = "Cyber Crime Police Station"


class TrackRequest(BaseModel):
    reference: str


# =============================================================================
# Helper Utilities
# =============================================================================

def _load_all_cases() -> List[Dict[str, Any]]:
    cases = []
    for path in sorted(glob.glob(os.path.join(CASE_DIR, "*.json"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data["_path"] = path
                data["_filename"] = os.path.basename(path)
                cases.append(data)
        except Exception:
            pass
    cases.sort(key=lambda c: c.get("generated_at", ""), reverse=True)
    return cases


def _find_case_by_ref(ref_str: str) -> Optional[Dict[str, Any]]:
    clean_target = re.sub(r"[^A-Za-z0-9]", "", ref_str or "").upper()
    if not clean_target:
        return None
    for c in _load_all_cases():
        c_ref = re.sub(r"[^A-Za-z0-9]", "", str(c.get("reference", ""))).upper()
        if c_ref == clean_target:
            return c
        # check filename match
        f_name = re.sub(r"[^A-Za-z0-9]", "", c.get("_filename", "")).upper()
        if clean_target in f_name:
            return c
    return None


# =============================================================================
# Core Endpoints
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h2>AI Cybercrime Complaint Assistant is starting up...</h2>")


@app.get("/health")
async def health_check():
    clf_ok = load_model()
    cases_count = len(glob.glob(os.path.join(CASE_DIR, "*.json")))
    return JSONResponse({
        "status": "healthy",
        "service": "National Cyber Crime Reporting Portal (NCRP) API",
        "version": "3.5.0",
        "classifier_loaded": clf_ok,
        "database": "SQLite (complaints.db, case_index.db)",
        "total_cases_indexed": cases_count,
        "supported_languages": ["en", "hi", "mr", "ta", "te", "bn", "gu", "pa", "ur"],
        "statutes": ["BNS 2023", "IT Act 2000", "BNSS 2023", "BSA 2023"]
    })


# =============================================================================
# Intake & AI Analysis Endpoints
# =============================================================================

@app.post("/api/intake/analyze")
async def analyze_intake_endpoint(req: IntakeAnalyzeRequest):
    """
    Step 1 -> Step 2 Engine:
    Combines:
      - Sentiment & Golden Hour Urgency Analysis
      - OCR entity extraction & reconciliation (if evidence uploaded)
      - Auto-fill payload creation
      - LinearSVC preliminary classification
      - Statutory BNS/IT Act legal sections resolution
    """
    raw_text = req.raw_text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Incident description cannot be empty.")

    # 1. Sentiment & Golden Hour Urgency
    sentiment_res = {}
    try:
        sentiment_res = analyze_sentiment_and_urgency(raw_text)
    except Exception as e:
        sentiment_res = {"urgency_level": "STANDARD", "is_golden_hour": False, "error": str(e)}

    # 2. OCR Evidence (if paths provided)
    ocr_entities = {}
    ocr_detailed = {}
    if req.evidence_paths:
        try:
            full_paths = [os.path.join(UPLOAD_DIR, os.path.basename(p)) for p in req.evidence_paths]
            valid_paths = [p for p in full_paths if os.path.exists(p)]
            if valid_paths:
                ocr_out = extract_from_images(valid_paths)
                ocr_entities = ocr_out.get("entities", {})
                ocr_detailed = ocr_out.get("detailed", {})
        except Exception as e:
            ocr_entities = {"_error": str(e)}

    # 3. Reconciliation
    reconcile_res = {}
    try:
        reconcile_res = reconcile(raw_text, ocr_entities)
    except Exception as e:
        reconcile_res = {"agreements": [], "conflicts": [], "gaps": [], "error": str(e)}

    # 4. Auto-Fill Pre-population
    # Never seed a request with a real person's profile. The caller must supply
    # any profile details it wants to use for autofill.
    user_prof = req.user_profile or {}
    autofill_res = {}
    try:
        autofill_res = generate_autofill_payload(raw_text, ocr_entities=ocr_entities, user_profile=user_prof)
    except Exception as e:
        autofill_res = {"error": str(e), "fields": {}}

    # 5. ML Crime Classification
    clf_res = classify_complaint_text(raw_text)
    pred_category = clf_res["predicted_category"]
    confidence = clf_res["confidence"]

    # 6. Legal Mapping
    legal_info = {}
    try:
        legal_info = map_sections(pred_category, complainant_age=user_prof.get("age"))
    except Exception:
        pass

    return JSONResponse({
        "ok": True,
        "sentiment": sentiment_res,
        "ocr_entities": ocr_entities,
        "ocr_detailed": ocr_detailed,
        "reconciliation": reconcile_res,
        "autofill": autofill_res,
        "classification": clf_res,
        "legal": legal_info,
        "standardised_narrative": autofill_res.get("standardised_narrative") or raw_text
    })


@app.post("/api/upload_evidence")
async def upload_evidence_endpoint(file: UploadFile = File(...)):
    """Upload screenshot/receipt, run OCR, and return extracted financial/suspect entities."""
    try:
        filename = f"evid_{int(time.time())}_{file.filename}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        ocr_res = extract_from_images([save_path])
        return JSONResponse({
            "ok": True,
            "filename": filename,
            "file_path": save_path,
            "chars_read": ocr_res.get("per_image", [{}])[0].get("chars", 0),
            "entities": ocr_res.get("entities", {}),
            "raw_snippet": ocr_res.get("per_image", [{}])[0].get("raw_text", "")[:300]
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/transcribe_audio")
async def transcribe_audio_endpoint(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
    task: Optional[str] = Form("transcribe")
):
    """Offline Whisper speech transcription in 16 Indian languages."""
    try:
        audio_bytes = await audio.read()
        res = transcribe_audio_bytes(
            audio_bytes,
            language=language,
            model_name="base",
            task=task or "transcribe"
        )
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# =============================================================================
# Case Submission & Registration Endpoints
# =============================================================================

@app.post("/api/cases/submit")
async def submit_case_endpoint(payload: Dict[str, Any]):
    """
    Step 3: Final Registration & Case File Assembly.
    Builds official JSON record, court-ready PDF, indexes into case_index.db.
    """
    try:
        comp = payload.get("complainant") or {}
        inc = payload.get("incident") or {}
        narrative = payload.get("standardised_narrative") or payload.get("incident_text") or "Cyber fraud incident reported."
        raw_text = payload.get("incident_text") or narrative

        # Classify
        clf_res = classify_complaint_text(narrative)
        assigned_sub = payload.get("sub_category") or clf_res["predicted_category"]
        confidence = clf_res["confidence"]

        # Parse transactions
        transactions = payload.get("transactions") or []
        suspect_transactions = payload.get("suspect_transactions") or []
        suspects = payload.get("suspects") or []
        evidence_list = payload.get("evidence") or []

        # Build Case Record
        case_record = build_case_file(
            complainant=comp,
            narrative=narrative,
            sub_category=assigned_sub,
            confidence=confidence,
            raw_complaint=raw_text,
            incident_datetime=inc.get("datetime") or str(inc.get("incident_date", "")),
            category=inc.get("category") or "Online Financial Fraud",
            modus_operandi=inc.get("modus_operandi") or "",
            incident_location=inc.get("location") or [],
            transactions=transactions,
            suspect_transactions=suspect_transactions,
            suspects=suspects,
            reconciliation=payload.get("reconciliation") or {},
            sentiment=payload.get("sentiment") or {}
        )

        ref_str = case_record["reference"]
        safe_filename = ref_str.replace("/", "-")
        json_path = os.path.join(CASE_DIR, f"{safe_filename}.json")
        pdf_path = os.path.join(CASE_DIR, f"{safe_filename}.pdf")

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(case_record, f, indent=2, ensure_ascii=False)

        # Generate PDF
        write_pdf(case_record, pdf_path)

        # Sync to graph index
        try:
            sync_all_case_files(CASE_DIR)
        except Exception:
            pass

        return JSONResponse({
            "ok": True,
            "reference": ref_str,
            "filename": safe_filename,
            "pdf_url": f"/api/pdf/{safe_filename}.pdf",
            "case": case_record
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# =============================================================================
# Case Querying, Tracking & Queue Endpoints
# =============================================================================

@app.get("/api/cases")
async def list_cases_endpoint(category: Optional[str] = None, priority: Optional[str] = None):
    """Retrieve all filed cases with high-level statistics."""
    all_cases = _load_all_cases()
    
    total_count = len(all_cases)
    total_loss = 0.0
    golden_hour_count = 0
    pending_count = 0
    category_counts: Dict[str, int] = {}
    urgency_counts: Dict[str, int] = {}

    for c in all_cases:
        # Sum loss
        txns = c.get("transactions") or []
        for t in txns:
            try:
                total_loss += float(t.get("amount", 0) or 0)
            except Exception:
                pass

        # Urgency & Golden Hour
        sent = c.get("sentiment") or {}
        urg = sent.get("urgency_level") or "STANDARD"
        urgency_counts[urg] = urgency_counts.get(urg, 0) + 1
        if sent.get("is_golden_hour"):
            golden_hour_count += 1

        # Status
        status = c.get("status") or "PENDING OFFICER REVIEW"
        if "PENDING" in status.upper():
            pending_count += 1

        # Category
        sub = c.get("classification", {}).get("sub_category") or c.get("incident", {}).get("category") or "Unclassified"
        category_counts[sub] = category_counts.get(sub, 0) + 1

    # Filter if requested
    filtered = all_cases
    if category:
        filtered = [c for c in filtered if c.get("classification", {}).get("sub_category") == category]
    if priority:
        filtered = [c for c in filtered if (c.get("sentiment", {}).get("urgency_level") or "").upper() == priority.upper()]

    return JSONResponse({
        "stats": {
            "total_cases": total_count,
            "total_loss_inr": total_loss,
            "golden_hour_count": golden_hour_count,
            "pending_count": pending_count,
            "category_distribution": category_counts,
            "urgency_distribution": urgency_counts
        },
        "cases": filtered
    })


@app.get("/api/cases/{case_ref:path}")
async def get_case_detail_endpoint(case_ref: str):
    """Retrieve full details for a single case."""
    case = _find_case_by_ref(case_ref)
    if not case:
        raise HTTPException(status_code=404, detail="Case record not found.")
    
    # Check if PDF exists
    safe_name = case.get("reference", "").replace("/", "-")
    pdf_path = os.path.join(CASE_DIR, f"{safe_name}.pdf")
    case["has_pdf"] = os.path.exists(pdf_path)
    case["pdf_url"] = f"/api/pdf/{safe_name}.pdf" if case["has_pdf"] else None

    return JSONResponse(case)


@app.post("/api/cases/track")
async def track_case_endpoint(req: TrackRequest):
    """Citizen status query by acknowledgement number."""
    case = _find_case_by_ref(req.reference)
    if not case:
        return JSONResponse({
            "found": False,
            "message": "No case file found matching the specified Acknowledgement Reference. Please verify and re-enter."
        })

    status = case.get("status") or "PENDING OFFICER REVIEW"
    friendly = {
        "PENDING OFFICER REVIEW": "Complaint registered successfully. Assigned to cyber cell officer for preliminary scrutiny.",
        "CONFIRMED BY OFFICER": "Complaint verified and confirmed by designated investigating officer.",
        "RECLASSIFIED BY OFFICER": "Complaint examined; statutory offence reclassified following legal review.",
    }.get(status, "Complaint is registered and undergoing standard verification.")

    return JSONResponse({
        "found": True,
        "reference": case.get("reference"),
        "status": status,
        "friendly_status": friendly,
        "category": case.get("classification", {}).get("sub_category") or case.get("incident", {}).get("category"),
        "lodged_at": case.get("generated_at"),
        "police_station": case.get("complainant", {}).get("police_station") or f"{case.get('complainant', {}).get('city', 'District')} Cyber Crime Police Station",
        "has_pdf": os.path.exists(os.path.join(CASE_DIR, f"{case.get('reference', '').replace('/', '-')}.pdf")),
        "pdf_url": f"/api/pdf/{case.get('reference', '').replace('/', '-')}.pdf"
    })


# =============================================================================
# Investigator Adjudication, Module L & Module M
# =============================================================================

@app.post("/api/cases/adjudicate")
async def adjudicate_case_endpoint(req: AdjudicateRequest):
    """Officer action: confirm or reclassify offence category."""
    case = _find_case_by_ref(req.reference)
    if not case:
        raise HTTPException(status_code=404, detail="Case record not found.")

    path = case.get("_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=500, detail="Case JSON file path is invalid.")

    if req.action == "CONFIRM":
        case["status"] = "CONFIRMED BY OFFICER"
        if isinstance(case.get("classification"), dict):
            case["classification"]["requires_confirmation"] = False
    elif req.action == "RECLASSIFY":
        if not req.new_category:
            raise HTTPException(status_code=400, detail="New category must be provided for reclassification.")
        old_cat = case.get("classification", {}).get("sub_category", "UNCLASSIFIED")
        if not isinstance(case.get("classification"), dict):
            case["classification"] = {}
        case["classification"]["sub_category"] = req.new_category
        case["classification"]["source"] = "Officer override"
        case["classification"]["requires_confirmation"] = False
        case["status"] = "RECLASSIFIED BY OFFICER"

        # History
        history = case.setdefault("_reclassification_history", [])
        history.append({
            "from": old_cat,
            "to": req.new_category,
            "note": req.officer_note or "",
            "at": datetime.now().isoformat(timespec="seconds")
        })

        # Remap legal sections
        try:
            age = case.get("complainant", {}).get("age")
            age = int(age) if age and str(age).isdigit() else None
            case["legal_sections"] = map_sections(req.new_category, complainant_age=age)
        except Exception:
            pass
    else:
        raise HTTPException(status_code=400, detail="Invalid action.")

    # Save to disk
    to_write = {k: v for k, v in case.items() if not k.startswith("_")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_write, f, indent=2, ensure_ascii=False)

    # Re-write PDF
    try:
        safe_name = case.get("reference", "").replace("/", "-")
        pdf_path = os.path.join(CASE_DIR, f"{safe_name}.pdf")
        write_pdf(case, pdf_path)
    except Exception:
        pass

    return JSONResponse({"ok": True, "status": case["status"], "case": case})


@app.post("/api/cases/syndicate")
async def syndicate_correlation_endpoint(payload: Dict[str, Any]):
    """Module L: Find cross-case patterns and build criminal syndicate dossiers."""
    ref = payload.get("reference")
    case = None
    if ref:
        case = _find_case_by_ref(ref)

    case_input = case or payload.get("case_data")
    if not case_input:
        raise HTTPException(status_code=400, detail="Provide case reference or case_data.")

    try:
        links = find_linked_cases(case_input)
        primary_suspect = None
        for sid in links.get("shared_identifiers", []):
            if "PHONE:" in sid or "UPI:" in sid:
                primary_suspect = sid.split(":", 1)[1].strip()
                break

        dossier = None
        if primary_suspect:
            dossier = build_suspect_dossier(primary_suspect)

        return JSONResponse({
            "ok": True,
            "links": links,
            "dossier": dossier
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/statutory_templates")
async def get_statutory_templates():
    """Module M: List available police legal notices and requisitions."""
    templates = list_available_templates()
    return JSONResponse(templates)


@app.post("/api/cases/generate_statutory_doc")
async def generate_statutory_doc_endpoint(req: GenerateDocRequest):
    """Module M: Auto-generate pre-filled police notices under BNSS & BSA 2023."""
    case = _find_case_by_ref(req.reference)
    if not case:
        raise HTTPException(status_code=404, detail="Case record not found.")

    try:
        doc_res = generate_investigation_document(
            doc_type=req.doc_type,
            case_data=case,
            io_name=req.io_name,
            io_designation=req.io_designation,
            police_station=req.police_station
        )
        return JSONResponse({
            "ok": True,
            "doc_type": req.doc_type,
            "title": doc_res.get("title"),
            "document_text": doc_res.get("document_text"),
            "statute": doc_res.get("statute"),
            "urgency": doc_res.get("urgency")
        })
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/benchmark")
async def get_benchmark_endpoint():
    """Retrieve certified empirical benchmark data and 21x21 confusion matrix."""
    bench_file = os.path.join(BASE_DIR, "models", "benchmark_metrics.json")
    if os.path.exists(bench_file):
        try:
            with open(bench_file, "r", encoding="utf-8") as f:
                return JSONResponse(json.load(f))
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({"error": "Benchmark data not found."}, status_code=404)


@app.get("/api/pdf/{filename}")
async def serve_pdf(filename: str):
    """Serve court-admissible PDF file."""
    safe_name = os.path.basename(filename)
    path = os.path.join(CASE_DIR, safe_name)
    if os.path.exists(path):
        return FileResponse(path, media_type="application/pdf", filename=safe_name)
    raise HTTPException(status_code=404, detail="Requested PDF case file not found on disk.")


# =============================================================================
# Conversational Intake / Copilot (Dual Mode)
# =============================================================================

@app.get("/api/state")
async def get_state(session_id: str = "default_session"):
    session = create_or_get_session(session_id)
    history = get_session_history(session_id)
    draft = get_complaint_draft(session_id)
    return JSONResponse({
        "session": session,
        "history": history,
        "draft": draft or {}
    })


@app.post("/api/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...), language: str = Form("hi")):
    """
    Local Whisper Speech-to-Text Endpoint.
    Transcribes audio recorded from the citizen's microphone via HTML5 MediaRecorder.
    Operates 100% locally via ffmpeg and Whisper tiny, supporting Hindi, Marathi, and English.
    """
    try:
        audio_bytes = await file.read()
        lang_code = language if language in ["hi", "mr", "en"] else "hi"
        res = transcribe_audio_bytes(
            audio_bytes,
            filename=file.filename or "recording.webm",
            lang_code=lang_code,
            model_name="tiny"
        )
        return JSONResponse({
            "ok": res.get("ok", False),
            "text": res.get("text", "").strip(),
            "language": res.get("language", lang_code),
            "latency": res.get("latency_seconds", 0)
        })
    except Exception as e:
        return JSONResponse({"ok": False, "text": "", "error": str(e)}, status_code=500)


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    create_or_get_session(req.session_id, req.language)
    save_message(req.session_id, "user", req.message)

    turn_result = conduct_counselor_turn(
        user_message=req.message,
        conversation_history=req.history,
        current_docket=req.current_docket,
        language=req.language
    )

    save_message(req.session_id, "assistant", turn_result["spoken_response"])
    save_complaint_draft(req.session_id, turn_result)

    return JSONResponse(turn_result)


@app.post("/agent/session/{session_id}/message")
async def agent_session_message_endpoint(session_id: str, req: AgentSessionMessageRequest):
    """
    Module A: Stateful Conversational AI Intake Agent.
    Accepts voice/text utterance, updates session state machine against the required NCRP schema,
    evaluates rule-based urgency, and returns ONE targeted follow-up question.
    """
    session = create_or_get_session(session_id, req.language)
    save_message(session_id, "user", req.message)
    
    current_draft = get_complaint_draft(session_id) or {}
    history = get_session_history(session_id)

    turn_result = conduct_counselor_turn(
        user_message=req.message,
        conversation_history=history,
        current_docket=current_draft,
        language=req.language or session.get("language", "hi")
    )

    save_message(session_id, "assistant", turn_result["spoken_response"])
    save_complaint_draft(session_id, turn_result)

    return JSONResponse({
        "session_id": session_id,
        "input_mode": req.mode or "text",
        "timestamp": datetime.now().isoformat(),
        "detected_language": req.language or "hi",
        "spoken_response": turn_result["spoken_response"],
        "spoken_response_en": turn_result.get("spoken_response_en"),
        "session_state": {
            "incident_category": turn_result.get("incident_category"),
            "date_time_of_incident": turn_result.get("date_time_of_incident"),
            "platform_involved": turn_result.get("platform_involved"),
            "financial_loss_amount": turn_result.get("financial_loss_amount"),
            "bank_name": turn_result.get("bank_name"),
            "utr_number": turn_result.get("utr_number"),
            "suspect_details": turn_result.get("suspect_details"),
            "complainant_age": turn_result.get("complainant_age"),
            "evidence_available": turn_result.get("evidence_available"),
            "urgency_flag": turn_result.get("urgency_flag", False),
            "urgency_reason": turn_result.get("urgency_reason", "STANDARD"),
            "turn_count": turn_result.get("turn_count", 1),
            "is_complete": turn_result.get("is_complete", False),
            "formal_narrative": turn_result.get("formal_narrative")
        },
        "emergency_guidance": turn_result.get("emergency_guidance")
    })


@app.post("/api/evidence/reconcile")
async def evidence_reconcile_endpoint(req: EvidenceReconcileRequest):
    """
    Module C: OCR & Entity Reconciliation Layer.
    Merges OCR entities with user's narrative and surfaces conflicting values for victim confirmation.
    """
    ocr_facts = req.ocr_entities or {}
    if req.evidence_paths:
        try:
            full_paths = [os.path.join(UPLOAD_DIR, os.path.basename(p)) for p in req.evidence_paths]
            valid_paths = [p for p in full_paths if os.path.exists(p)]
            if valid_paths:
                ocr_out = extract_from_images(valid_paths)
                ocr_facts.update(ocr_out.get("entities", {}))
        except Exception:
            pass

    reconciliation_result = reconcile(req.typed_narrative, ocr_facts)
    return JSONResponse(reconciliation_result)


@app.post("/api/confirm")
async def confirm_endpoint(req: ConfirmRequest):
    classification_res = classify_complaint_text(req.confirmed_narrative)
    pred_category = classification_res["predicted_category"]
    confidence = classification_res["confidence"]
    decision_margin = classification_res["decision_margin"]

    fields = req.confirmed_fields or {}
    age = fields.get("complainant_age")
    
    legal_info = {}
    try:
        legal_info = map_sections(pred_category, complainant_age=age)
    except Exception:
        pass

    # Law Enforcement Routing (Deterministic static lookup)
    user_state = fields.get("state") or fields.get("complainant_state") or "Maharashtra"
    user_district = fields.get("district") or fields.get("city") or "Mumbai Suburban"
    routing_info = route_complaint(
        state=user_state,
        district=user_district,
        city=fields.get("city")
    )

    confirm_and_classify_draft(
        session_id=req.session_id,
        user_edited_narrative=req.confirmed_narrative,
        predicted_category=pred_category,
        confidence=confidence,
        decision_margin=decision_margin
    )

    main_cat = get_main_category(pred_category)
    return JSONResponse({
        "session_id": req.session_id,
        "main_category": main_cat,
        "predicted_category": pred_category,
        "confidence": confidence,
        "decision_margin": decision_margin,
        "top_alternatives": classification_res["top_alternatives"],
        "caveat": classification_res["caveat"],
        "routing": routing_info,
        "legal": {
            "bns_sections": [f"BNS Sec {s.get('section')}: {s.get('description', '')}" for s in legal_info.get("bns", [])],
            "it_act_sections": [f"IT Act Sec {s.get('section')}: {s.get('description', '')}" for s in legal_info.get("it_act", [])],
            "other_sections": [f"{s.get('act', 'Act')} Sec {s.get('section')}: {s.get('description', '')}" for s in legal_info.get("other", [])],
            "conditional_applied": legal_info.get("conditional_applied", []),
            "cognizable": any(s.get("cognizable", True) for s in legal_info.get("bns", []) + legal_info.get("it_act", [])),
            "bailable": all(s.get("bailable", False) for s in legal_info.get("bns", []) if "bailable" in s),
        }
    })


@app.post("/api/generate_pdf")
async def generate_pdf_endpoint(req: GeneratePdfRequest):
    """
    Generate and stream an official, court-ready Cybercrime Complaint PDF draft.
    """
    try:
        ref_id = f"CYB-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        pdf_filename = f"{ref_id}_Complaint_Draft.pdf"
        pdf_path = os.path.join(CASE_DIR, pdf_filename)
        
        txns = []
        if req.lost_amount:
            try:
                amt = float(str(req.lost_amount).replace(",", "").replace("₹", "").strip())
            except Exception:
                amt = 5000.0
            txns.append({
                "bank_name": req.bank_name or "Bank",
                "account_number": "XXXX-XXXX",
                "amount": amt,
                "utr_number": req.utr_number or "Pending Verification",
                "date": datetime.now().strftime("%Y-%m-%d")
            })

        suspects = []
        if req.suspect_identifier:
            suspects.append({
                "name": "Unknown Suspect",
                "phone": req.suspect_identifier,
                "details": f"Channel/Identifier: {req.suspect_identifier}"
            })

        routing_info = route_complaint(
            state=req.state or "Maharashtra",
            district=req.district or "Mumbai Suburban"
        )

        case_record = build_case_file(
            complainant={
                "name": "Citizen Complainant",
                "phone": "Confidential / Provided at Intake",
                "city": req.district or "Mumbai",
                "state": req.state or "Maharashtra",
                "police_station": routing_info["police_station"]
            },
            narrative=req.formal_narrative,
            sub_category=req.predicted_category,
            confidence=req.confidence,
            raw_complaint=req.formal_narrative,
            incident_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            category=get_main_category(req.predicted_category),
            modus_operandi=f"{req.predicted_category} via {req.bank_name or 'Digital Gateway'}",
            transactions=txns,
            suspects=suspects
        )

        write_pdf(case_record, pdf_path)
        
        if os.path.exists(pdf_path):
            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=pdf_filename
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to write PDF to disk.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/taxonomy")
async def get_taxonomy_endpoint():
    """Return the authoritative 3 main categories and 21 sub-categories."""
    return JSONResponse(MAIN_CATEGORIES)


@app.post("/api/reset")
async def reset_endpoint(req: ResetRequest):
    reset_session(req.session_id)
    return JSONResponse({"ok": True, "message": "Session reset successfully"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=os.getenv("HOST", "127.0.0.1"), port=8000, reload=True)
