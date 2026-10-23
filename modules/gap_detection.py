"""
MODULE — Gap Detection

Analyses a raw complaint (typed text) and OCR-extracted entities together,
determines what category of crime is being described, and returns the specific
fields that are still missing — with plain-language, multilingual questions.

WHY THIS EXISTS
    A citizen writes "paise gaye" — money gone.
    OCR reads the screenshot: PhonePe, ₹40,000, 12 Aug 2026.
    Together they still don't say: which bank account? Was an OTP requested?
    
    Gap detection finds exactly what's still missing and asks only for that.
    It does NOT ask for things the system can already read from the text or images.
    It caps at 3 questions per category so the citizen is not interrogated.

DESIGN DECISIONS
    - Deterministic keyword matching, no LLM. This runs before Module A, so
      speed matters and the system should not depend on Ollama being available.
    - Category is inferred from keywords in the raw text + OCR entities together.
      This is a rough hint, not a full classification. Module B does the real
      classification after Module A has standardised the narrative.
    - Each gap check is an independent function. Easy to test, easy to extend.
    - A gap is only reported if the answer is genuinely absent from BOTH the
      typed text AND the OCR entities. If either source has the value, no question
      is asked for it.
    - Multi-lingual question generation: detects whether input is Marathi, Hindi,
      or English and returns localized clarifying questions.

USAGE
    from modules.gap_detection import detect_gaps

    result = detect_gaps(
        raw_text="paise gaye account se, koi otp nahi diya",
        ocr_entities={"amount": "40000", "platform": "PhonePe"},
    )
    result["category_hint"]    # "financial_upi"
    result["questions"]        # [{"field": "date", "question": "..."}, ...]
    result["critical"]         # fields missing that matter most for this case

    python modules/gap_detection.py               # demo over 6 sample complaints
    python modules/gap_detection.py --check       # self-test
"""

import re
import sys
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Category hints — keyword groups that signal the kind of complaint.
# These map to field requirement profiles below.
# Checked in ORDER — first match wins. Put more specific patterns earlier.
# ---------------------------------------------------------------------------

CATEGORY_HINTS = [
    # --- financial ---
    ("financial_upi",   [
        r"\bupi\b", r"collect request", r"qr code", r"scan.*receive",
        r"phonepe", r"google pay", r"gpay", r"paytm", r"bhim",
        r"\bvpa\b", r"@[a-z]{2,15}\b",
    ]),
    ("financial_banking", [
        r"net banking", r"internet banking", r"online banking",
        r"beneficiary", r"\bapk\b", r"login.*bank", r"bank.*login",
        r"otp.*bank", r"bank.*otp", r"neft", r"rtgs", r"imps",
    ]),
    ("financial_card",  [
        r"debit card", r"credit card", r"card.*block", r"card.*stolen",
        r"cvv", r"card number", r"\bsim swap\b", r"duplicate sim",
        r"network.*gone", r"signal.*loss",
    ]),
    ("financial_aeps",  [
        r"\baeps\b", r"thumb impression", r"fingerprint.*withdraw",
        r"biometric", r"micro.?atm", r"aadhaar.*money", r"money.*aadhaar",
    ]),
    ("financial_invest",[
        r"trading.*platform", r"fake.*trading", r"investment.*return",
        r"demat", r"\bipo\b", r"portfolio.*profit", r"withdraw.*profit",
        r"unlock.*fee", r"tax.*release", r"telegram.*invest",
    ]),
    ("financial_job",   [
        r"job.*fee", r"registration fee", r"training fee",
        r"part.?time", r"work from home", r"task.*earn",
        r"hr.*call", r"offer letter.*pay", r"pay.*job", r"naukri",
    ]),
    ("financial_wallet",[
        r"wallet", r"kyc.*expire", r"screen.*share",
        r"remote.*access", r"anydesk", r"teamviewer",
    ]),
    # --- account takeover ---
    ("account",         [
        r"account.*hack", r"hack.*account", r"someone.*log",
        r"log.*someone", r"password.*change", r"profile.*hack",
        r"email.*hack", r"gmail.*hack", r"instagram.*hack",
    ]),
    # --- harassment / content ---
    ("harassment",      [
        r"message.*threat", r"threat.*message", r"blackmail",
        r"morphed.*photo", r"fake.*profile", r"fake.*id",
        r"stalk", r"bother.*online", r"online.*bother",
        r"video.*viral", r"photo.*viral", r"sexting",
    ]),
    # --- hacking / technical ---
    ("hacking",         [
        r"website.*hack", r"server.*attack", r"ransomware",
        r"data.*breach", r"data.*leak", r"defaced",
    ]),
]


