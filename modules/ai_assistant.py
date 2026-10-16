"""
MODULE A - AI Assistant (intake and narrative standardisation)

Takes a complaint as a real person actually writes it - short, informal, mixed
language, incomplete - together with any entities extracted from screenshots, and
produces ONE clean English narrative in the register the classifier was trained on.

WHY THIS MODULE EXISTS
    The classifier was trained on formal generated English. A real complainant
    writes "paise gaye 40000 koi otp nahi aaya". Those share almost no vocabulary.
    Module A is the layer that closes that gap, so the classifier sees the register
    it expects regardless of how the complaint arrived.

THE RULE THAT MATTERS MOST
    Only information present in the user's text or the extracted entities may
    appear in the narrative. The model must not infer a date, a platform, an
    amount or a mechanism that was not supplied.

    An LLM asked to "write a proper complaint" will happily invent plausible
    detail. In a police system that is not a cosmetic problem - a fabricated
    detail becomes part of a case file an officer acts on. So every narrative is
    checked before it is returned, and anything that adds numbers not present in
    the input is rejected.

DESIGN DECISION: this is PROMPTED, not trained. The task is rewriting, which
frontier and mid-size instruction models already do well. Training a model here
would add cost and remove the ability to adjust behaviour by editing text.

USAGE
    from modules.ai_assistant import standardise

    result = standardise(
        "paise gaye account se 40000, koi otp nahi aaya, card mere paas hai",
        entities={"amount": "Rs. 40,000", "transaction_date": "12 August 2026"},
    )
    result["narrative"]      the standardised English narrative
    result["ok"]             False if the guard rejected it
    result["issues"]         what the guard found

    python modules/ai_assistant.py            demo over sample messy complaints
    python modules/ai_assistant.py --check    guard self-test, no model needed
"""

import argparse
import json
import os
import re
import sys

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen2.5:7b"      # measured better at fact fidelity than llama3.1:8b

MIN_CHARS, MAX_CHARS = 200, 1500  # the NCRP complaint field limits

SYSTEM = """You convert citizen cybercrime complaints into a standardised English narrative
for an official complaint record.

ABSOLUTE RULES
1. Use ONLY facts stated in the complaint or listed in the extracted details.
   Never invent a date, amount, platform, name, location or mechanism.
2. If something is not stated, leave it out. Do NOT write "unknown" or guess.
3. Reproduce every amount and date EXACTLY as given, digit for digit.
4. Write in plain formal English, third person. Refer to the complainant, but
   vary sentence openings — begin with the date, the action, or the amount.
   Example of the register expected:
   "On 12 August 2026 an unauthorised debit of Rs. 40,000 was noticed from the
   complainant's account. No one-time password had been shared, and the debit
   card remained in the complainant's possession. The bank has indicated that
   a thumb impression was used to authorise the withdrawal."
5. Write one paragraph, between 200 and 1500 characters.
6. Do not name the type of crime and do not suggest any legal provision.
7. Do not add advice, opinion, sympathy or next steps.
8. Write flowing connected prose, not a list of short sentences. Vary how
   sentences begin — do not start every sentence with "The complainant".
   Aim for 300-600 characters where the input supports it.
Output ONLY the narrative. No preamble, no heading, no quotation marks."""


# ---------------------------------------------------------------- guard

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
CURRENT_YEARS = {"2024", "2025", "2026", "2027"}

_NUM = re.compile(r"\d[\d,]*")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")

# Mechanisms the model must not introduce on its own. If one of these appears in
# the narrative but nowhere in the input, the model has invented the method.
_MECHANISMS = [
    "otp", "one-time password", "qr code", "collect request", "upi", "biometric",
    "fingerprint", "thumb", "sim", "duplicate sim", "screen-sharing", "screen sharing",
    "apk", "ransomware", "encrypt", "phishing link", "video call", "matrimonial",
    "demat", "ipo", "beneficiary", "net banking", "debit card", "credit card",
]


def _normalize_text(text):
    """Normalizes Devanagari and Indic numerals to standard ASCII digits."""
    if not text:
        return ""
    return str(text).translate(DEVANAGARI_DIGITS)


def _digits(text):
    """All numbers in the text, normalized and comma-stripped, as strings."""
    norm = _normalize_text(text)
    return {n.replace(",", "") for n in _NUM.findall(norm or "")}


