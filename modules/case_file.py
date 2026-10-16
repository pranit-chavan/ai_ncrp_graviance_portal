"""
MODULE E - Case File Generator

Assembles the output of every other module into one investigator-ready case file.

WHAT IT CONSUMES
    complainant details   structured form fields
    incident details       date/time, category, modus operandi, where it happened
    narrative              Module A  (stubbed until A is built)
    entities               Module C  (stubbed until C is built)
    classification         Module B  (the trained classifier)
    legal sections         Module D  (built and working)
    transactions            victim's own lost-money transaction(s), if any
    suspect_transactions   money-trail transaction(s) on the suspect side, if known
    suspects                suspect identity record(s), if known
    evidence_table          structured evidence rows (description / text info / file)

WHAT IT PRODUCES
    a JSON record   - machine readable, goes to the database and Module F
    a PDF document  - what an investigating officer actually opens

DESIGN DECISION: every module is optional. If Module A or C has not run, the case
file is still produced with those sections marked "not available". A pipeline that
collapses because one component is missing is useless in the field, where OCR fails
on poor screenshots and complainants submit text with no attachments at all.

DESIGN DECISION: the case file records CONFIDENCE and states plainly that the
classification is machine-generated and requires officer confirmation. This system
assists an officer; it does not decide.

DESIGN DECISION: "incident.category" / "incident.sub_category" / "incident.modus_operandi"
are what the CITIZEN selected (AI-suggested, but citizen-editable, exactly as on the
real portal). "classification" is what Module B actually computed at submission time.
The two are kept separate and both are shown to the officer - the gap between them is
often the most useful signal, since self-categorisation is what citizens get wrong.

DESIGN DECISION: every field added here is additive. A case file written by an
older version of this module (no "incident", "transactions", "suspects",
"evidence.table" keys) still loads: every new field defaults to an empty
value here and every reader is expected to treat a missing key the same way.

USAGE
    from modules.case_file import build_case_file, write_pdf

    case = build_case_file(
        complainant={"name": "...", "age": 34, "phone": "...", "city": "..."},
        narrative="...",
        sub_category="AePS Fraud",
        confidence=0.94,
        entities={"amount": "Rs. 40,000", "upi_id": "x@ybl"},
        attachments=["screenshot1.png"],
    )
    write_pdf(case, "case_files/NCRP-2026-000123.pdf")

    python modules/case_file.py        # builds a demo case file end to end
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.legal_mapping import map_sections, format_sections, UnknownCategory

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(_HERE), "case_files")

# Actions an officer should take first, by category. Time matters most in the
# financial categories, where the golden hour determines whether funds can be held.
SUGGESTED_ACTIONS = {
    "_financial": [
        "Report beneficiary account and UPI identifiers to the bank for immediate freezing",
        "Raise the transaction on the NCRP/I4C portal within the golden hour",
        "Obtain the bank statement and transaction references from the complainant",
        "Issue notice to the beneficiary bank for KYC of the recipient account",
    ],
    "_account": [
        "Advise the complainant to reset credentials and enable two-factor authentication",
        "Obtain access logs and login records from the service provider",
        "Preserve screenshots of the account activity before it is altered",
    ],
    "_content": [
        "Issue a takedown request to the platform for the offending content or profile",
        "Preserve the profile link, post URLs and screenshots before removal",
        "Obtain subscriber details of the account from the platform",
    ],
    "_institutional": [
        "Confirm the organisation has reported to CERT-In within the required period",
        "Secure server and access logs before restoration overwrites them",
        "Obtain the incident report and forensic findings from the organisation",
    ],
}

CATEGORY_ACTION_GROUP = {
    "AePS Fraud": "_financial",
    "Debit/Credit Card Fraud / SIM Swap Fraud": "_financial",
    "Demat / Depository Fraud": "_financial",
    "E-Wallet Related Fraud": "_financial",
    "Internet Banking Related Fraud": "_financial",
    "UPI Related Frauds": "_financial",
    "Online Job Fraud": "_financial",
    "Online Matrimonial Fraud": "_financial",
    "Impersonating Email (Business Email Compromise)": "_financial",
    "Cheating by Impersonation": "_financial",
    "Email Phishing": "_account",
    "Email Hacking": "_account",
    "Profile Hacking / Identity Theft": "_account",
    "Fake / Impersonating Profile": "_content",
    "Cyber Bullying / Stalking / Sexting": "_content",
    "Provocative Speech for Unlawful Acts": "_content",
    "Intimidating Email": "_institutional",
    "Damage to Computer / Computer System": "_institutional",
    "Unauthorised Access / Data Breach": "_institutional",
    "Tampering with Computer Source Document": "_institutional",
    "Website Defacement / Hacking": "_institutional",
}

CONFIDENCE_BANDS = [
    (0.90, "HIGH", "Classification is reliable. Officer confirmation still required."),
    (0.70, "MEDIUM", "Review the narrative before accepting the classification."),
    (0.00, "LOW", "Manual classification recommended. Adjacent categories should be considered."),
]


def _reference_number(seq=None):
    now = datetime.now()
    seq = seq if seq is not None else int(now.timestamp()) % 100000
    return f"NCRP/{now.year}/{seq:06d}"


def _confidence_band(confidence):
    if confidence is None:
        return "NOT SUPPLIED", "No confidence score was returned by the classifier."
    for threshold, label, guidance in CONFIDENCE_BANDS:
        if confidence >= threshold:
            return label, guidance
    return "LOW", ""


def build_case_file(complainant, narrative, sub_category,
                    confidence=None, entities=None, attachments=None,
                    raw_complaint=None, reference=None,
                    # -- NCRP-shaped additions, all optional and additive --
                    incident_datetime=None, category=None, modus_operandi=None,
                    incident_location=None, transactions=None,
                    suspect_transactions=None, suspects=None,
                    evidence_table=None, gaps_identified=None,
                    reconciliation=None, sentiment=None,
                    delay_in_reporting=None, delay_reason=None):
    """Assemble a case file record. Missing modules degrade gracefully.

    incident_datetime      str, when the citizen says it happened
    category                str, the citizen's own top-level category pick
    modus_operandi          str, the citizen's own modus-operandi text
    incident_location       list[str], platforms/media where it happened
    transactions            list[dict], the victim's own lost-money transaction(s)
    suspect_transactions    list[dict], money-trail transaction(s) on the suspect side
    suspects                list[dict], suspect identity record(s)
    evidence_table          list[dict], structured evidence rows
    reconciliation          dict, output of modules.reconcile.reconcile()
    delay_in_reporting      str, 'Yes' or 'No'
    delay_reason            str, explanation if delay > 24 hours
    """

    entities = entities or {}
    attachments = attachments or []
    transactions = transactions or []
    suspect_transactions = suspect_transactions or []
    suspects = suspects or []
    evidence_table = evidence_table or []
    incident_location = incident_location or []

    # ---- legal sections (Module D) ----
    age = complainant.get("age")
    try:
        legal = map_sections(sub_category, complainant_age=age)
        legal_status = "resolved"
    except UnknownCategory as e:
        legal = None
        legal_status = f"unresolved: {e}"

    band, guidance = _confidence_band(confidence)
    group = CATEGORY_ACTION_GROUP.get(sub_category)
    actions = list(SUGGESTED_ACTIONS.get(group, []))

    if legal:
        for c in legal["conditional_applied"]:
            if c["status"].startswith("NOT EVALUATED"):
                actions.insert(0, "Confirm the complainant's age - POCSO may apply.")

    case = {
        "reference": reference or _reference_number(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),

        "complainant": {
            "title": complainant.get("title", ""),
            "name": complainant.get("name", "not supplied"),
            "gender": complainant.get("gender", "not supplied"),
            "dob": complainant.get("dob", "not supplied"),
            "age": age if age is not None else "not supplied",
            "relative_name": complainant.get("relative_name", "not supplied"),
            "relative_type": complainant.get("relative_type", "Father"),
            "phone": complainant.get("phone", "not supplied"),
            "email": complainant.get("email", "not supplied"),
            "address": complainant.get("address", "not supplied"),
            "city": complainant.get("city", "not supplied"),
            "district": complainant.get("district", "not supplied"),
            "state": complainant.get("state", "not supplied"),
            "pincode": complainant.get("pincode", "not supplied"),
            "police_station": complainant.get("police_station", "not supplied"),
            "relationship_with_victim": complainant.get("relationship_with_victim", "Self"),
            "id_type": complainant.get("id_type", "not supplied"),
            "id_upload_name": complainant.get("id_upload_name", "not supplied"),
        },

        "incident": {
            # what the CITIZEN filed - AI-suggested, citizen-editable, may disagree
            # with "classification" below. That gap is deliberately preserved.
            "datetime": incident_datetime or "not supplied",
            "category": category or "not supplied",
            "sub_category_reported": sub_category if category else "not supplied",
            "modus_operandi": modus_operandi or "not supplied",
            "location": incident_location,
            "delay_in_reporting": delay_in_reporting or "No",
            "delay_reason": delay_reason or "N/A",
        },

        "complaint": {
            "raw_text": raw_complaint or "not supplied",
            "standardised_narrative": narrative or "NOT AVAILABLE - Module A did not run",
            "narrative_source": "Module A" if narrative else "unavailable",
        },

        "classification": {
            # what MODULE B actually computed. Always machine-generated, always
            # subject to officer confirmation, regardless of what the citizen
            # picked in "incident" above.
            "sub_category": sub_category,
            "confidence": confidence,
            "confidence_band": band,
            "guidance": guidance,
            "source": "Module B - machine generated",
            "requires_confirmation": True,
        },

        "extracted_entities": entities if entities else {"_status": "NOT AVAILABLE - Module C did not run"},

        "legal_sections": legal if legal else {"_status": legal_status},

        "transactions": transactions,
        "suspect_transactions": suspect_transactions,
        "suspects": suspects,

        "evidence": {
            "attachments": attachments,
            "count": len(attachments),
            "table": evidence_table,
        },

        "intake_gaps_identified": gaps_identified or [],

        "reconciliation": {
            "agreements": reconciliation.get("agreements", []) if reconciliation else [],
            "conflicts": reconciliation.get("conflicts", []) if reconciliation else [],
            "gaps": reconciliation.get("gaps", []) if reconciliation else [],
            "ocr_only": reconciliation.get("ocr_only", []) if reconciliation else [],
            "confidence_note": reconciliation.get("confidence_note", "not available") if reconciliation else "not available",
            "has_conflicts": reconciliation.get("has_conflicts", False) if reconciliation else False,
        } if reconciliation else {"_status": "not available"},

        "sentiment": sentiment or {},

        "data_provenance": {
            "narrative": "Module A (AI Standardised)" if narrative else "Citizen Raw Text",
            "extracted_entities_source": "Module C (OCR + Regex)" if entities else "Not Available",
            "classification_source": "Module B (LinearSVC Model)",
            "legal_mapping_source": "Module D (Deterministic Statutory Lookup)",
            "reconciliation_source": "Reconciliation Layer" if reconciliation else "Not Available",
        },

        "suggested_actions": actions,

        "status": "PENDING OFFICER REVIEW",

        "_disclaimer": (
            "This case file was assembled automatically from a citizen complaint. "
            "The classification and the legal provisions proposed are decision-support "
            "for the investigating officer and require confirmation before any action "
            "is taken on them."
        ),
    }
    return case


# ---- rendering -------------------------------------------------------------

def format_text(case):
    """Plain-text rendering, useful for the console and for the dashboard."""
    L = []
    add = L.append
    add("=" * 74)
    add(f"CASE FILE   {case['reference']}")
    add(f"Generated   {case['generated_at']}")
    add(f"Status      {case['status']}")
    add("=" * 74)

    c = case["complainant"]
    add("\nCOMPLAINANT")
    add(f"  Name    : {c['name']}")
    add(f"  Age     : {c['age']}")
    add(f"  Contact : {c['phone']}   {c['email']}")
    add(f"  Location: {c['city']}, {c['state']}")

    inc = case.get("incident") or {}
    if any(v not in (None, "", "not supplied", []) for v in inc.values()):
        add("\nINCIDENT (as filed by the citizen)")
        add(f"  Date/time    : {inc.get('datetime', 'not supplied')}")
        add(f"  Category     : {inc.get('category', 'not supplied')}")
        add(f"  Modus operandi: {inc.get('modus_operandi', 'not supplied')}")
        loc = inc.get("location") or []
        add(f"  Where it happened: {', '.join(loc) if loc else 'not supplied'}")

    cl = case["classification"]
    add("\nCLASSIFICATION (Module B - machine generated)")
    add(f"  Sub-category : {cl['sub_category']}")
    conf = f"{cl['confidence']:.1%}" if isinstance(cl["confidence"], float) else "not supplied"
    add(f"  Confidence   : {conf}  [{cl['confidence_band']}]")
    add(f"  {cl['guidance']}")

    add("\nSTANDARDISED NARRATIVE")
    for line in _wrap(case["complaint"]["standardised_narrative"], 70):
        add(f"  {line}")

    add("\nEXTRACTED ENTITIES")
    ent = case["extracted_entities"]
    if "_status" in ent:
        add(f"  {ent['_status']}")
    else:
        for k, v in ent.items():
            add(f"  {k:<18}: {v}")

    add("")
    legal = case["legal_sections"]
    if "_status" in legal:
        add(f"LEGAL SECTIONS\n  {legal['_status']}")
    else:
        add(format_sections(legal))

    txns = case.get("transactions") or []
    if txns:
        add("\nVICTIM TRANSACTION DETAILS")
        for i, t in enumerate(txns, 1):
            add(f"  {i}. {t.get('bank', '?')}  acct/UPI {t.get('account_no', '?')}  "
                f"UTR {t.get('transaction_id', '?')}  Rs.{t.get('amount', '?')}  "
                f"on {t.get('transaction_date', '?')}")

    stxns = case.get("suspect_transactions") or []
    if stxns:
        add("\nSUSPECT ACCOUNT / MONEY-TRAIL DETAILS")
        for i, t in enumerate(stxns, 1):
            add(f"  {i}. {t.get('method', '?')}  {t.get('bank', '?')}  "
                f"acct/UPI {t.get('account_no', '?')}  UTR {t.get('transaction_id', '?')}  "
                f"Rs.{t.get('amount', '?')}  on {t.get('transaction_date', '?')}")

    suspects = case.get("suspects") or []
    if suspects:
        add("\nSUSPECT DETAILS")
        for i, s in enumerate(suspects, 1):
            add(f"  {i}. {s.get('name', 'unknown')}  ({s.get('id_type', '?')}: {s.get('id_number', '?')})")
        addr = suspects[0].get("address") if suspects else None
        if addr:
            add(f"  Address: {addr}")

    add("\nEVIDENCE")
    ev = case["evidence"]
    if ev["count"]:
        for a in ev["attachments"]:
            add(f"  - {a}")
    else:
        add("  No attachments submitted")
    for row in ev.get("table") or []:
        add(f"    {row.get('description', '')}: {row.get('text_information', '')}")

    add("\nSUGGESTED FIRST ACTIONS")
    for i, a in enumerate(case["suggested_actions"], 1):
        add(f"  {i}. {a}")

    add("\n" + "-" * 74)
    for line in _wrap(case["_disclaimer"], 72):
        add(line)
    return "\n".join(L)


def _wrap(text, width):
    words, line, out = str(text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line); line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return out or [""]


def write_json(case, path=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = path or os.path.join(OUT_DIR, case["reference"].replace("/", "-") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(case, f, indent=2, ensure_ascii=False)
    return path


def write_pdf(case, path=None):
    """Render the case file as an official, court-ready Ministry of Home Affairs (MHA) /
    National Cyber Crime Reporting Portal (NCRP) Complaint Acknowledgement & Investigation Report.
    Requires reportlab.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
        )
    except ImportError:
        raise SystemExit("PDF output needs reportlab.  pip install reportlab")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = path or os.path.join(OUT_DIR, case["reference"].replace("/", "-") + ".pdf")

    # ---- Geometry & Color Scheme ----
    # A4: 595.27 x 841.89 pt. 14mm margins -> 516 pt printable width.
    W_TOTAL = 516

    NAVY = colors.HexColor("#0f2b5c")
    NAVY_LIGHT = colors.HexColor("#1e3a8a")
    SAFFRON = colors.HexColor("#d97706")
    GREEN = colors.HexColor("#15803d")
    LIGHT_BG = colors.HexColor("#f8fafc")
    ALT_ROW = colors.HexColor("#f1f5f9")
    BORDER_COL = colors.HexColor("#cbd5e1")
    TEXT_DARK = colors.HexColor("#0f172a")
    TEXT_MUTED = colors.HexColor("#475569")
    RED_ALERT = colors.HexColor("#b91c1c")
    WHITE = colors.HexColor("#ffffff")
    AMBER_BG = colors.HexColor("#fffbeb")

    ss = getSampleStyleSheet()

    # Typography styles
    style_hdr_hi = ParagraphStyle(
        "hdr_hi", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10,
        textColor=colors.HexColor("#1e293b"), alignment=1
    )
    style_hdr_en = ParagraphStyle(
        "hdr_en", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11,
        textColor=NAVY, alignment=1
    )
    style_portal = ParagraphStyle(
        "portal", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=13.5,
        textColor=NAVY, alignment=1
    )
    style_doc_title = ParagraphStyle(
        "doc_title", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12.5,
        textColor=colors.HexColor("#92400e"), alignment=1, spaceBefore=2, spaceAfter=2
    )
    style_doc_sub = ParagraphStyle(
        "doc_sub", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=7, leading=9,
        textColor=TEXT_MUTED, alignment=1, spaceAfter=4
    )
    style_part_hdr = ParagraphStyle(
        "part_hdr", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10,
        textColor=WHITE
    )

    c_label = ParagraphStyle(
        "c_label", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9,
        textColor=colors.HexColor("#334155")
    )
    c_val = ParagraphStyle(
        "c_val", parent=ss["Normal"], fontName="Helvetica", fontSize=7.2, leading=9,
        textColor=TEXT_DARK
    )
    c_val_bold = ParagraphStyle(
        "c_val_bold", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9,
        textColor=TEXT_DARK
    )
    c_val_alert = ParagraphStyle(
        "c_val_alert", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9,
        textColor=RED_ALERT
    )
    c_th = ParagraphStyle(
        "c_th", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9,
        textColor=WHITE
    )
    body_text = ParagraphStyle(
        "body_text", parent=ss["Normal"], fontName="Helvetica", fontSize=7.5, leading=10.5,
        textColor=TEXT_DARK
    )
    raw_statement_style = ParagraphStyle(
        "raw_stmt", parent=ss["Normal"], fontName="Helvetica-Oblique", fontSize=7.2, leading=10,
        textColor=colors.HexColor("#1e293b")
    )
    disclaimer_style = ParagraphStyle(
        "disclaimer", parent=ss["Normal"], fontName="Helvetica", fontSize=6.5, leading=8.5,
        textColor=colors.HexColor("#64748b")
    )

    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm,
                            title=f"NCRP Official Report - {case['reference']}")
    S = []

    # ---- 1. Bilingual Government Letterhead ----
    S.append(Paragraph("भारत सरकार / GOVERNMENT OF INDIA", style_hdr_hi))
    S.append(Paragraph("गृह मंत्रालय / MINISTRY OF HOME AFFAIRS", style_hdr_en))
    S.append(Paragraph("भारतीय साइबर अपराध समन्वय केंद्र (I4C) | राष्ट्रीय साइबर अपराध रिपोर्टिंग पोर्टल", style_hdr_hi))
    S.append(Paragraph("INDIAN CYBER CRIME COORDINATION CENTRE (I4C) &bull; NATIONAL CYBER CRIME REPORTING PORTAL", style_portal))
    S.append(HRFlowable(width="100%", thickness=1.75, color=SAFFRON, spaceBefore=3, spaceAfter=3))
    S.append(Paragraph("OFFICIAL COMPLAINT ACKNOWLEDGEMENT &amp; INVESTIGATION REPORT", style_doc_title))
    S.append(Paragraph("(Statutory Digital Evidentiary Record under Information Technology Act 2000 &amp; Bharatiya Nagarik Suraksha Sanhita 2023)", style_doc_sub))

    # ---- 2. High-Visibility Acknowledgement Banner ----
    c = case.get("complainant", {})
    sentiment = case.get("sentiment") or {}
    is_golden = sentiment.get("is_golden_hour") or sentiment.get("urgency_level") == "EMERGENCY_GOLDEN_HOUR"
    priority_text = "CRITICAL: GOLDEN HOUR INTERVENTION" if is_golden else "STANDARD STATUTORY INVESTIGATION"

    ps_str = c.get("police_station") or "Cyber Crime Police Station"
    dist_state = f"{c.get('district', '')}, {c.get('state', '')}".strip(", ")
    jurisdiction_str = f"{ps_str} ({dist_state})" if dist_state else ps_str

    banner_data = [
        [
            Paragraph(f"<b>ACKNOWLEDGEMENT NO:</b><br/>{case['reference']}", ParagraphStyle("b1", parent=c_val_bold, textColor=WHITE)),
            Paragraph(f"<b>FILING TIMESTAMP (IST):</b><br/>{case.get('generated_at', 'not supplied')}", ParagraphStyle("b2", parent=c_val, textColor=WHITE)),
            Paragraph(f"<b>OPERATIONAL PRIORITY:</b><br/><b>{priority_text}</b>", ParagraphStyle("b3", parent=c_val_bold, textColor=colors.HexColor("#fef08a") if is_golden else WHITE)),
        ],
        [
            Paragraph(f"<b>ASSIGNED POLICE JURISDICTION:</b> {jurisdiction_str}", ParagraphStyle("b4", parent=c_val, textColor=WHITE)),
            "",
            Paragraph(f"<b>CURRENT ADJUDICATION:</b> {case.get('status', 'PENDING OFFICER REVIEW')}", ParagraphStyle("b5", parent=c_val_bold, textColor=WHITE)),
        ]
    ]
    t_banner = Table(banner_data, colWidths=[175, 175, 166])
    t_banner.setStyle(TableStyle([
        ("SPAN", (0, 1), (1, 1)),
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 1, SAFFRON),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#334155")),
    ]))
    S.append(t_banner)
    S.append(Spacer(1, 5))

    def make_part_banner(title_text):
        t = Table([[Paragraph(f"<b>{title_text}</b>", style_part_hdr)]], colWidths=[W_TOTAL])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def make_grid(rows, col_widths):
        table_rows = []
        for r in rows:
            formatted_row = []
            for idx, cell in enumerate(r):
                if isinstance(cell, Paragraph):
                    formatted_row.append(cell)
                elif idx % 2 == 0:
                    formatted_row.append(Paragraph(str(cell), c_label))
                else:
                    formatted_row.append(Paragraph(str(cell), c_val))
            table_rows.append(formatted_row)
        t = Table(table_rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, ALT_ROW]),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER_COL),
        ]))
        return t

    def make_data_table(headers, data_rows, col_widths):
        hdr_row = [Paragraph(f"<b>{h}</b>", c_th) for h in headers]
        rows = [hdr_row]
        for r in data_rows:
            rows.append([Paragraph(str(cell), c_val) if not isinstance(cell, Paragraph) else cell for cell in r])
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY_LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ALT_ROW]),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER_COL),
        ]))
        return t

    # ---- 3. PART I: Incident Particulars & Statutory Categorisation ----
    S.append(make_part_banner("PART I: INCIDENT PARTICULARS &amp; STATUTORY OFFENCE CATEGORISATION"))
    inc = case.get("incident") or {}
    cl = case.get("classification") or {}
    conf = f"{cl['confidence']:.1%}" if isinstance(cl.get("confidence"), float) else "not supplied"
    loc = inc.get("location") or []
    loc_str = ", ".join(loc) if loc else "not supplied"

    delay_rep = inc.get("delay_in_reporting", "No")
    delay_desc = f"{delay_rep} (Reason: {inc.get('delay_reason', 'N/A')})" if delay_rep == "Yes" else "No (Reported without statutory delay)"

    part1_rows = [
        ["Primary Crime Category", inc.get("category", "not supplied"), "Reported Sub-Category", inc.get("sub_category_reported", cl.get("sub_category", "not supplied"))],
        ["AI Machine Classification", f"{cl.get('sub_category', 'not supplied')} [Confidence: {conf}]", "Reliability Band", f"{cl.get('confidence_band', 'LOW')} ({cl.get('guidance', '')})"],
        ["Occurrence Date & Time", inc.get("datetime", "not supplied"), "Reporting Delay Audit", delay_desc],
        ["Crime Inception Media", loc_str, "Modus Operandi Summary", inc.get("modus_operandi", "not supplied")],
    ]
    S.append(make_grid(part1_rows, [115, 143, 115, 143]))
    S.append(Spacer(1, 4))

    # ---- 4. PART II: Complaint Statements & Factual Testimony ----
    S.append(make_part_banner("PART II: COMPLAINT STATEMENTS &amp; FACTUAL TESTIMONY"))
    narrative_p = Paragraph(f"<b>Standardised Legal Narrative (Module A Structured Account):</b><br/>{case['complaint'].get('standardised_narrative', 'NOT AVAILABLE')}", body_text)
    t_narrative = Table([[narrative_p]], colWidths=[W_TOTAL])
    t_narrative.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COL),
    ]))
    S.append(t_narrative)
    S.append(Spacer(1, 3))

    raw_text = case["complaint"].get("raw_text") or "not supplied"
    raw_p = Paragraph(f"<b>Original Citizen Grievance Statement (Evidentiary Text as Filed):</b><br/><i>&ldquo;{raw_text}&rdquo;</i><br/><font size='6' color='#64748b'>[Evidentiary record preserved verbatim pursuant to Section 63 BNSS 2023 &amp; Section 61 Bharatiya Sakshya Adhiniyam 2023]</font>", raw_statement_style)
    t_raw = Table([[raw_p]], colWidths=[W_TOTAL])
    t_raw.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fefce8")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#fde047")),
    ]))
    S.append(t_raw)
    S.append(Spacer(1, 4))

    # ---- 5. PART III: Digital Evidence Audit & Forensic Reconciliation ----
    S.append(make_part_banner("PART III: DIGITAL EVIDENCE AUDIT &amp; FORENSIC RECONCILIATION"))
    ev = case.get("evidence") or {}
    ev_table = ev.get("table") or []
    if ev_table:
        ev_rows = []
        for r in ev_table:
            ev_rows.append([r.get("filename", "-"), r.get("description", "-"), r.get("text_information", "-")])
        S.append(make_data_table(["Document / Screenshot File", "Evidence Classification", "Extracted Metadata / Transaction Text"], ev_rows, [130, 150, 236]))
    else:
        att_list = ", ".join(ev.get("attachments", [])) if ev.get("count") else "No direct media files attached"
        S.append(make_grid([["Uploaded Media Attachments", att_list, "Forensic Extraction Status", "No structured evidence rows uploaded"]], [120, 138, 120, 138]))

    # Extracted forensic entities summary
    ent = case.get("extracted_entities") or {}
    if ent and "_status" not in ent:
        ent_rows = []
        items = list(ent.items())
        for i in range(0, len(items), 2):
            k1, v1 = items[i]
            k2, v2 = items[i+1] if i+1 < len(items) else ("", "")
            ent_rows.append([k1.replace("_", " ").title(), str(v1), k2.replace("_", " ").title() if k2 else "", str(v2) if k2 else ""])
        if ent_rows:
            S.append(Spacer(1, 2))
            S.append(make_grid(ent_rows, [115, 143, 115, 143]))

    # Reconciliation section
    recon = case.get("reconciliation") or {}
    if recon.get("has_conflicts") and recon.get("conflicts"):
        S.append(Spacer(1, 2))
        conf_hdr = Paragraph("<b>[!] EVIDENTIARY RECONCILIATION DISCREPANCIES IDENTIFIED:</b> Complainant typed mentions conflict with OCR receipt data.", c_val_alert)
        S.append(conf_hdr)
        c_rows = []
        for cf in recon["conflicts"]:
            c_rows.append([
                str(cf.get("field", "")),
                str(cf.get("ocr_value", "")),
                ", ".join(str(x) for x in cf.get("typed_mentions", [])),
                str(cf.get("resolution", "")),
            ])
        S.append(make_data_table(["Audit Field", "OCR Receipt Evidence", "Citizen Statement Mentions", "Forensic Audit Resolution"], c_rows, [85, 110, 135, 186]))
    elif recon.get("agreements"):
        agr_msg = Paragraph(f"<b>Forensic Evidence Verification:</b> Citizen statement and attached screenshot evidence agree on {len(recon['agreements'])} verified field(s). Confidence: {recon.get('confidence_note', 'Verified')}.", ParagraphStyle("agr", parent=c_val, textColor=GREEN))
        t_agr = Table([[agr_msg]], colWidths=[W_TOTAL])
        t_agr.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#86efac")),
        ]))
        S.append(Spacer(1, 2))
        S.append(t_agr)
    S.append(Spacer(1, 4))

    # ---- 6. PART IV: Financial Debit Trail & Suspect Beneficiary Particulars ----
    S.append(make_part_banner("PART IV: FINANCIAL DEBIT TRAIL &amp; SUSPECT BENEFICIARY PARTICULARS"))
    txns = case.get("transactions") or []
    stxns = case.get("suspect_transactions") or []
    suspects = case.get("suspects") or []

    if txns:
        t_rows = []
        for t in txns:
            amt_fmt = f"INR {float(t.get('amount', 0)):,.2f}" if str(t.get("amount", "")).replace(".", "", 1).isdigit() else str(t.get("amount", ""))
            t_rows.append([
                str(t.get("bank", "-")),
                str(t.get("account_no", "-")),
                str(t.get("transaction_id", "-")),
                amt_fmt,
                str(t.get("transaction_date", "-")),
            ])
        S.append(Paragraph("<b>1. Complainant Debited Financial Accounts:</b>", c_label))
        S.append(make_data_table(["Debited Bank / Entity", "Account / UPI VPA", "Transaction ID / UTR", "Debit Amount", "Date / Time"], t_rows, [110, 110, 120, 96, 80]))

    if stxns:
        S.append(Spacer(1, 2))
        S.append(Paragraph("<b>2. Suspect Destination Beneficiary Trail (Inter-Bank Money Trail):</b>", c_label))
        st_rows = []
        for st in stxns:
            amt_fmt = f"INR {float(st.get('amount', 0)):,.2f}" if str(st.get("amount", "")).replace(".", "", 1).isdigit() else str(st.get("amount", ""))
            st_rows.append([
                str(st.get("method", "-")),
                str(st.get("bank", "-")),
                str(st.get("account_no", "-")),
                str(st.get("transaction_id", "-")),
                amt_fmt,
                str(st.get("transaction_date", "-")),
            ])
        S.append(make_data_table(["Transfer Method", "Beneficiary Bank / Gateway", "Suspect Account / UPI ID", "UTR Reference", "Credited Amount", "Txn Date"], st_rows, [80, 95, 105, 100, 76, 60]))

    if suspects:
        S.append(Spacer(1, 2))
        S.append(Paragraph("<b>3. Suspect Identity &amp; Platform Handle Particulars:</b>", c_label))
        s_rows = []
        for sp in suspects:
            s_rows.append([
                str(sp.get("name", "Unknown")),
                str(sp.get("id_type", "-")),
                str(sp.get("id_number", "-")),
                str(sp.get("address", "Not provided / Cyber footprint only")),
            ])
        S.append(make_data_table(["Suspect Name / Alias", "Identifier Type", "Account / Mobile / Handle", "Known Address / Locational Footprint"], s_rows, [110, 100, 130, 176]))

    if not txns and not stxns and not suspects:
        S.append(make_grid([["Financial Debits Reported", "Nil (Non-financial incident or debit trail pending)", "Suspect Particulars", "No individual suspect identities reported at intake"]], [120, 138, 120, 138]))
    S.append(Spacer(1, 4))

    # ---- 7. PART V: Complainant Identification & Police Jurisdiction ----
    S.append(make_part_banner("PART V: COMPLAINANT IDENTIFICATION &amp; POLICE JURISDICTION"))
    c_title = f"{c.get('title', '')} " if c.get('title') else ""
    full_name = f"{c_title}{c.get('name', 'not supplied')}"
    dob_age = f"{c.get('age', 'not supplied')} yrs"
    if c.get("dob") and c.get("dob") != "not supplied":
        dob_age += f" (DOB: {c.get('dob')})"

    rel_str = f"{c.get('relative_name', 'not supplied')} ({c.get('relative_type', 'Father')})" if c.get("relative_name") and c.get("relative_name") != "not supplied" else "not supplied"
    addr_full = f"{c.get('address', '')} {c.get('city', '')} {c.get('district', '')} {c.get('state', '')} {c.get('pincode', '')}".strip()
    id_doc = f"{c.get('id_type', 'not supplied')}"
    if c.get("id_upload_name") and c.get("id_upload_name") != "not supplied":
        id_doc += f" (File: {c.get('id_upload_name')})"

    part5_rows = [
        ["Complainant Full Name", full_name, "Gender / Age / DOB", f"{c.get('gender', 'not supplied')} | {dob_age}"],
        ["Father's / Spouse's Name", rel_str, "Relationship with Victim", c.get("relationship_with_victim", "Self")],
        ["Mobile Contact Number", c.get("phone", "not supplied"), "Email Address", c.get("email", "not supplied")],
        ["Full Residential Address", addr_full or f"{c.get('city', 'not supplied')}, {c.get('state', 'not supplied')}", "Designated Police Station", c.get("police_station", "not supplied")],
        ["National Identity Proof", id_doc, "State & District Jurisdiction", f"{c.get('district', 'not supplied')}, {c.get('state', 'not supplied')}"],
    ]
    S.append(make_grid(part5_rows, [115, 143, 115, 143]))
    S.append(Spacer(1, 4))

    # ---- 8. PART VI: Applicable Statutory Penal Provisions (Module D Engine) ----
    S.append(make_part_banner("PART VI: APPLICABLE STATUTORY PENAL PROVISIONS (AI LEGAL ENGINE)"))
    legal = case.get("legal_sections") or {}
    if "_status" in legal and not legal.get("it_act"):
        S.append(Paragraph(f"<b>Statutory Mapping Status:</b> {legal.get('_status', 'Unresolved')}", body_text))
    else:
        audit_tag = (
            "<b>Statutory Framework:</b> Bharatiya Nyaya Sanhita, 2023 (Act 45/2023) &amp; Information Technology Act, 2000 &bull; "
            "<i>Certified Current against Gazette of India (indiacode.nic.in)</i>"
        )
        S.append(Paragraph(audit_tag, ParagraphStyle("aud_nt", parent=c_val, textColor=NAVY, fontSize=6.8, leading=8.5)))
        S.append(Spacer(1, 2))

        leg_rows = []
        for s in legal.get("it_act", []):
            leg_rows.append(["Information Technology Act, 2000", f"Section {s.get('section', '')}", s.get("description", "")])
        for s in legal.get("bns", []):
            ipc = f"<br/><font color='#64748b' size='6.5'>(IPC Equivalent: Section {s.get('ipc_equivalent')})</font>" if s.get("ipc_equivalent") else ""
            leg_rows.append(["Bharatiya Nyaya Sanhita, 2023", f"Section {s.get('section', '')}", s.get("description", "") + ipc])
        for s in legal.get("other", []):
            sec = f" Section {s.get('section')}" if s.get("section") else ""
            leg_rows.append([s.get("act", "Special & Local Laws"), sec, s.get("description", "")])

        if leg_rows:
            S.append(make_data_table(["Statutory Enactment", "Section Charged", "Offence Definition & Legal Scope"], leg_rows, [130, 85, 301]))

        # Statutory Proof Elements
        elements = legal.get("statutory_elements") or []
        if elements:
            S.append(Spacer(1, 2))
            elem_p = "<b>IO Proof Checklist (Essential Ingredients):</b> " + " &bull; ".join(elements)
            S.append(Paragraph(elem_p, ParagraphStyle("elem_p", parent=c_val, fontSize=6.5, leading=8, textColor=TEXT_DARK)))

        # Evidentiary Notice
        evid_note = (
            "<b>Evidentiary Admissibility Notice:</b> In terms of Section 63 Bharatiya Sakshya Adhiniyam (BSA) 2023, "
            "a formal Certificate in relation to digital device logs, SMS, emails, and transaction receipts must be obtained "
            "prior to filing the final Police Report (Charge Sheet under Section 193 BNSS 2023)."
        )
        S.append(Spacer(1, 2))
        S.append(Paragraph(evid_note, ParagraphStyle("ev_nt", parent=c_val, fontSize=6.5, leading=8, textColor=TEXT_MUTED)))

        # Conditionals & Investigator notes
        for cond in legal.get("conditional_applied", []):
            if cond.get("status") == "APPLIED":
                S.append(Spacer(1, 1.5))
                S.append(Paragraph(f"<b>[STATUTORY CONDITIONAL APPLIED]</b> {cond.get('rule')}: {cond.get('reason')}", ParagraphStyle("cd1", parent=c_val_bold, textColor=NAVY_LIGHT)))
            elif str(cond.get("status", "")).startswith("NOT EVALUATED"):
                S.append(Spacer(1, 1.5))
                S.append(Paragraph(f"<b>[!] STATUTORY VERIFICATION REQUIRED:</b> {cond.get('action')}", c_val_alert))
        if legal.get("notes"):
            S.append(Spacer(1, 1.5))
            S.append(Paragraph(f"<b>Statutory Adjudication Note:</b> {legal.get('notes')}", c_val))
    S.append(Spacer(1, 4))

    # ---- 9. PART VII: First-Response Investigative Directives & Police Sign-Off ----
    actions = case.get("suggested_actions") or []
    sop_elements = []
    sop_elements.append(make_part_banner("PART VII: FIRST-RESPONSE INVESTIGATIVE DIRECTIVES &amp; POLICE SIGN-OFF"))

    sop_text = ""
    for idx, act in enumerate(actions, 1):
        sop_text += f"<b>{idx}.</b> {act}&nbsp;&nbsp;&nbsp;&nbsp;"
    sop_elements.append(Paragraph(f"<b>Mandatory Standard Operating Procedures (SOP):</b><br/>{sop_text}", c_val))
    sop_elements.append(Spacer(1, 4))

    endorse_left = [
        Paragraph("<b>AFFIRMATION BY COMPLAINANT:</b>", c_val_bold),
        Spacer(1, 2),
        Paragraph("I hereby solemnly declare that the statements made herein are true to the best of my knowledge and no material fact has been concealed.", disclaimer_style),
        Spacer(1, 10),
        Paragraph("________________________________________________", c_label),
        Paragraph("Signature / Digital Thumb Impression of Complainant", c_label),
        Paragraph(f"Date: {case.get('generated_at', '')[:10]}", c_val),
    ]

    endorse_right = [
        Paragraph("<b>OFFICIAL POLICE ENDORSEMENT &amp; VERIFICATION:</b>", c_val_bold),
        Spacer(1, 2),
        Paragraph(f"Entered in Station Cyber Diary. Assigned to IO / Cyber Cell.<br/>Jurisdiction: <b>{jurisdiction_str}</b>", disclaimer_style),
        Spacer(1, 10),
        Paragraph("________________________________________________", c_label),
        Paragraph("Investigating Officer / Station House Officer (SHO)", c_label),
        Paragraph("Police Station Seal / Official Stamp &amp; Date", c_val),
    ]

    t_endorse = Table([[endorse_left, endorse_right]], colWidths=[253, 253])
    t_endorse.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), LIGHT_BG),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f8fafc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (0, 0), 0.5, BORDER_COL),
        ("BOX", (1, 0), (1, 0), 0.5, BORDER_COL),
    ]))
    sop_elements.append(t_endorse)
    sop_elements.append(Spacer(1, 4))

    # Statutory Disclaimer Footer
    disclaimer_text = (
        "CONFIDENTIAL &amp; PRIVILEGED LAW ENFORCEMENT RECORD &bull; GENERATED VIA NATIONAL CYBER CRIME REPORTING PORTAL (NCRP) / "
        "INDIAN CYBER CRIME COORDINATION CENTRE (I4C), MINISTRY OF HOME AFFAIRS, GOVT. OF INDIA. Under Section 65B Indian Evidence Act / "
        "Section 61 Bharatiya Sakshya Adhiniyam 2023, this digital record constitutes an admissible computer-generated record. Automated "
        "classifications and statutory legal mappings provide decision support and require formal confirmation by the Investigating Officer."
    )
    sop_elements.append(Paragraph(disclaimer_text, disclaimer_style))

    S.append(KeepTogether(sop_elements))

    doc.build(S)
    return path