def _hint(raw_text, ocr_entities):
    """Return the best-matching category hint string."""
    combined = (raw_text or "").lower()
    if ocr_entities:
        combined += " " + " ".join(str(v) for v in ocr_entities.values()).lower()

    for hint, patterns in CATEGORY_HINTS:
        for pat in patterns:
            if re.search(pat, combined, re.I):
                return hint
    if any(w in combined for w in ("paise", "kat", "debit", "rupee", "rs", "₹", "पैसे", "रुपये", "कापले")):
        return "financial_upi"
    return "general"

detect_category_group = _hint
CATEGORY_GROUP_MAP = dict(CATEGORY_HINTS)


def detect_language(text: str) -> str:
    """Detects primary language script (Devanagari/Marathi/Hindi vs English)."""
    if not text:
        return "en"
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
    total_alpha = len(re.findall(r"[a-zA-Z\u0900-\u097F]", text))
    if total_alpha > 0 and (devanagari_chars / total_alpha) > 0.3:
        marathi_markers = ["आहे", "गेले", "नाही", "झाले", "केले", "पाहिजे", "वरून", "पैसे", "कळवा", "सांगितले"]
        if any(w in text for w in marathi_markers):
            return "mr"
        return "hi"
    return "en"


# ---------------------------------------------------------------------------
# Field checkers — each returns None if the field is present, or a string
# describing what is missing (used internally to build the question).
# Each checker looks at BOTH raw_text and ocr_entities before flagging absent.
# ---------------------------------------------------------------------------

def _has_amount(text, ents):
    if ents and any("amount" in k for k in ents):
        return None
    if re.search(r"(?:₹|rs\.?|inr|rupee|रुपये|रु\.?)\s?[\d,]+", text, re.I):
        return None
    if re.search(r"\b\d{3,}(?:,\d{3})*\b", text):
        return None
    return "amount"


def _has_date(text, ents):
    if ents and "date" in ents:
        return None
    months = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    if re.search(rf"\d{{1,2}}[/-]{months}[/-]?\d{{0,4}}", text, re.I):
        return None
    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text):
        return None
    if re.search(r"\b(today|yesterday|last\s+\w+|aaj|kal|काल|आज|संध्याकाळी)\b", text, re.I):
        return None
    if re.search(r"\b(20\d{2})\b", text):
        return None
    return "date"


def _has_platform(text, ents):
    if ents and "platform" in ents:
        return None
    platforms = (r"phonepe|google pay|gpay|paytm|bhim|amazon pay|mobikwik"
                 r"|whatsapp|telegram|instagram|facebook|naukri|linkedin"
                 r"|sbi|hdfc|icici|axis|kotak|pnb|upi|net banking"
                 r"|email|gmail|portal|website|app")
    if re.search(platforms, text, re.I):
        return None
    return "platform"


def _has_account_or_upi(text, ents):
    if ents and any(k in ents for k in ("upi_id", "account_last4", "card_last4")):
        return None
    if re.search(r"[\w.\-]{2,30}@[a-zA-Z]{2,15}", text):   # UPI ID
        return None
    if re.search(r"\b(?:a/c|account|acct?)[\s.]*(?:no\.?|number)?[\s.]*[\dX*]{4,}", text, re.I):
        return None
    return "account_or_upi"

_has_upi_or_account = _has_account_or_upi