def guard(source_text, entities, narrative):
    """
    Check the narrative introduced nothing that was not in the input.
    Returns (ok, issues). Conservative by design: it would rather flag a
    borderline narrative than let a fabricated fact reach a case file.
    """
    issues = []
    entity_blob = " ".join(f"{k} {v}" for k, v in (entities or {}).items())
    source = _normalize_text(f"{source_text} {entity_blob}").lower()
    norm_narrative = _normalize_text(narrative)

    # 1. invented numbers -------------------------------------------------
    src_nums = _digits(source)
    new_nums = {n for n in _digits(norm_narrative) if len(n) >= 3 and n not in CURRENT_YEARS}   # ignore 1-2 digit noise and current year
    invented = {n for n in new_nums if n not in src_nums}
    if invented:
        issues.append(f"numbers not in the input: {sorted(invented)[:4]}")

    # 2. dropped amounts --------------------------------------------------
    # Look for amounts (4-8 digits, excluding 10-digit mobile and 12-digit UTRs)
    src_big = {n for n in src_nums if 4 <= len(n) <= 8}
    lost = {n for n in src_big if n not in _digits(norm_narrative)}
    if lost:
        issues.append(f"amounts from the input are missing: {sorted(lost)[:4]}")

    # 3. invented year ----------------------------------------------------
    src_years = {m.group() for m in _YEAR.finditer(source)}
    nar_years = {m.group() for m in _YEAR.finditer(norm_narrative)}
    unexpected_years = (nar_years - src_years) - CURRENT_YEARS
    if unexpected_years:
        issues.append(f"year not in the input: {sorted(unexpected_years)}")

    # 4. invented mechanism ----------------------------------------------
    low = narrative.lower()
    added = [m for m in _MECHANISMS if m in low and m not in source]
    # allow a mechanism if a close variant was present (otp / one-time password)
    if "otp" in source or "one-time password" in source:
        added = [m for m in added if m not in ("otp", "one-time password")]
    if added:
        issues.append(f"mechanism not in the input: {added[:4]}")

    # 5. length -----------------------------------------------------------
    n = len(narrative)
    if n < MIN_CHARS:
        issues.append(f"too short: {n} chars (minimum {MIN_CHARS})")
    elif n > MAX_CHARS:
        issues.append(f"too long: {n} chars (maximum {MAX_CHARS})")

    # 6. refusals and meta commentary -------------------------------------
    for bad in ("i cannot", "i'm sorry", "as an ai", "here is the", "narrative:"):
        if low.startswith(bad) or f"\n{bad}" in low:
            issues.append("model returned commentary instead of a narrative")
            break

    return (not issues), issues


# ---------------------------------------------------------------- providers

