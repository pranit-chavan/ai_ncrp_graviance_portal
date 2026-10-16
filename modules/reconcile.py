"""
RECONCILIATION LAYER

Combines the citizen's typed text with OCR-extracted entities into ONE
consistent input for Module A, and reports:
  - agreements   (both sources say the same thing — high confidence)
  - conflicts    (sources disagree — needs the citizen or officer to resolve)
  - gaps         (neither source has it — candidate for a follow-up question)

WHY THIS EXISTS
    A citizen types: "paise gaye 40000"
    A screenshot they attach shows: a UPI ID, a DIFFERENT amount (Rs. 42,000 —
    the typed figure was a rough memory), a transaction reference, a date.

    Right now these two sources go into Module A separately with no check
    between them. Two failure modes are possible:

    1. They agree — fine, no problem.
    2. They disagree — the narrative might pick one arbitrarily, or Module A's
       guard might reject the narrative because the numbers "don't match" when
       in fact one source is just more precise than the other.

    There also isn't currently anything that looks at BOTH sources together and
    says "the text mentions a job offer but no company name was given, and the
    screenshot doesn't have one either — this is a genuine gap."

DESIGN PRINCIPLE
    OCR entities are usually MORE precise than typed text for numbers (amount,
    date, phone, transaction ref), because they come from an official
    confirmation screen rather than memory. Typed text is usually MORE
    reliable for narrative facts (what happened, why, who called) because OCR
    cannot read intent.

    So the reconciliation rule is:
        numeric/structured facts  -> OCR wins if present, typed text is fallback
        narrative/contextual facts -> typed text is authoritative, OCR only adds

USAGE
    from modules.reconcile import reconcile

    result = reconcile(
        typed_text="paise gaye 40000",
        ocr_entities={"amount": "Rs. 42,000", "upi_id": "fraud99@ybl",
                      "transaction_ref": "428391756201", "date": "12 Aug 2026"},
    )
    result["merged_text"]       typed text + labelled appendix of OCR facts
    result["agreements"]        entities found in both sources
    result["conflicts"]         entities where OCR and typed text disagree
    result["gaps"]              fields with no value from either source
    result["confidence_note"]   short reliability string for the officer

    python modules/reconcile.py              demo with sample inputs
    python modules/reconcile.py --check      self-test
"""

import re
import sys
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Entity keys that are numeric/structured — OCR wins for these
# ---------------------------------------------------------------------------

NUMERIC_ENTITY_KEYS = {
    "amount", "upi_id", "transaction_ref", "phone",
    "date", "time", "account_last4", "card_last4", "aadhaar_last4",
}

# Keys that are narrative/contextual — typed text is authoritative
NARRATIVE_ENTITY_KEYS = {
    "platform", "email",
}