def _has_transaction_ref(text, ents):
    if ents and "transaction_ref" in ents:
        return None
    if re.search(r"\b(?:utr|rrn|txn|ref(?:erence)?|transaction)[\s:#-]*[A-Z0-9]{6,}", text, re.I):
        return None
    return "transaction_ref"


def _has_bank(text, ents):
    banks = r"sbi|hdfc|icici|axis|kotak|pnb|canara|bob|baroda|union|yes bank|idfc|indusind"
    if re.search(banks, text, re.I):
        return None
    if re.search(r"\bbank\b", text, re.I):
        return None
    return "bank_name"


def _has_otp_context(text, ents):
    """Check if the complaint says anything about OTP (shared or not shared)."""
    if re.search(r"\botp\b|\bone.?time.?pass", text, re.I):
        return None
    return "otp_context"


def _has_suspect(text, ents):
    if re.search(r"\b(?:phone|mobile|contact|number)\s*:?\s*[6-9]\d{9}", text):
        return None
    if re.search(r"\b[6-9]\d{9}\b", text):
        return None
    if ents and any(k in ents for k in ("phone", "upi_id", "email")):
        return None
    if re.search(r"[\w.\-]{2,30}@[a-zA-Z]{2,15}", text):   # UPI ID or email
        return None
    if re.search(r"(?:whatsapp|telegram|instagram|email|profile|handle|username)\s*(?:id|link|handle|number)?\s*[:=]\s*\S+", text, re.I):
        return None
    if re.search(r"@(?!ok|ybl|paytm|axis|icici|hdfc|sbi)[\w.]{3,30}", text):  # social handle like @badguy
        return None
    return "suspect_contact"


def _has_incident_location(text, ents):
    locations = r"whatsapp|telegram|instagram|facebook|email|website|portal|app|sms|call"
    if re.search(locations, text, re.I):
        return None
    return "incident_location"


def _has_when_started(text, ents):
    if re.search(r"(since|from|start|begin|first|ago|past|last)\b", text, re.I):
        return None
    return "when_started"


def _has_accessed_what(text, ents):
    if re.search(r"(email|instagram|facebook|account|profile|server|database|website)", text, re.I):
        return None
    return "what_was_accessed"

_has_what_was_accessed = _has_accessed_what


def _has_data_affected(text, ents):
    if re.search(r"(data|record|file|information|detail|customer|user)", text, re.I):
        return None
    return "what_data_affected"

_has_what_data_affected = _has_data_affected


# ---------------------------------------------------------------------------
# Field definitions — question and priority for each field key
# priority: 1 = critical (show always), 2 = important, 3 = helpful
# ---------------------------------------------------------------------------