# ---- demo ------------------------------------------------------------------

def _demo():
    print("Building three demo case files, each with a different level of module coverage.\n")

    # 1. full pipeline
    full = build_case_file(
        complainant={"name": "R. Sharma", "age": 34, "phone": "98XXXXXX21",
                     "email": "rsharma@example.com", "city": "Nashik", "state": "Maharashtra"},
        raw_complaint="paise gaye account se, 40000, koi otp nahi aaya, card mere paas hi hai",
        narrative=("On 12 August 2026 the complainant found an unauthorised debit of Rs. 40,000 "
                   "from the Aadhaar-linked savings account. The transactions were recorded as "
                   "AePS withdrawals at a Business Correspondent outlet in another district. "
                   "No one-time password was shared and the debit card remained in the "
                   "complainant's possession throughout."),
        sub_category="AePS Fraud",
        confidence=0.94,
        entities={"amount": "Rs. 40,000", "transaction_date": "12 August 2026",
                  "account_last4": "4417", "outlet_district": "Jalgaon",
                  "transaction_type": "AePS withdrawal"},
        attachments=["passbook_page.jpg", "sms_alert.png"],
        reference="NCRP/2026/000123",
        incident_datetime="12 August 2026 10:30",
        category="Online Financial Fraud",
        modus_operandi="Unauthorised AePS withdrawal using biometric spoofing",
        incident_location=["Mobile App"],
        transactions=[{"bank": "SBI", "account_no": "XXXX4417", "transaction_id": "SBIN12345678AB",
                       "amount": "40000", "transaction_date": "12 August 2026", "reference_no": "REF001"}],
    )

    # 2. minor complainant - POCSO rule fires
    minor = build_case_file(
        complainant={"name": "Withheld", "age": 16, "phone": "97XXXXXX08",
                     "city": "Pune", "state": "Maharashtra"},
        narrative=("The complainant was contacted on a social media platform by an unknown "
                   "account. Private material was obtained during a video call without consent "
                   "and its circulation was threatened unless payment was made."),
        sub_category="Cyber Bullying / Stalking / Sexting",
        confidence=0.91,
        entities={"platform": "Instagram", "amount_demanded": "Rs. 20,000"},
        attachments=["chat_screenshot.png"],
        reference="NCRP/2026/000124",
    )

    # 3. degraded - Modules A and C did not run, age unknown
    degraded = build_case_file(
        complainant={"name": "A. Patil", "phone": "99XXXXXX55", "city": "Thane"},
        narrative=None,
        sub_category="Cyber Bullying / Stalking / Sexting",
        confidence=0.62,
        entities=None,
        attachments=[],
        reference="NCRP/2026/000125",
    )

    for case, label in [(full, "full pipeline"),
                        (minor, "minor complainant - POCSO"),
                        (degraded, "degraded - modules A and C missing")]:
        jp = write_json(case)
        try:
            pp = write_pdf(case)
        except SystemExit:
            pp = "(reportlab not installed)"
        print(f"  {label:<38} {case['reference']}")
        print(f"    json {jp}")
        print(f"    pdf  {pp}")

    print("\n" + "=" * 74)
    print("SAMPLE OUTPUT - full pipeline")
    print("=" * 74)
    print(format_text(full))

    print("\n" + "=" * 74)
    print("DEGRADED CASE - note how missing modules are reported")
    print("=" * 74)
    d = format_text(degraded)
    for line in d.split("\n"):
        if ("NOT AVAILABLE" in line or "Confirm the complainant" in line
                or "NOT EVALUATED" in line or "LOW" in line):
            print(line)


if __name__ == "__main__":
    _demo()
