"""
END-TO-END PIPELINE

Runs a raw citizen complaint through every module that exists and produces a
case file.

    raw text + screenshots
        -> Module C  entity extraction        (stub until C is built)
        -> Module A  standardised narrative
        -> Module B  classification
        -> Module D  legal sections
        -> Module E  case file (JSON + PDF)

Every stage degrades gracefully. If Module A cannot produce a narrative that
passes its guard, the pipeline continues on the raw text and records that fact
in the case file, rather than failing.

USAGE
    python pipeline.py --demo
    python pipeline.py --text "paise gaye 40000 koi otp nahi aaya"
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.ai_assistant import standardise, detect_gaps_and_autofill, analyze_and_extract
from modules.case_file import build_case_file, write_json, write_pdf, format_text
from modules.ocr_extract import extract_from_images, extract_entities as parse_text_entities
from modules.reconcile import reconcile
from modules.sentiment_analysis import analyze_sentiment_and_urgency


# ---- Module B: classifier ---------------------------------------------------

_MODEL = {"vec": None, "clf": None, "labels": None}


def _load_classifier():
    """Train the baseline on demand. In production this would load a saved model."""
    if _MODEL["clf"] is not None:
        return True
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.svm import LinearSVC
        from sklearn.preprocessing import LabelEncoder
    except ImportError:
        return False

    texts, labels = [], []
    for p in sorted(glob.glob(os.path.join("dataset", "splits", "train", "*.jsonl"))):
        for line in open(p, encoding="utf-8"):
            r = json.loads(line)
            texts.append(r["complaint_text"])
            labels.append(r["sub_category"])
    if not texts:
        return False

    le = LabelEncoder().fit(labels)
    vec = TfidfVectorizer(ngram_range=(1, 2), max_features=50000,
                          sublinear_tf=True, min_df=2)
    X = vec.fit_transform(texts)
    clf = LinearSVC(C=1.0, max_iter=10000).fit(X, le.transform(labels))

    _MODEL.update(vec=vec, clf=clf, labels=le)
    return True


def classify(narrative):
    """Return (sub_category, confidence). Confidence from the decision margin."""
    if not _load_classifier():
        return None, None
    import numpy as np
    X = _MODEL["vec"].transform([narrative])
    margins = _MODEL["clf"].decision_function(X)[0]
    idx = int(np.argmax(margins))

    # A linear SVM has no probability. What it does have is a MARGIN: how far
    # the top class sits ahead of the runner-up. That gap is the honest signal -
    # a wide gap means the decision was clear, a narrow one means two categories
    # were competing. Mapped to 0-1 so the case file can band it.
    order = np.sort(margins)[::-1]
    gap = float(order[0] - order[1])
    conf = float(min(1.0, max(0.0, 0.5 + gap / 2.0)))

    return str(_MODEL["labels"].inverse_transform([idx])[0]), conf


def enrich_text_for_classification(text, entities=None, ocr_texts=None):
    """
    Enrich raw text with platform and mechanism keywords found in OCR so that
    even very short complaints benefit from multimodal evidence.
    """
    extras = []
    if entities:
        for k, v in entities.items():
            if k in ("platform", "upi_id", "transaction_ref"):
                if isinstance(v, list):
                    extras.extend(str(item) for item in v)
                elif v:
                    extras.append(str(v))
    if ocr_texts:
        for t in ocr_texts:
            if t:
                extras.append(t[:300])

    if extras:
        return f"{text} {' '.join(extras)}"
    return text


# ---- Module C: entity extraction --------------------------------------------

def extract_entities(attachments):
    """
    Extract structured entities from image attachments using Module C (OCR).
    Returns flat entities dictionary or None if no attachments or extraction failed.
    """
    if not attachments:
        return None
    try:
        res = extract_from_images(attachments)
        if res.get("ok"):
            return res.get("entities")
    except Exception as e:
        print(f"[C] OCR error: {e}")
    return None


def extract_entities_detailed(attachments):
    """
    Extract full OCR results including raw text and confidence scores.
    """
    if not attachments:
        return {"ok": False, "entities": {}, "detailed": {}, "per_image": [], "errors": []}
    try:
        return extract_from_images(attachments)
    except Exception as e:
        return {"ok": False, "entities": {}, "detailed": {}, "per_image": [], "errors": [{"file": "all", "error": str(e)}]}


# ---- Adaptive Multi-Modal Triage --------------------------------------------

def triage_complaint(raw_text, attachments=None, provider="ollama", model="qwen2.5:7b", verbose=False):
    """
    Multi-modal triage engine:
      1. OCR on attachments -> extracts text + entities
      2. Reconciliation -> merges typed text with OCR, finds agreements/conflicts/gaps
      3. AI Assistant -> gap detection & auto-fill fields using reconciled input
      4. AI Assistant -> standardises narrative using all gathered facts
      5. Classifier -> predicts NCRP category using enriched multi-modal context
    """
    log = print if verbose else (lambda *a, **k: None)

    # 1. OCR
    log("[C] Running OCR on attachments...")
    ocr_res = extract_entities_detailed(attachments) if attachments else {"ok": False, "entities": {}, "detailed": {}, "per_image": [], "errors": []}
    entities = ocr_res.get("entities", {})
    ocr_raw_snippets = [img.get("raw_text", "") for img in ocr_res.get("per_image", []) if img.get("raw_text")]

    # 2. Reconciliation — merge typed text with OCR entities
    log("[R] Reconciling typed text with OCR evidence...")
    recon = reconcile(raw_text, entities)
    merged_text = recon["merged_text"]
    if recon["has_conflicts"]:
        log(f"    [CONFLICT] {len(recon['conflicts'])} conflict(s) detected")
    if recon["gaps"]:
        log(f"    [GAP] gaps: {recon['gaps']}")

    # 3. Initial field extraction for prompt context (using reconciled input)
    gaps_initial = detect_gaps_and_autofill(merged_text, entities=entities)

    # 4. Standardise / Translate Narrative (Module A) — uses merged text
    log("[A] Standardising and translating narrative...")
    std_res = standardise(merged_text, entities=entities, form_fields=gaps_initial["extracted_fields"],
                          provider=provider, model=model)
    english_narrative = std_res.get("narrative", "") if std_res.get("ok") else raw_text

    # 5. Classify using the English narrative + OCR features (Module B)
    log("[B] Classifying narrative...")
    enriched_text = enrich_text_for_classification(english_narrative, entities, ocr_raw_snippets)
    sub_category, confidence = classify(enriched_text)
    if not sub_category:
        sub_category = "UNCLASSIFIED"
        confidence = 0.0

    # 6. Final Gap analysis tailored to the predicted category
    gaps = detect_gaps_and_autofill(merged_text, entities=entities, sub_category=sub_category)

    # 7. Sentiment & Emotional Urgency Triage
    sentiment = analyze_sentiment_and_urgency(merged_text, entities=entities)

    return {
        "raw_text": raw_text,
        "attachments": attachments or [],
        "ocr_result": ocr_res,
        "entities": entities,
        "reconciliation": recon,
        "sub_category": sub_category,
        "confidence": confidence,
        "group": gaps["group"],
        "extracted_fields": gaps["extracted_fields"],
        "missing_critical_info": gaps["missing_critical_info"],
        "completeness_score": gaps["completeness_score"],
        "standardised_narrative": english_narrative,
        "narrative_ok": std_res.get("ok", False),
        "narrative_issues": std_res.get("issues", []),
        "sentiment": sentiment,
    }


# ---- the pipeline -----------------------------------------------------------

def run(raw_text, complainant=None, attachments=None,
        provider="ollama", model="qwen2.5:7b", verbose=True,
        # -- NCRP-shaped additions, all optional and forwarded to Module E --
        incident_datetime=None, category=None, modus_operandi=None,
        incident_location=None, transactions=None,
        suspect_transactions=None, suspects=None,
        evidence_table=None, entities=None,
        delay_in_reporting=None, delay_reason=None):

    complainant = complainant or {}
    attachments = attachments or []
    log = print if verbose else (lambda *a, **k: None)

    log("\n[C] entity extraction")
    if entities is None:
        entities = extract_entities(attachments)
    log(f"    {entities if entities else 'No OCR entities extracted from attachments'}")

    log("\n[R] reconciliation")
    recon = reconcile(raw_text, entities)
    merged_text = recon["merged_text"]
    if recon["has_conflicts"]:
        log(f"    [CONFLICT] {len(recon['conflicts'])} conflict(s) between typed text and evidence")
        for c in recon["conflicts"]:
            log(f"      {c['field']}: OCR={c['ocr_value']} vs typed={c['typed_mentions']}")
    if recon["agreements"]:
        log(f"    [AGREE] {len(recon['agreements'])} agreement(s)")
    if recon["gaps"]:
        log(f"    [GAP] gaps: {recon['gaps']}")
    log(f"    confidence: {recon['confidence_note']}")

    log("\n[A] narrative standardisation")
    a = standardise(merged_text, entities, provider=provider, model=model)
    if a["ok"]:
        narrative = a["narrative"]
        log(f"    accepted on attempt {a['attempts']}")
        log(f"    {narrative[:150]}...")
    else:
        narrative = None
        log(f"    REJECTED: {a['issues']}")
        log("    falling back to the raw text for classification")

    log("\n[B] classification")
    text_for_classifier = narrative or raw_text
    sub_category, confidence = classify(text_for_classifier)
    if sub_category:
        log(f"    {sub_category}  ({confidence:.1%})")
    else:
        log("    classifier unavailable")
        sub_category = "UNCLASSIFIED"

    log("\n[D+E] legal mapping and case file")
    case = build_case_file(
        complainant=complainant,
        raw_complaint=raw_text,
        narrative=narrative,
        sub_category=sub_category,
        confidence=confidence,
        entities=entities,
        attachments=attachments,
        incident_datetime=incident_datetime,
        category=category,
        modus_operandi=modus_operandi,
        incident_location=incident_location,
        transactions=transactions,
        suspect_transactions=suspect_transactions,
        suspects=suspects,
        evidence_table=evidence_table,
        reconciliation=recon,
        sentiment=analyze_sentiment_and_urgency(raw_text, entities=entities, incident_datetime=incident_datetime),
        delay_in_reporting=delay_in_reporting,
        delay_reason=delay_reason,
    )
    if not a["ok"]:
        case["complaint"]["narrative_source"] = f"unavailable - {a['issues']}"

    jp = write_json(case)
    try:
        pp = write_pdf(case)
    except SystemExit:
        pp = None
    log(f"    {case['reference']}")
    log(f"    {jp}")
    if pp:
        log(f"    {pp}")

    return case


DEMO = [
    ("sir mere account se 40000 nikal gaye, maine koi otp nahi diya, card mere paas hi hai, "
     "bank wale bol rahe hai thumb impression use hua",
     {"name": "R. Sharma", "age": 34, "phone": "98XXXXXX21", "city": "Nashik",
      "state": "Maharashtra"}),
    ("i applied for job on a portal then someone called saying hr and asked registration fee "
     "5000 i paid then he asked 12000 more for training now number is off no job nothing",
     {"name": "A. Patil", "age": 22, "phone": "97XXXXXX40", "city": "Pune",
      "state": "Maharashtra"}),
]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--text")
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default="qwen2.5:7b")
    a = ap.parse_args()

    if a.text:
        case = run(a.text, provider=a.provider, model=a.model)
        print("\n" + format_text(case))
    else:
        for i, (text, who) in enumerate(DEMO, 1):
            print("=" * 74)
            print(f"COMPLAINT {i}")
            print("=" * 74)
            print(f"RAW: {text}")
            run(text, who, provider=a.provider, model=a.model)
            print()