FIELD_META = {
    "amount": {
        "question_en": "How much money was involved? (e.g. ₹40,000)",
        "question_hi": "कुल कितनी राशि कटी या ट्रांसफर हुई? (जैसे ₹40,000)",
        "question_mr": "एकूण किती रक्कम कापली गेली किंवा ट्रान्सफर झाली? (उदा. ₹40,000)",
        "priority": 1,
    },
    "date": {
        "question_en": "On what date did this happen? (e.g. 12 August 2026)",
        "question_hi": "यह घटना किस तारीख को हुई? (जैसे 12 अगस्त 2026)",
        "question_mr": "ही घटना कोणत्या तारखेला घडली? (उदा. १२ ऑगस्ट २०२६)",
        "priority": 1,
    },
    "platform": {
        "question_en": "Which app, website, or platform was involved? (e.g. PhonePe, WhatsApp, a job portal)",
        "question_hi": "कौन सा ऐप, वेबसाइट या प्लेटफॉर्म शामिल था? (जैसे PhonePe, WhatsApp, जॉब पोर्टल)",
        "question_mr": "कोणते अ‍ॅप, वेबसाईट किंवा प्लॅटफॉर्म वापरले गेले होते? (उदा. PhonePe, WhatsApp, जॉब पोर्टल)",
        "priority": 1,
    },
    "bank_name": {
        "question_en": "Which bank or payment service was your money debited from?",
        "question_hi": "पैसे किस बैंक या पेमेंट सर्विस से कटे हैं?",
        "question_mr": "पैसे कोणत्या बँकेतून किंवा पेमेंट सेवेतून कापले गेले आहेत?",
        "priority": 1,
    },
    "account_or_upi": {
        "question_en": "What is the UPI ID or account number that was used? (last 4 digits is fine)",
        "question_hi": "इस्तेमाल किया गया UPI ID या बैंक खाता नंबर (अंतिम 4 अंक) क्या है?",
        "question_mr": "वापरलेला UPI ID किंवा बँक खाते क्रमांक (शेवटचे ४ अंक) काय आहे?",
        "priority": 2,
    },
    "transaction_ref": {
        "question_en": "Do you have a transaction reference number? (UTR or RRN from your bank or app)",
        "question_hi": "क्या आपके पास 12-अंकीय UTR या ट्रांजैक्शन रेफरेंस नंबर है?",
        "question_mr": "तुमच्याकडे १२-अंकी UTR किंवा Transaction Reference क्रमांक आहे का?",
        "priority": 2,
    },
    "otp_context": {
        "question_en": "Were you asked to share a one-time password (OTP), or did you share one?",
        "question_hi": "क्या आपसे OTP मांगा गया था या आपने OTP शेयर किया था?",
        "question_mr": "तुमच्याकडून OTP मागितला गेला होता का किंवा तुम्ही OTP शेअर केला होता का?",
        "priority": 2,
    },
    "suspect_contact": {
        "question_en": "Do you have any contact detail for the person who did this? (phone number, email, social media profile)",
        "question_hi": "क्या आपके पास संशयित का फोन नंबर, ईमेल या सोशल मीडिया प्रोफाइल लिंक है?",
        "question_mr": "तुमच्याकडे संशयिताचा फोन नंबर, ईमेल किंवा सोशल मीडिया प्रोफाइल लिंक आहे का?",
        "priority": 2,
    },
    "incident_location": {
        "question_en": "Where did this happen? (e.g. received a WhatsApp message, clicked a link in an email, got a call)",
        "question_hi": "यह कहां हुआ? (जैसे WhatsApp मैसेज, ईमेल लिंक, फोन कॉल)",
        "question_mr": "हे कुठे घडले? (उदा. WhatsApp मेसेज, ईमेल लिंक, फोन कॉल)",
        "priority": 1,
    },
    "when_started": {
        "question_en": "When did this start, and is it still happening?",
        "question_hi": "यह कब शुरू हुआ और क्या यह अभी भी जारी है?",
        "question_mr": "हे कधी सुरू झाले आणि अजूनही सुरू आहे का?",
        "priority": 2,
    },
    "what_was_accessed": {
        "question_en": "Which of your accounts or devices was accessed? (e.g. Gmail, Instagram, a company server)",
        "question_hi": "आपका कौन सा अकाउंट या डिवाइस हैक हुआ? (जैसे Gmail, Instagram, सर्वर)",
        "question_mr": "तुमचे कोणते खाते किंवा डिव्हाइस अ‍ॅक्सेस झाले? (उदा. Gmail, Instagram, सर्व्हर)",
        "priority": 1,
    },
    "what_data_affected": {
        "question_en": "What information was exposed or taken? (e.g. customer records, personal files)",
        "question_hi": "क्या जानकारी या डेटा प्रभावित हुआ? (जैसे व्यक्तिगत फोटो, रिकॉर्ड)",
        "question_mr": "कोणती माहिती किंवा डेटा प्रभावित झाला? (उदा. खाजगी फोटो, डेटा)",
        "priority": 2,
    },
}


# ---------------------------------------------------------------------------
# Category profiles — which checks to run and in what order for each hint
# ---------------------------------------------------------------------------