# Fields the officer needs for a traceable case. If NEITHER source has
# one of these, it is a genuine gap worth flagging.
IMPORTANT_FIELDS = ["amount", "date", "platform", "upi_id", "transaction_ref"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_numbers(text):
    """All digit-only strings (commas stripped) of 3+ digits from text.
    Returns a set of cleaned numeric strings."""
    if not text:
        return set()
    # normalise Devanagari digits
    tr = str.maketrans("०१२३४५६७८९", "0123456789")
    norm = text.translate(tr)
    return {re.sub(r"[^\d]", "", n) for n in re.findall(r"[\d,]{3,}", norm) if re.sub(r"[^\d]", "", n)}


def _digits_of(value):
    """Extract just the digit characters from a value (amount, ref, etc.)."""
    if not value:
        return ""
    return re.sub(r"[^\d]", "", str(value))


def _has_amount_in_text(text):
    """Check if typed text mentions any amount (₹/Rs/number)."""
    if not text:
        return False
    if re.search(r"(?:₹|Rs\.?|INR)\s?[\d,]+", text, re.I):
        return True
    return bool(_extract_numbers(text))


def _has_date_in_text(text):
    """Check if typed text mentions any date."""
    if not text:
        return False
    months = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    if re.search(rf"\d{{1,2}}[-/\s]{months}", text, re.I):
        return True
    if re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", text):
        return True
    if re.search(r"\b(20\d{2})\b", text):
        return True
    if re.search(r"\b(today|yesterday|last\s+\w+|aaj|kal|काल|आज)\b", text, re.I):
        return True
    return False


def _has_platform_in_text(text):
    """Check if typed text mentions a platform name."""
    if not text:
        return False
    platforms = (r"phonepe|google pay|gpay|paytm|bhim|amazon pay|mobikwik"
                 r"|whatsapp|telegram|instagram|facebook|naukri|linkedin"
                 r"|sbi|hdfc|icici|axis|kotak|pnb|upi|net banking"
                 r"|email|gmail|portal|website|app")
    return bool(re.search(platforms, text, re.I))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reconcile(typed_text, ocr_entities=None):
    """
    Merge a citizen's typed complaint with OCR-extracted entities from
    their attached screenshots.

    Parameters
    ----------
    typed_text    : str   — the citizen's raw complaint text
    ocr_entities  : dict  — output of modules.ocr_extract, or None/{}

    Returns
    -------
    dict with:
        merged_text       : str   — typed text + labelled OCR appendix, ready for Module A
        agreements        : list  — [(field, value)] entities found in both sources
        conflicts         : list  — [dict] where OCR and typed text disagree
        gaps              : list  — [str] field names missing from BOTH sources
        ocr_only          : list  — [(field, value)] entities present ONLY in OCR
        typed_only        : list  — [(field, value)] entities present ONLY in typed text
        confidence_note   : str   — short reliability assessment for officer
        has_conflicts     : bool  — True if any conflicts exist
    """
    ocr_entities = ocr_entities or {}
    typed_numbers = _extract_numbers(typed_text)

    agreements = []
    conflicts = []
    ocr_only = []
    appendix_lines = []

    for key, value in ocr_entities.items():
        # Handle list values (multiple matches from OCR)
        vals = value if isinstance(value, list) else [value]

        if key in NARRATIVE_ENTITY_KEYS:
            # Narrative-adjacent entity (e.g. platform) — just append,
            # no conflict check needed. Typed text is authoritative for
            # context; OCR only adds.
            for v in vals:
                if v:
                    appendix_lines.append(f"{key}: {v}")
                    ocr_only.append((key, v))
            continue

        if key not in NUMERIC_ENTITY_KEYS:
            # Unknown key — include but don't conflict-check
            for v in vals:
                if v:
                    appendix_lines.append(f"{key}: {v}")
            continue

        # Numeric / structured entity — OCR is more precise
        for v in vals:
            v_digits = _digits_of(v)
            if not v_digits:
                appendix_lines.append(f"{key}: {v}")
                continue

            if v_digits in typed_numbers:
                # ✓ AGREEMENT — both sources have the same number
                agreements.append((key, str(v)))
                appendix_lines.append(f"{key}: {v}  (confirmed — matches typed text)")
            else:
                # The number is in OCR but NOT in typed text.
                # This becomes a CONFLICT only if the typed text mentions a
                # DIFFERENT figure for the same kind of field (e.g. both
                # mention an amount, but with different numbers).
                is_conflict = False

                if key == "amount" and _has_amount_in_text(typed_text):
                    # Typed text mentions an amount AND OCR has a different one
                    is_conflict = True
                    conflicts.append({
                        "field": key,
                        "ocr_value": str(v),
                        "typed_mentions": sorted(typed_numbers)[:5],
                        "resolution": (
                            "OCR value used — screenshots are more reliable "
                            "for exact amounts than memory"
                        ),
                    })

                if not is_conflict:
                    # Present in OCR only — not a conflict, just additional info
                    ocr_only.append((key, str(v)))

                appendix_lines.append(
                    f"{key}: {v}  (from attached evidence"
                    + (" — differs from typed text" if is_conflict else "")
                    + ")"
                )

    # ---- detect genuine gaps ------------------------------------------------
    # A gap means NEITHER the typed text NOR the OCR has this information.
    gaps = []

    if "amount" not in ocr_entities and not _has_amount_in_text(typed_text):
        gaps.append("amount")

    if "date" not in ocr_entities and not _has_date_in_text(typed_text):
        gaps.append("date")

    if "platform" not in ocr_entities and not _has_platform_in_text(typed_text):
        gaps.append("platform")

    # UPI ID / account — only flag as a gap for financial complaints
    financial_signal = any(
        w in (typed_text or "").lower()
        for w in ("paise", "kat", "debit", "rupee", "rs", "₹", "transfer",
                  "upi", "bank", "account", "पैसे")
    )
    if financial_signal:
        if ("upi_id" not in ocr_entities
                and "account_last4" not in ocr_entities
                and not re.search(r"[\w.\-]{2,30}@[a-zA-Z]{2,15}", typed_text or "")):
            gaps.append("account_or_upi")

    # ---- build merged text --------------------------------------------------
    merged_text = typed_text or ""
    if appendix_lines:
        merged_text += "\n\nDetails confirmed from attached evidence:\n"
        merged_text += "\n".join(f"  - {line}" for line in appendix_lines)

    # ---- confidence note ----------------------------------------------------
    if agreements and not conflicts:
        confidence_note = "high — typed account and evidence agree"
    elif not conflicts and not ocr_only:
        confidence_note = "text only — no screenshot evidence to cross-check"
    elif not conflicts:
        confidence_note = "medium — some figures came only from evidence"
    else:
        confidence_note = (
            "needs review — typed account and evidence disagree on key figures"
        )

    return {
        "merged_text": merged_text,
        "agreements": agreements,
        "conflicts": conflicts,
        "gaps": gaps,
        "ocr_only": ocr_only,
        "typed_only": [],  # placeholder — could extract typed-only entities later
        "confidence_note": confidence_note,
        "has_conflicts": bool(conflicts),
    }


def format_reconciliation_for_display(result):
    """Render reconciliation result as a short string for dashboard/terminal."""
    lines = []

    if result["agreements"]:
        lines.append("✓ Agreements (typed text matches evidence):")
        for field, val in result["agreements"]:
            lines.append(f"    {field}: {val}")

    if result["conflicts"]:
        lines.append("⚠ Conflicts (typed text disagrees with evidence):")
        for c in result["conflicts"]:
            lines.append(f"    {c['field']}: OCR says {c['ocr_value']}, "
                         f"typed text mentions {c['typed_mentions']}")
            lines.append(f"      → {c['resolution']}")

    if result["ocr_only"]:
        lines.append("+ Additional from evidence only:")
        for field, val in result["ocr_only"]:
            lines.append(f"    {field}: {val}")

    if result["gaps"]:
        lines.append("✗ Missing from both sources:")
        for g in result["gaps"]:
            lines.append(f"    {g}")

    lines.append(f"\nConfidence: {result['confidence_note']}")

    return "\n".join(lines) if lines else "No reconciliation needed (text only, no attachments)."


# ---------------------------------------------------------------------------
# Demo and self-test
# ---------------------------------------------------------------------------

DEMO_CASES = [
    {
        "label": "Agreement — typed amount matches OCR",
        "typed": "paise gaye 40000 phonepe se, koi otp nahi diya",
        "ocr": {"amount": "Rs. 40,000", "platform": "PhonePe",
                "date": "12 Aug 2026", "transaction_ref": "428391756201"},
    },
    {
        "label": "Conflict — typed says 40000, OCR says 42000",
        "typed": "mere account se 40000 nikal gaye bina otp ke",
        "ocr": {"amount": "Rs. 42,000", "upi_id": "fraud99@ybl",
                "date": "12 Aug 2026"},
    },
    {
        "label": "OCR fills everything — citizen typed almost nothing",
        "typed": "paise gaye",
        "ocr": {"amount": "Rs. 15,000", "platform": "Google Pay",
                "upi_id": "scam123@ybl", "date": "10 Sep 2026",
                "transaction_ref": "UPI928374610293"},
    },
    {
        "label": "No OCR — text only",
        "typed": "i applied for job on naukri, someone called as HR, asked 5000 registration fee, i paid via UPI on 15 august",
        "ocr": {},
    },
    {
        "label": "Both empty — maximum gaps",
        "typed": "someone cheated me",
        "ocr": {},
    },
]


def _selftest():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("RECONCILIATION SELF-TEST\n" + "=" * 64)
    tests = [
        # (typed, ocr, expected_agreements_min, expected_conflicts, expected_gaps_subset)
        (
            "paise gaye 40000 phonepe se",
            {"amount": "Rs. 40,000", "platform": "PhonePe", "date": "12 Aug 2026"},
            1,   # at least 1 agreement (amount)
            0,   # no conflicts
            [],  # no gaps expected
        ),
        (
            "mere account se 40000 nikal gaye",
            {"amount": "Rs. 42,000"},
            0,   # no agreement (numbers differ)
            1,   # 1 conflict (amount)
            [],
        ),
        (
            "someone cheated me",
            {},
            0, 0,
            ["amount", "date", "platform"],  # genuine gaps
        ),
        (
            "paise gaye",
            {"amount": "15000", "platform": "PhonePe", "date": "12 Aug 2026"},
            0, 0,
            [],  # no gaps — OCR fills everything
        ),
        (
            "₹40,000 taken from PhonePe on 12 August 2026 via UTR 4283917",
            {},
            0, 0,
            [],  # text has everything, no gaps
        ),
    ]

    passed = 0
    for typed, ocr, min_agree, n_conflict, exp_gaps in tests:
        r = reconcile(typed, ocr)
        ok = True
        if len(r["agreements"]) < min_agree:
            ok = False
        if len(r["conflicts"]) != n_conflict:
            ok = False
        if not all(g in r["gaps"] for g in exp_gaps):
            ok = False
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] '{typed[:50]}'")
        if not ok:
            print(f"         agreements={len(r['agreements'])} (min {min_agree}), "
                  f"conflicts={len(r['conflicts'])} (exp {n_conflict}), "
                  f"gaps={r['gaps']} (exp subset {exp_gaps})")

    print(f"\n{passed}/{len(tests)} self-test cases passed")


def _demo():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("RECONCILIATION LAYER DEMO\n" + "=" * 64)
    for c in DEMO_CASES:
        r = reconcile(c["typed"], c.get("ocr", {}))
        print(f"\n--- {c['label']}")
        print(f"  typed : {c['typed'][:70]}")
        if c.get("ocr"):
            print(f"  ocr   : {c['ocr']}")
        print(format_reconciliation_for_display(r))
        print(f"  merged text preview: {r['merged_text'][:120]}...")


if __name__ == "__main__":
    if "--check" in sys.argv:
        _selftest()
    else:
        _demo()