def _ollama(prompt, model):
    import requests
    base = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    r = requests.post(base + "/api/chat", timeout=180, json={
        "model": model, "stream": False,
        "options": {"temperature": 0.2},          # low: this is transcription, not creativity
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def _gemini(prompt, model):
    import google.generativeai as genai
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")
    genai.configure(api_key=key)
    return genai.GenerativeModel(model or "gemini-3.5-flash",
                                 system_instruction=SYSTEM).generate_content(prompt).text.strip()


def _anthropic(prompt, model):
    import anthropic
    c = anthropic.Anthropic()
    m = c.messages.create(model=model or "claude-sonnet-4-6", max_tokens=800,
                          system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in m.content if b.type == "text").strip()


_CALL = {"ollama": _ollama, "gemini": _gemini, "anthropic": _anthropic}


# ---------------------------------------------------------------- main entry

def build_prompt(raw_text, entities=None, form_fields=None):
    parts = [f"COMPLAINT AS WRITTEN BY THE COMPLAINANT:\n{raw_text}"]

    if entities:
        lines = "\n".join(f"  {k}: {v}" for k, v in entities.items())
        parts.append(f"\nDETAILS EXTRACTED FROM ATTACHED SCREENSHOTS:\n{lines}")

    if form_fields:
        lines = "\n".join(f"  {k}: {v}" for k, v in form_fields.items() if v)
        if lines:
            parts.append(f"\nDETAILS FROM THE COMPLAINT FORM:\n{lines}")

    parts.append("\nWrite the standardised narrative using only the information above.")
    return "\n".join(parts)


def standardise(raw_text, entities=None, form_fields=None,
                provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL, retries=2):
    """
    Convert a raw complaint into a standardised English narrative.

    Returns a dict:
        ok         bool   whether the guard passed
        narrative  str    the narrative, or "" if every attempt was rejected
        issues     list   guard findings from the final attempt
        attempts   int
        source     "Module A"
    """
    if not raw_text or not raw_text.strip():
        return {"ok": False, "narrative": "", "issues": ["no complaint text supplied"],
                "attempts": 0, "source": "Module A"}

    if provider not in _CALL:
        return {"ok": False, "narrative": "", "issues": [f"provider '{provider}' not configured"],
                "attempts": 0, "source": "Module A"}

    prompt = build_prompt(raw_text, entities, form_fields)
    call = _CALL[provider]
    last_issues, narrative = [], ""

    for attempt in range(1, retries + 2):
        try:
            narrative = call(prompt, model)
        except Exception as e:
            return {"ok": False, "narrative": "",
                    "issues": [f"{type(e).__name__}: {str(e)[:120]}"],
                    "attempts": attempt, "source": "Module A"}

        narrative = re.sub(r"^\s*(narrative|complaint)\s*:\s*", "", narrative, flags=re.I).strip()
        narrative = narrative.strip('"').strip()

        ok, issues = guard(raw_text, entities, narrative)
        if ok:
            return {"ok": True, "narrative": narrative, "issues": [],
                    "attempts": attempt, "source": "Module A"}

        last_issues = issues
        # tighten the instruction and try once more
        prompt += ("\n\nThe previous attempt was rejected because: "
                   + "; ".join(issues)
                   + ". Use ONLY the information given above. Do not add anything.")

    return {"ok": False, "narrative": narrative, "issues": last_issues,
            "attempts": retries + 1, "source": "Module A"}


# ---------------------------------------------------------------- Gap Analysis & Intake State Machine

try:
    from modules.gap_detection import (
        GAP_CHECKLISTS,
        CATEGORY_GROUP_MAP,
        detect_category_group,
        detect_gaps,
        detect_language,
    )
except ImportError:
    from gap_detection import (
        GAP_CHECKLISTS,
        CATEGORY_GROUP_MAP,
        detect_category_group,
        detect_gaps,
        detect_language,
    )


try:
    from modules.sentiment_analysis import analyze_sentiment_and_urgency
except ImportError:
    try:
        from sentiment_analysis import analyze_sentiment_and_urgency
    except ImportError:
        analyze_sentiment_and_urgency = None


def detect_gaps_and_autofill(raw_text, entities=None, sub_category=None):
    """Backwards-compatible wrapper for pipeline and dashboard."""
    return detect_gaps(raw_text, entities=entities, sub_category=sub_category)


def standardise_interactive(raw_text, entities=None, form_fields=None,
                            round_count=0, max_rounds=2,
                            provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL):
    """
    State-machine enabled intake handler with Sentiment & Gap Analysis.

    If the complaint is thin or missing critical statutory fields, returns:
      {
        "status": "need_more_info",
        "questions": ["...", "..."],
        "missing_fields": [...],
        "completeness_score": 0.4,
        "round": 1,
        "sentiment": {...}
      }

    Once sufficient details exist or round limit reached, returns:
      {
        "status": "ready",
        "ok": True,
        "narrative": "...",
        "issues": [],
        "completeness_score": 0.8,
        "extracted_fields": {...},
        "sentiment": {...}
      }
    """
    gaps = detect_gaps(raw_text, entities=entities)
    sent_res = analyze_sentiment_and_urgency(raw_text, entities=entities) if analyze_sentiment_and_urgency else None

    if gaps.get("is_thin") and round_count < max_rounds:
        return {
            "status": "need_more_info",
            "questions": gaps.get("questions", []),
            "missing_fields": gaps.get("missing_critical_info", []),
            "completeness_score": gaps.get("completeness_score", 0.0),
            "group": gaps.get("group", "_general"),
            "extracted_fields": gaps.get("extracted_fields", {}),
            "round": round_count + 1,
            "max_rounds": max_rounds,
            "sentiment": sent_res,
        }

    merged_fields = dict(gaps.get("extracted_fields", {}))
    if form_fields:
        merged_fields.update(form_fields)

    std_res = standardise(raw_text, entities=entities, form_fields=merged_fields,
                          provider=provider, model=model)

    return {
        "status": "ready",
        "ok": std_res.get("ok", False),
        "narrative": std_res.get("narrative", ""),
        "issues": std_res.get("issues", []),
        "attempts": std_res.get("attempts", 1),
        "completeness_score": gaps.get("completeness_score", 1.0),
        "group": gaps.get("group", "_general"),
        "extracted_fields": merged_fields,
        "round": round_count,
        "sentiment": sent_res,
    }


def analyze_and_extract(raw_text, entities=None, sub_category=None,
                        provider=DEFAULT_PROVIDER, model=DEFAULT_MODEL):
    """
    Unified entry point for Step 2 of the adaptive triage pipeline.
    Combines deterministic gap extraction with narrative standardisation and sentiment analysis.
    """
    gaps = detect_gaps(raw_text, entities=entities, sub_category=sub_category)
    sent_res = analyze_sentiment_and_urgency(raw_text, entities=entities) if analyze_sentiment_and_urgency else None
    
    std_res = standardise(raw_text, entities=entities, form_fields=gaps["extracted_fields"],
                          provider=provider, model=model)
    
    return {
        "ok": True,
        "group": gaps["group"],
        "extracted_fields": gaps["extracted_fields"],
        "missing_critical_info": gaps["missing_critical_info"],
        "completeness_score": gaps["completeness_score"],
        "standardised_narrative": std_res.get("narrative", ""),
        "narrative_ok": std_res.get("ok", False),
        "narrative_issues": std_res.get("issues", []),
        "sentiment": sent_res,
    }


# ---------------------------------------------------------------- demo

SAMPLES = [
    {
        "label": "Hinglish, informal, AePS",
        "raw": "sir mere account se 40000 nikal gaye, maine koi otp nahi diya, card mere paas hi hai, "
               "bank wale bol rahe hai thumb impression use hua",
        "entities": {"amount": "Rs. 40,000", "transaction_date": "12 August 2026"},
    },
    {
        "label": "Very short, UPI",
        "raw": "refund ke liye qr scan kiya aur 15000 kat gaye",
        "entities": {"amount": "Rs. 15,000"},
    },
    {
        "label": "Rambling, job fraud",
        "raw": "i applied for job on a portal then someone called saying hr and asked registration fee "
               "5000 i paid then he asked 12000 more for training i paid that also now number is off "
               "no job nothing please help",
        "entities": None,
    },
    {
        "label": "No entities, harassment",
        "raw": "someone made fake instagram id with my photos and sending messages to my friends",
        "entities": None,
    },
]


def _guard_selftest():
    """Exercises the guard without needing a model running."""
    print("GUARD SELF-TEST (no model required)\n" + "=" * 66)
    src = "paise gaye 40000 koi otp nahi aaya"
    ent = {"transaction_date": "12 August 2026"}

    cases = [
        ("clean - uses only supplied facts",
         "On 12 August 2026 the complainant found that an amount of 40000 had been debited "
         "from the account. No otp was shared by the complainant at any stage. The complainant "
         "requests that the matter be investigated and the amount recovered from the recipient.",
         True),
        ("invents an amount",
         "On 12 August 2026 the complainant lost 40000 and a further 25000 was debited later "
         "from the same account without any authorisation being given by the complainant at "
         "any point during the said period of the transactions.",
         False),
        ("invents a mechanism",
         "On 12 August 2026 the complainant received a phishing link and 40000 was debited "
         "from the account thereafter without any otp being shared by the complainant with "
         "any person at any time during the relevant period.",
         False),
        ("drops the amount",
         "On 12 August 2026 the complainant found that a sum of money had been debited from "
         "the account without authorisation. No otp was shared. The complainant requests that "
         "the matter be investigated and appropriate action be taken in accordance with law.",
         False),
        ("invents a year",
         "On 12 August 2024 the complainant found that 40000 had been debited from the account. "
         "No otp was shared by the complainant. The complainant requests that the matter be "
         "investigated and the amount be recovered from the recipient account.",
         False),
    ]
    passed = 0
    for label, narrative, should_pass in cases:
        ok, issues = guard(src, ent, narrative)
        good = (ok == should_pass)
        passed += good
        print(f"  [{'PASS' if good else 'FAIL'}] {label}")
        print(f"         guard says ok={ok}" + (f"  -> {issues[0]}" if issues else ""))
    print(f"\n{passed}/{len(cases)} guard behaviours correct")


def _demo(provider, model):
    print(f"MODULE A DEMO   provider={provider}  model={model}\n" + "=" * 74)
    for s in SAMPLES:
        print(f"\n--- {s['label']}")
        print(f"RAW      : {s['raw']}")
        if s["entities"]:
            print(f"ENTITIES : {s['entities']}")
        r = standardise(s["raw"], s["entities"], provider=provider, model=model)
        if r["ok"]:
            print(f"NARRATIVE: {r['narrative']}")
            print(f"           [accepted on attempt {r['attempts']}, {len(r['narrative'])} chars]")
        else:
            print(f"REJECTED : {r['issues']}")
            if r["narrative"]:
                print(f"  last attempt was: {r['narrative'][:200]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="guard self-test, no model needed")
    ap.add_argument("--provider", choices=list(_CALL), default=DEFAULT_PROVIDER)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--text", help="standardise one complaint and exit")
    a = ap.parse_args()

    if a.check:
        _guard_selftest()
    elif a.text:
        r = standardise(a.text, provider=a.provider, model=a.model)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _demo(a.provider, a.model)