PROFILES = {
    "financial_upi": [
        _has_amount, _has_date, _has_platform,
        _has_transaction_ref,
    ],
    "financial_banking": [
        _has_amount, _has_date, _has_bank,
        _has_account_or_upi, _has_transaction_ref, _has_otp_context,
    ],
    "financial_card": [
        _has_amount, _has_date, _has_bank,
        _has_account_or_upi, _has_otp_context,
    ],
    "financial_aeps": [
        _has_amount, _has_date, _has_bank,
        _has_account_or_upi, _has_transaction_ref,
    ],
    "financial_invest": [
        _has_amount, _has_date, _has_platform,
        _has_transaction_ref, _has_suspect,
    ],
    "financial_job": [
        _has_amount, _has_date, _has_platform,
        _has_suspect, _has_transaction_ref,
    ],
    "financial_wallet": [
        _has_amount, _has_date, _has_platform,
        _has_transaction_ref, _has_otp_context,
    ],
    "account": [
        _has_date, _has_what_was_accessed,
        _has_incident_location, _has_suspect,
    ],
    "harassment": [
        _has_date, _has_incident_location,
        _has_when_started, _has_suspect,
    ],
    "hacking": [
        _has_date, _has_what_was_accessed,
        _has_data_affected, _has_suspect,
    ],
    "general": [
        _has_date, _has_platform,
        _has_amount, _has_incident_location,
    ],
}

