"""
MODULE I — Intelligent Auto-Fill & Case Pre-Population Engine

Transforms unstructured victim speech, typed text, and OCR evidence into a
100% structured, pre-populated NCRP complaint payload ready for immediate
verification and registration.

Eliminates manual form filling by auto-mapping:
  1. Complainant Profile (User defaults or profile fallback)
  2. Incident Particulars (Category, Sub-category, Modus Operandi, Platforms, Datetime)
  3. Victim Transaction Records (Bank, Account Last 4, Amount, UTR, Date, Payment Mode)
  4. Suspect Destination Trail (Beneficiary UPI/Account, Recipient Bank, Suspect Phones)
  5. Suspect Entity Records (Name, Persona, Phone Numbers, Social Handles, Malicious Apps)

Provides a completion score, lists all fields auto-filled with provenance source,
and flags genuine missing critical fields for minimal follow-up.

USAGE:
    from modules.auto_fill import generate_autofill_payload

    payload = generate_autofill_payload(
        raw_text="On 17 Oct 2026, ₹25,000 was debited from my HDFC A/c ending 1234 via UPI UTR: 326712345678 to fraudster@paytm",
        user_profile={"name": "Rajesh Sharma", "phone": "9876543210", "city": "Pune", "state": "Maharashtra"}
    )
    print("Auto-filled Completion:", payload["completion_percentage"], "%")
"""

import os
import re
import sys
from datetime import datetime, date
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.entity_extractor import extract_entities_v2
from modules.mo_knowledge_base import match_mo, get_critical_fields


# Top-level NCRP Category umbrella mapping
NCRP_MAIN_CATEGORIES = {
    "Financial Fraud": [
        "UPI Related Frauds", "Internet Banking Related Fraud", "Debit/Credit Card Fraud / SIM Swap Fraud",
        "E-Wallet Related Fraud", "AePS Fraud", "Demat / Depository Fraud", "Online Job Fraud"
    ],
    "Cyber Crime Against Women & Children": [
        "Cyber Bullying / Stalking / Sexting"
    ],
    "Social Media & Impersonation Crime": [
        "Fake / Impersonating Profile", "Profile Hacking / Identity Theft", "Online Matrimonial Fraud",
        "Cheating by Impersonation"
    ],
    "Cyber Attacks & System Intrusions": [
        "Damage to Computer / Computer System", "Unauthorised Access / Data Breach",
        "Email Hacking", "Website Defacement / Hacking", "Tampering with Computer Source Document"
    ],
    "Cyber Terrorism & Unlawful Acts": [
        "Provocative Speech for Unlawful Acts", "Intimidating Email", "Email Phishing",
        "Impersonating Email (Business Email Compromise)"
    ]
}


def _resolve_top_category(sub_category: Optional[str]) -> str:
    """Resolve sub-category into top-level NCRP category umbrella."""
    if not sub_category:
        return "Financial Fraud"
    for main_cat, subs in NCRP_MAIN_CATEGORIES.items():
        if sub_category in subs:
            return main_cat
    return "Financial Fraud"


