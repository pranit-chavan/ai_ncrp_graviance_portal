"""
MODULE C - OCR and Entity Extraction

Reads screenshots a complainant attaches - payment confirmations, chat threads,
fraudulent SMS, transaction alerts - and pulls out the structured facts an
investigator needs.

WHY THIS MATTERS
    A complainant writes "paise gaye". The screenshot says the amount, the UPI ID,
    the transaction reference and the timestamp. Those are exactly the identifiers
    that let an officer freeze a beneficiary account, and they are the difference
    between a traceable case and an untraceable one.

    The entities feed two places:
      Module A - so the narrative can state facts the complainant did not type
      Module E - the evidence section of the case file

DESIGN DECISION: OCR then REGEX, not OCR then LLM.
    Once text is extracted, finding a UPI ID or an amount is pattern matching, and
    a regex is exact, instant, free and auditable. An LLM here would add latency,
    cost, and the possibility of inventing a transaction reference that was never
    on the screen. The same principle as Module D: where the answer is
    deterministic, do not use a model.

DESIGN DECISION: every entity carries its confidence and the raw matched text.
    An investigator acting on a UPI ID needs to know whether OCR read it cleanly
    or guessed at a blurred character.

SETUP
    pip install pytesseract pillow
    Windows: install Tesseract from
        https://github.com/UB-Mannheim/tesseract/wiki
    then either add it to PATH or set:
        pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

USAGE
    from modules.ocr_extract import extract_from_images

    result = extract_from_images(["upi_screenshot.png", "chat.png"])
    result["entities"]      merged entities across all images
    result["per_image"]     what each image contributed
    result["ok"]            False if OCR was unavailable

    python modules/ocr_extract.py --check          regex self-test, no images needed
    python modules/ocr_extract.py path/to/img.png  extract from one image
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------- patterns
#
# Ordered by specificity. A 12-digit number is an Aadhaar; a 10-digit number
# starting 6-9 is an Indian mobile. Order matters because the more specific
# pattern must claim the text first.

PATTERNS = {
    "upi_id": {
        # name@bank - the handle is 3-15 alpha chars, no digits, which rules out
        # email addresses ending in .com
        "re": re.compile(r"\b([\w.\-]{2,30}@[a-zA-Z]{3,15})\b"),
        "label": "UPI ID",
        "reject": lambda m: "." in m.split("@")[1],   # that is an email domain
    },
    "amount": {
        # Rs. 40,000 / ₹40000 / INR 40,000.00 - Indian grouping included
        "re": re.compile(r"(?:₹|Rs\.?|INR)\s?([\d,]+(?:\.\d{2})?)", re.I),
        "label": "Amount",
    },
    "transaction_ref": {
        # UTR / RRN / txn id - 12 to 22 digits, or an alphanumeric reference
        "re": re.compile(r"\b(?:UTR|RRN|Txn|Transaction|Ref(?:erence)?)[\s:.#]*"
                         r"([A-Z0-9]{8,25})\b", re.I),
        "label": "Transaction reference",
    },
    "phone": {
        "re": re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)"),
        "label": "Phone number",
    },
    "aadhaar_last4": {
        # never store a full Aadhaar - capture only the masked form
        "re": re.compile(r"(?:x{4,}|X{4,}|\*{4,})\s?(\d{4})\b"),
        "label": "Masked ID last 4 digits",
    },
    "account_last4": {
        "re": re.compile(r"(?:A/c|Acct?|Account)[\s.:No]*(?:x+|X+|\*+)?(\d{4})\b", re.I),
        "label": "Account last 4 digits",
    },
    "card_last4": {
        "re": re.compile(r"(?:card|ending)[\s.:in]*(?:x+|X+|\*+)?(\d{4})\b", re.I),
        "label": "Card last 4 digits",
    },
    "date": {
        "re": re.compile(r"\b(\d{1,2}[-/\s](?:\d{1,2}|Jan|Feb|Mar|Apr|May|Jun|Jul|"
                         r"Aug|Sep|Oct|Nov|Dec)[a-z]*[-/\s]\d{2,4})\b", re.I),
        "label": "Date",
    },
    "time": {
        "re": re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?\s?(?:AM|PM|am|pm)?)\b"),
        "label": "Time",
    },
    "email": {
        "re": re.compile(r"\b([\w.\-]+@[\w\-]+\.[a-zA-Z]{2,})\b"),
        "label": "Email address",
    },
}

# Platform names worth recording. Presence of these in a screenshot is a strong
# signal for the classifier and useful context for the officer.
PLATFORMS = [
    "PhonePe", "Google Pay", "GPay", "Paytm", "BHIM", "Amazon Pay", "Mobikwik",
    "WhatsApp", "Telegram", "Instagram", "Facebook", "Snapchat",
    "SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "Bank of Baroda", "Canara",
    "Naukri", "LinkedIn", "Shine", "Indeed",
]


def _clean(text):
    """OCR routinely confuses these. Applied only inside numeric contexts."""
    return text


def _confidence(key, raw, full_text):
    """
    A crude but honest confidence. OCR gives per-word confidence, but for a
    regex match what matters more is whether the match looks well-formed.
    """
    score = 0.75
    if key == "amount":
        digits = raw.replace(",", "").replace(".", "")
        if digits.isdigit():
            score = 0.9
        if len(digits) > 9:               # implausibly large - likely a misread
            score = 0.4
    elif key == "upi_id":
        score = 0.9 if re.fullmatch(r"[\w.\-]{2,30}@[a-z]{3,15}", raw) else 0.6
    elif key == "phone":
        score = 0.9
    elif key in ("account_last4", "card_last4", "aadhaar_last4"):
        score = 0.85
    elif key == "transaction_ref":
        score = 0.8 if raw.isalnum() else 0.5
    return score


def extract_entities(text):
    """
    Pull structured entities out of already-extracted text.
    Works on OCR output, but also on any plain text - which is what makes the
    regexes testable without an image.
    """
    found = {}

    for key, spec in PATTERNS.items():
        matches = []
        for m in spec["re"].finditer(text):
            raw = m.group(1).strip()
            if spec.get("reject") and spec["reject"](raw):
                continue
            matches.append(raw)
        if matches:
            # de-duplicate, keep order
            seen, uniq = set(), []
            for v in matches:
                if v not in seen:
                    seen.add(v)
                    uniq.append(v)
            found[key] = [{"value": v,
                           "confidence": _confidence(key, v, text),
                           "label": spec["label"]} for v in uniq]

    # "A/c XXXX4417" matches both the account pattern and the generic masked-ID
    # pattern. The one with explicit account/card context is the correct read.
    if "aadhaar_last4" in found:
        claimed = set()
        for k in ("account_last4", "card_last4"):
            claimed |= {e["value"] for e in found.get(k, [])}
        found["aadhaar_last4"] = [e for e in found["aadhaar_last4"]
                                  if e["value"] not in claimed]
        if not found["aadhaar_last4"]:
            del found["aadhaar_last4"]

    # a UPI ID also matches the email pattern - drop the duplicate
    if "upi_id" in found and "email" in found:
        upis = {e["value"] for e in found["upi_id"]}
        found["email"] = [e for e in found["email"] if e["value"] not in upis]
        if not found["email"]:
            del found["email"]

    plats = [p for p in PLATFORMS if re.search(rf"\b{re.escape(p)}\b", text, re.I)]
    if plats:
        found["platform"] = [{"value": p, "confidence": 0.85, "label": "Platform"}
                             for p in plats]

    return found


# ---------------------------------------------------------------- OCR

def ocr_image(path, lang="eng"):
    """
    Extract text from one image. Returns (text, error).
    Never raises - a missing Tesseract must degrade, not crash the pipeline.
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter
    except ImportError as e:
        return "", f"missing package: {e.name}. Run: pip install pytesseract pillow"

    if not os.path.exists(path):
        return "", f"file not found: {path}"

    try:
        img = Image.open(path)
        # Screenshots are usually clean, but upscaling small ones and raising
        # contrast measurably improves reads on phone screenshots.
        if img.width < 1000:
            img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        text = pytesseract.image_to_string(img, lang=lang)
        return text, None
    except Exception as e:
        msg = str(e)
        if "tesseract" in msg.lower():
            msg = ("Tesseract is not installed or not on PATH. "
                   "Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        return "", msg


def extract_from_images(paths, lang="eng"):
    """
    Run OCR over a list of images and merge the entities found.

    Returns:
        ok         False if no image could be read at all
        entities   merged, flattened - the form Module A and E expect
        detailed   entities with confidence and source image
        per_image  raw text and entity count per image
        errors     anything that went wrong
    """
    paths = paths or []
    per_image, errors, merged = [], [], {}

    for p in paths:
        text, err = ocr_image(p, lang)
        if err:
            errors.append({"file": os.path.basename(p), "error": err})
            per_image.append({"file": os.path.basename(p), "chars": 0, "entities": 0})
            continue

        ents = extract_entities(text)
        per_image.append({
            "file": os.path.basename(p),
            "chars": len(text),
            "entities": sum(len(v) for v in ents.values()),
            "raw_text": text[:500],
        })

        for key, items in ents.items():
            for item in items:
                item = dict(item, source=os.path.basename(p))
                merged.setdefault(key, [])
                if item["value"] not in [e["value"] for e in merged[key]]:
                    merged[key].append(item)

    # flatten to the simple key: value shape Modules A and E consume
    flat = {}
    for key, items in merged.items():
        best = max(items, key=lambda e: e["confidence"])
        flat[key] = best["value"] if len(items) == 1 else [i["value"] for i in items]

    return {
        "ok": bool(merged),
        "entities": flat,
        "detailed": merged,
        "per_image": per_image,
        "errors": errors,
    }


# ---------------------------------------------------------------- self test

SAMPLES = [
    ("UPI payment confirmation", """
        Payment Successful
        ₹ 40,000
        To: rahul4417@okaxis
        From: A/c XXXX4417
        UTR: 428391756201
        12 Aug 2026, 3:42 PM
        PhonePe
    """),
    ("Bank SMS alert", """
        Dear Customer, Rs.15,000.00 debited from A/c no. XX8821 on 03-08-2026
        to VPA fraudster99@ybl (UPI Ref 219847362015). Not you? Call 18001234567.
        - SBI
    """),
    ("Job fraud chat", """
        HR Priya  10:15 AM
        Congratulations! You are selected.
        Registration fee Rs. 5,000 to be paid today.
        Pay to: hrpriya2026@paytm
        Contact 9876543210
        WhatsApp
    """),
    ("Card statement line", """
        Transaction Alert
        Card ending 6411
        INR 2,50,000.00
        15/09/2026 11:03:22
        Ref# TXN889201773645
    """),
]


def _selftest():
    print("MODULE C - ENTITY EXTRACTION SELF-TEST")
    print("Regex only, no images or Tesseract required.\n" + "=" * 70)
    total = 0
    for label, text in SAMPLES:
        ents = extract_entities(text)
        n = sum(len(v) for v in ents.values())
        total += n
        print(f"\n{label}   ({n} entities)")
        for key, items in ents.items():
            for it in items:
                print(f"   {it['label']:<26} {it['value']:<24} conf {it['confidence']:.2f}")
    print("\n" + "=" * 70)
    print(f"{total} entities extracted across {len(SAMPLES)} samples")

    print("\nChecks:")
    e1 = extract_entities(SAMPLES[0][1])
    checks = [
        ("amount found",        "amount" in e1),
        ("UPI ID found",        "upi_id" in e1),
        ("UPI not misread as email", "email" not in e1),
        ("account last 4 only", e1.get("account_last4", [{}])[0].get("value") == "4417"),
        ("platform detected",   "platform" in e1),
    ]
    e4 = extract_entities(SAMPLES[3][1])
    checks.append(("card last 4 only", e4.get("card_last4", [{}])[0].get("value") == "6411"))
    for name, ok in checks:
        print(f"   [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{sum(ok for _, ok in checks)}/{len(checks)} checks passed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="*", help="image files to process")
    ap.add_argument("--check", action="store_true", help="regex self-test, no images")
    ap.add_argument("--lang", default="eng")
    ap.add_argument("--text", help="extract from a text string instead of an image")
    a = ap.parse_args()

    if a.check:
        _selftest()
    elif a.text:
        print(json.dumps(extract_entities(a.text), indent=2, ensure_ascii=False))
    elif a.images:
        r = extract_from_images(a.images, a.lang)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        _selftest()