GAP_CHECKLISTS = PROFILES
MAX_QUESTIONS = 3   # never interrogate the citizen more than this


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_gaps(raw_text: str, ocr_entities: Optional[Dict] = None, sub_category: Optional[str] = None, lang: Optional[str] = None, entities: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Analyse a raw complaint and OCR entities together.
    Returns what is missing and what to ask.

    raw_text     : str  — complaint as typed by the citizen
    ocr_entities : dict — output of modules.ocr_extract, or None
    entities     : dict — alias for ocr_entities
    """
    text = (raw_text or "").strip()
    ents = ocr_entities or entities or {}
    hint = _hint(text, ents)
    language = lang or detect_language(text)
    checks = PROFILES.get(hint, PROFILES["general"])

    # Extract regex entities from raw text for downstream modules
    try:
        from modules.ocr_extract import extract_entities as parse_regex_entities
    except ImportError:
        from ocr_extract import extract_entities as parse_regex_entities
    text_ents = parse_regex_entities(text)

    combined_ents = dict(ents)
    for k, v in text_ents.items():
        if k not in combined_ents:
            combined_ents[k] = v[0]["value"] if len(v) == 1 else [i["value"] for i in v]

    extracted_fields = {
        "amount": combined_ents.get("amount") or "",
        "transaction_ref": combined_ents.get("transaction_ref") or "",
        "upi_id": combined_ents.get("upi_id") or "",
        "phone": combined_ents.get("phone") or "",
        "email": combined_ents.get("email") or "",
        "account_last4": combined_ents.get("account_last4") or "",
        "card_last4": combined_ents.get("card_last4") or "",
        "date": combined_ents.get("date") or "",
        "time": combined_ents.get("time") or "",
        "platform": combined_ents.get("platform") or "",
    }
    for k, v in list(extracted_fields.items()):
        extracted_fields[k] = ", ".join(str(item) for item in v) if isinstance(v, list) else (str(v) if v else "")

    gaps = []
    for check_fn in checks:
        missing = check_fn(text, ents)
        if missing and missing in FIELD_META:
            meta = FIELD_META[missing]
            q_key = f"question_{language}" if f"question_{language}" in meta else "question_en"
            gaps.append({
                "field":    missing,
                "question": meta.get(q_key, meta["question_en"]),
                "priority": meta["priority"],
            })

    gaps.sort(key=lambda g: g["priority"])
    asked = gaps[:MAX_QUESTIONS]
    critical = [g["field"] for g in asked if g["priority"] == 1]

    total_checks = len(checks)
    missing_count = len(gaps)
    score = float(max(0.0, (total_checks - missing_count) / total_checks)) if total_checks else 1.0

    return {
        "category_hint":      hint,
        "language":           language,
        "questions":          asked,
        "critical":           critical,
        "all_gaps":           [g["field"] for g in gaps],
        "has_gaps":           bool(asked),
        "is_thin":            bool(len(critical) >= 1 or score < 0.75),
        "completeness_score": round(score, 2),
        "extracted_fields":   extracted_fields,
        "missing_critical_info": [{"field": g["field"], "priority": "CRITICAL" if g["priority"] == 1 else "HIGH", "hint": g["question"]} for g in asked],
        "group":              f"_{hint.split('_')[0]}",
    }


def format_for_display(result: Dict[str, Any]) -> str:
    """
    Render the gap-detection result as a short string suitable for the
    dashboard or the terminal.
    """
    if not result.get("has_gaps"):
        return "No missing information detected. Proceeding to analysis."

    lines = [f"[{result['category_hint']}] The following information appears to be missing:\n"]
    for i, q in enumerate(result["questions"], 1):
        tag = " *" if q["priority"] == 1 else ""
        lines.append(f"  {i}. {q['question']}{tag}")
    if result.get("critical"):
        lines.append("\n  (* Required for an accurate classification)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo and self-test
# ---------------------------------------------------------------------------

DEMO_CASES = [
    {
        "label": "Very thin complaint — money gone",
        "raw": "paise gaye",
        "ocr": {},
    },
    {
        "label": "Partial — amount from OCR, nothing else",
        "raw": "paise nikal gaye account se",
        "ocr": {"amount": "40000", "platform": "PhonePe"},
    },
    {
        "label": "UPI fraud — most info in OCR",
        "raw": "refund ke liye qr scan kiya aur paise chale gaye",
        "ocr": {"amount": "15000", "upi_id": "fraud99@ybl",
                "transaction_ref": "428391756201", "date": "12 Aug 2026",
                "platform": "PhonePe"},
    },
    {
        "label": "Job fraud — needs platform and suspect",
        "raw": "i applied for job online, someone called as hr and asked 5000 registration fee, i paid",
        "ocr": {},
    },
    {
        "label": "Account takeover — complete enough",
        "raw": "my instagram account was hacked on 14 august 2026, password changed, "
               "messages sent to my contacts asking for money",
        "ocr": {},
    },
    {
        "label": "Harassment — needs date and platform",
        "raw": "someone is sending threatening messages and blackmailing me with my photos",
        "ocr": {},
    },
]


def _selftest():
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("GAP DETECTION SELF-TEST\n" + "=" * 64)
    tests = [
        # (raw, ocr, expected_gaps_subset, should_have_gaps)
        ("paise gaye", {}, ["amount", "date"], True),
        ("₹40,000 taken from PhonePe on 12 August 2026 via UTR 4283917", {},
         [], False),
        ("job fraud, registration fee paid", {},
         ["date", "platform", "transaction_ref"], True),
        ("instagram hack", {}, ["date"], True),
        ("paise nikal gaye", {"amount": "40000", "platform": "PhonePe",
                               "date": "12 Aug 2026", "transaction_ref": "12345678"},
         [], False),
    ]
    passed = 0
    for raw, ocr, expected, should_have in tests:
        r = detect_gaps(raw, ocr)
        found_gaps = r["all_gaps"]
        gaps_ok = all(e in found_gaps for e in expected)
        has_ok = (r["has_gaps"] == should_have)
        ok = gaps_ok and has_ok
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] '{raw[:50]}'")
        if not ok:
            print(f"         expected gaps {expected}, has_gaps={should_have}")
            print(f"         got      gaps {found_gaps}, has_gaps={r['has_gaps']}")
    print(f"\n{passed}/{len(tests)} self-test cases passed")


def _demo():
    import sys
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("GAP DETECTION DEMO\n" + "=" * 64)
    for c in DEMO_CASES:
        r = detect_gaps(c["raw"], c.get("ocr", {}))
        print(f"\n--- {c['label']}")
        print(f"  raw : {c['raw'][:70]}")
        if c.get("ocr"):
            print(f"  ocr : {c['ocr']}")
        print(format_for_display(r))


if __name__ == "__main__":
    if "--check" in sys.argv:
        _selftest()
    else:
        _demo()