def generate_autofill_payload(
    raw_text: str,
    ocr_entities: Optional[Dict[str, Any]] = None,
    user_profile: Optional[Dict[str, Any]] = None,
    reference_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Generate a complete, pre-populated complaint form dictionary from raw text and evidence.

    Returns:
      - complainant: Dict[str, Any]
      - incident: Dict[str, Any]
      - transactions: List[Dict[str, Any]]
      - suspect_transactions: List[Dict[str, Any]]
      - suspects: List[Dict[str, Any]]
      - prefilled_fields: List[Dict[str, str]] (provenance tracker)
      - missing_critical_fields: List[str]
      - completion_percentage: float (0.0 to 100.0)
      - matched_mo: Optional[Dict[str, Any]]
    """
    user_profile = user_profile or {}
    ocr_entities = ocr_entities or {}

    # Step 1: Extract entities via NER v2
    extracted = extract_entities_v2(raw_text, ocr_entities=ocr_entities, reference_date=reference_date)

    # Step 2: Match Modus Operandi pattern
    mo_match = match_mo(raw_text, entities=extracted)

    prefilled_items: List[Dict[str, str]] = []

    def record_fill(field_name: str, value: Any, source: str):
        if value not in (None, "", [], "not supplied"):
            prefilled_items.append({
                "field": field_name,
                "value": str(value),
                "source": source
            })

    # -------------------------------------------------------------------------
    # 1. COMPLAINANT PROFILE
    # -------------------------------------------------------------------------
    complainant = {
        "title": user_profile.get("title", "Shri/Smt"),
        "name": user_profile.get("name", "not supplied"),
        "gender": user_profile.get("gender", "not supplied"),
        "dob": user_profile.get("dob", "not supplied"),
        "age": user_profile.get("age", "not supplied"),
        "phone": user_profile.get("phone") or (extracted["victim_phones"][0] if extracted["victim_phones"] else "not supplied"),
        "email": user_profile.get("email", "not supplied"),
        "address": user_profile.get("address", "not supplied"),
        "city": user_profile.get("city", "not supplied"),
        "district": user_profile.get("district", "not supplied"),
        "state": user_profile.get("state", "not supplied"),
        "pincode": user_profile.get("pincode", "not supplied"),
        "police_station": user_profile.get("police_station", "not supplied"),
        "relationship_with_victim": user_profile.get("relationship_with_victim", "Self"),
    }

    for k, v in complainant.items():
        if v != "not supplied":
            src = "User Profile" if k in user_profile else "Text / Speech NER"
            record_fill(f"complainant.{k}", v, src)

    # -------------------------------------------------------------------------
    # 2. INCIDENT PARTICULARS
    # -------------------------------------------------------------------------
    sub_category = mo_match["primary_ncrp_subcategory"] if mo_match else "UPI Related Frauds"
    category = _resolve_top_category(sub_category)
    mo_title = mo_match["name"] if mo_match else "Cyber Fraud"

    incident_date = extracted["date"] or date.today().isoformat()
    incident_time = datetime.now().strftime("%H:%M")
    incident_datetime = f"{incident_date} {incident_time}"

    platforms = extracted["platforms"] or (mo_match.get("common_platforms", []) if mo_match else ["Online / Digital"])

    incident = {
        "datetime": incident_datetime,
        "category": category,
        "sub_category_reported": sub_category,
        "modus_operandi": mo_title,
        "location": platforms,
        "delay_in_reporting": "No",
        "delay_reason": "N/A"
    }

    record_fill("incident.category", category, "NCRP Taxonomy Engine")
    record_fill("incident.sub_category_reported", sub_category, "MO-KB Pattern Match")
    record_fill("incident.modus_operandi", mo_title, "MO-KB Pattern Match")
    record_fill("incident.datetime", incident_datetime, "Entity Extractor / System Clock")
    record_fill("incident.location", ", ".join(platforms), "Entity Extractor (Platforms)")

    # -------------------------------------------------------------------------
    # 3. VICTIM TRANSACTIONS
    # -------------------------------------------------------------------------
    transactions: List[Dict[str, Any]] = []
    if extracted["amount"] or extracted["utr"] or extracted["bank_name"]:
        bank_val = extracted["bank_name"] or "Bank Account"
        acct_val = f"A/c ending {extracted['account_last4']}" if extracted["account_last4"] else "Primary Account"
        utr_val = extracted["utr"] or "Pending Bank Statement"
        amt_val = extracted["amount"] or 0
        date_val = extracted["date"] or incident_date

        tx_record = {
            "bank": bank_val,
            "account_no": acct_val,
            "transaction_id": utr_val,
            "amount": amt_val,
            "transaction_date": date_val,
            "payment_mechanism": "UPI" if ("UPI" in platforms or extracted["upi_id"]) else "Bank Transfer"
        }
        transactions.append(tx_record)

        record_fill("transactions[0].bank", bank_val, "Entity Extractor (Bank)")
        record_fill("transactions[0].account_no", acct_val, "Entity Extractor (Account)")
        record_fill("transactions[0].transaction_id", utr_val, "Entity Extractor (UTR / RRN)")
        record_fill("transactions[0].amount", amt_val, "Entity Extractor (Amount)")
        record_fill("transactions[0].transaction_date", date_val, "Entity Extractor (Date)")

    # -------------------------------------------------------------------------
    # 4. SUSPECT ACCOUNT & MONEY TRAIL
    # -------------------------------------------------------------------------
    suspect_transactions: List[Dict[str, Any]] = []
    if extracted["upi_id"]:
        suspect_tx = {
            "method": "UPI",
            "bank": extracted["upi_id"].split("@")[-1].upper(),
            "account_no": extracted["upi_id"],
            "transaction_id": extracted["utr"] or "Pending Bank Confirmation",
            "amount": extracted["amount"] or 0,
            "transaction_date": extracted["date"] or incident_date
        }
        suspect_transactions.append(suspect_tx)
        record_fill("suspect_transactions[0].account_no", extracted["upi_id"], "Entity Extractor (Beneficiary UPI)")

    # -------------------------------------------------------------------------
    # 5. SUSPECT ENTITY PROFILES
    # -------------------------------------------------------------------------
    suspects: List[Dict[str, Any]] = []
    suspect_phone_numbers = extracted["suspect_phones"]

    if suspect_phone_numbers:
        for idx, ph in enumerate(suspect_phone_numbers):
            s_name = extracted["suspect_persona"] or f"Unknown Suspect Caller #{idx+1}"
            suspect_entry = {
                "name": s_name,
                "id_type": "Mobile Phone Number",
                "id_number": ph,
                "address": "Under Investigation via Telecom CDR"
            }
            suspects.append(suspect_entry)
            record_fill(f"suspects[{idx}].phone", ph, "Entity Extractor (Phone)")
            if extracted["suspect_persona"]:
                record_fill(f"suspects[{idx}].persona", extracted["suspect_persona"], "Entity Extractor (Persona)")

    if extracted["upi_id"] and not any(s.get("id_number") == extracted["upi_id"] for s in suspects):
        suspect_entry = {
            "name": extracted["suspect_persona"] or "Beneficiary VPA Holder",
            "id_type": "UPI VPA Handle",
            "id_number": extracted["upi_id"],
            "address": "Lien Requested via PSP Bank"
        }
        suspects.append(suspect_entry)

    # -------------------------------------------------------------------------
    # 6. MISSING CRITICAL FIELDS CHECK
    # -------------------------------------------------------------------------
    critical_needed = []
    if mo_match:
        mo_critical = get_critical_fields(mo_match["mo_id"])
        if "utr" in mo_critical and not extracted["utr"]:
            critical_needed.append("12-digit UTR / Transaction Reference Number")
        if "beneficiary_upi_or_account" in mo_critical and not extracted["upi_id"]:
            critical_needed.append("Suspect UPI ID or Beneficiary Bank Account")
        if "suspect_phone" in mo_critical and not extracted["suspect_phones"]:
            critical_needed.append("Suspect Caller / Sender Mobile Number")
        if "apk_file_or_link" in mo_critical and not extracted["app_names"] and ("apk" in raw_text.lower() or "app" in raw_text.lower()):
            critical_needed.append("Name or link of APK / Remote Access Application")

    if complainant["name"] == "not supplied":
        critical_needed.append("Complainant Full Name")
    if complainant["phone"] == "not supplied":
        critical_needed.append("Complainant Contact Mobile Number")

    # -------------------------------------------------------------------------
    # 7. COMPLETION SCORING
    # -------------------------------------------------------------------------
    total_key_fields = 10
    filled_count = len(prefilled_items)
    completion_percentage = round(min(100.0, (filled_count / total_key_fields) * 100.0), 1)

    return {
        "complainant": complainant,
        "incident": incident,
        "transactions": transactions,
        "suspect_transactions": suspect_transactions,
        "suspects": suspects,
        "extracted_entities": extracted,
        "matched_mo": mo_match,
        "prefilled_fields": prefilled_items,
        "prefilled_count": filled_count,
        "missing_critical_fields": critical_needed,
        "completion_percentage": completion_percentage,
        "requires_followup": len(critical_needed) > 0
    }


# ---------------------------------------------------------------------------
# Self-Check & Testing CLI
# ---------------------------------------------------------------------------

def _run_self_test() -> bool:
    """Run automated unit verification for Auto-Fill Engine."""
    print("[Auto-Fill] Running pre-population verification test...")

    sample_complaint = (
        "On 17 Oct 2026, ₹25,000 was fraudulently debited from my HDFC Bank account (A/c ending 1234) "
        "via UPI without my authorization. UTR: 326712345678 to fraudster@paytm. Scammer called from 9876543210 "
        "claiming electricity bill disconnect."
    )
    user_prof = {
        "name": "Pranit Chavan",
        "city": "Pune",
        "state": "Maharashtra",
        "phone": "9123456789"
    }

    res = generate_autofill_payload(sample_complaint, user_profile=user_prof)

    assert res["complainant"]["name"] == "Pranit Chavan"
    assert res["incident"]["sub_category_reported"] == "UPI Related Frauds"
    assert len(res["transactions"]) == 1
    assert res["transactions"][0]["amount"] == 25000
    assert res["transactions"][0]["transaction_id"] == "326712345678"
    assert res["transactions"][0]["bank"] == "HDFC"
    assert res["suspect_transactions"][0]["account_no"] == "fraudster@paytm"
    assert len(res["suspects"]) >= 1
    assert res["completion_percentage"] >= 80.0

    print(f"  [PASS] Auto-filled {res['prefilled_count']} fields cleanly.")
    print(f"  [PASS] Form Completion: {res['completion_percentage']}%")
    print(f"  [PASS] Modus Operandi: {res['incident']['modus_operandi']}")
    print(f"  [PASS] Missing Gaps remaining: {res['missing_critical_fields']}")
    return True


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv or len(sys.argv) == 1:
        success = _run_self_test()
        sys.exit(0 if success else 1)
    else:
        q = " ".join(sys.argv[1:])
        payload = generate_autofill_payload(q)
        print("Pre-filled Form Data:")
        import json
        print(json.dumps(payload, indent=2, ensure_ascii=False))
