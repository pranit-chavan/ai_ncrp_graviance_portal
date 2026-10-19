"""
MODULE L — Cross-Case Pattern & Criminal Syndicate Correlation Engine

Investigator Decision-Support System:
Uncovers multi-complaint scam campaigns by correlating digital fingerprints across
isolated grievances:
  1. Exact Suspect Phone Numbers (Normalized 10-digit Indian mobiles)
  2. Suspect UPI VPA Handles (e.g., fraudster@paytm across multiple victims)
  3. Destination Bank Accounts & Beneficiary Trails
  4. Modus Operandi (MO) & Regional Scam Campaigns
  5. Shared Malicious APKs, Phishing Domains, or Social Media Handles

FEATURES:
  - SQLite Embedded Graph Index (`case_index.db`) — lightweight, instant, offline
  - Automatic Syndicate Dossier Compilation (Combined losses, victims, phone/UPI footprint)
  - Inter-jurisdictional Linking (Alerts officers when the same suspect strikes multiple cities)
  - Automated Lead Scoring for Investigating Officers

USAGE:
    from modules.pattern_engine import find_linked_cases, build_suspect_dossier, sync_all_case_files

    sync_all_case_files("case_files")
    links = find_linked_cases("NCRP/2026/074454")
    print("Linked Complaints:", links["total_cases_linked"])
    print("Total Defrauded:", links["total_amount_defrauded"])
"""

import os
import re
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "case_index.db")


# =============================================================================
# 1. DATABASE SCHEMA & INITIALIZATION
# =============================================================================

@contextmanager
def get_connection(db_path: str = _DEFAULT_DB_PATH):
    """Open a thread-safe connection to the local SQLite case index and ensure it closes."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = _DEFAULT_DB_PATH):
    """Initialize relational index schema for cross-case correlation."""
    with get_connection(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT UNIQUE NOT NULL,
                citizen_name TEXT,
                citizen_phone TEXT,
                citizen_city TEXT,
                citizen_state TEXT,
                category TEXT,
                sub_category TEXT,
                mo_id TEXT,
                mo_name TEXT,
                amount REAL DEFAULT 0,
                utr TEXT,
                incident_date TEXT,
                registered_at TEXT,
                json_path TEXT
            );

            CREATE TABLE IF NOT EXISTS identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_reference TEXT NOT NULL,
                id_type TEXT NOT NULL,         -- 'PHONE', 'UPI', 'ACCOUNT', 'UTR', 'APK', 'PERSONA'
                raw_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                FOREIGN KEY (case_reference) REFERENCES cases(reference) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_cases_ref ON cases(reference);
            CREATE INDEX IF NOT EXISTS idx_cases_mo ON cases(mo_id);
            CREATE INDEX IF NOT EXISTS idx_identifiers_lookup ON identifiers(id_type, normalized_value);
            CREATE INDEX IF NOT EXISTS idx_identifiers_case ON identifiers(case_reference);
        """)


# =============================================================================
# 2. IDENTIFIER NORMALIZATION
# =============================================================================

def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone to 10-digit Indian standard."""
    if not phone:
        return None
    clean = re.sub(r"[^\d]", "", str(phone))
    if len(clean) >= 10:
        clean = clean[-10:]
        if clean[0] in "6789":
            return clean
    return None


def normalize_upi(upi: str) -> Optional[str]:
    """Normalize UPI handle."""
    if not upi or "@" not in str(upi):
        return None
    return str(upi).strip().lower()


def normalize_account(acct: str) -> Optional[str]:
    """Normalize account string."""
    if not acct:
        return None
    clean = re.sub(r"[^\w]", "", str(acct).lower())
    return clean if len(clean) >= 4 else None


# =============================================================================
# 3. CASE INDEXING PIPELINE
# =============================================================================

def index_case(case_data: Dict[str, Any], json_path: Optional[str] = None, db_path: str = _DEFAULT_DB_PATH):
    """Index a single case file into the SQLite cross-case correlation graph."""
    init_db(db_path)
    ref = case_data.get("reference")
    if not ref:
        return

    c = case_data.get("complainant", {})
    inc = case_data.get("incident", {})
    txns = case_data.get("transactions", [])
    stxns = case_data.get("suspect_transactions", [])
    suspects = case_data.get("suspects", [])
    entities = case_data.get("extracted_entities", {})

    # Extract primary transaction amount and UTR
    total_amount = 0.0
    primary_utr = None
    for t in txns:
        try:
            amt = float(t.get("amount", 0))
            total_amount += amt
        except (ValueError, TypeError):
            pass
        if not primary_utr and t.get("transaction_id"):
            primary_utr = str(t.get("transaction_id"))
        elif not primary_utr and t.get("utr_number"):
            primary_utr = str(t.get("utr_number"))

    if total_amount == 0 and entities.get("amount"):
        try:
            total_amount = float(entities["amount"])
        except Exception:
            pass

    if not primary_utr and entities.get("utr"):
        primary_utr = str(entities["utr"])

    mo_id = case_data.get("mo_id") or ""
    mo_name = inc.get("modus_operandi", "")

    with get_connection(db_path) as conn:
        # Upsert case record
        conn.execute("""
            INSERT INTO cases (
                reference, citizen_name, citizen_phone, citizen_city, citizen_state,
                category, sub_category, mo_id, mo_name, amount, utr, incident_date,
                registered_at, json_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(reference) DO UPDATE SET
                citizen_name=excluded.citizen_name,
                citizen_phone=excluded.citizen_phone,
                citizen_city=excluded.citizen_city,
                citizen_state=excluded.citizen_state,
                category=excluded.category,
                sub_category=excluded.sub_category,
                mo_id=excluded.mo_id,
                mo_name=excluded.mo_name,
                amount=excluded.amount,
                utr=excluded.utr,
                incident_date=excluded.incident_date,
                registered_at=excluded.registered_at,
                json_path=excluded.json_path;
        """, (
            ref,
            c.get("name", "not supplied"),
            c.get("phone", "not supplied"),
            c.get("city", "not supplied"),
            c.get("state", "not supplied"),
            inc.get("category", "Financial Fraud"),
            inc.get("sub_category_reported") or case_data.get("classification", {}).get("sub_category", "UPI Related Frauds"),
            mo_id,
            mo_name,
            total_amount,
            primary_utr or "",
            inc.get("datetime", ""),
            case_data.get("generated_at", datetime.now().isoformat()),
            json_path or ""
        ))

        # Clear existing identifiers for this case
        conn.execute("DELETE FROM identifiers WHERE case_reference = ?", (ref,))

        # Collect suspect identifiers
        identifiers_to_insert: List[Tuple[str, str, str, str]] = []

        def add_id(id_type: str, raw_val: str, norm_val: Optional[str]):
            if norm_val and (ref, id_type, str(raw_val), norm_val) not in identifiers_to_insert:
                identifiers_to_insert.append((ref, id_type, str(raw_val), norm_val))

        # Suspect phones
        for s in suspects:
            ph = s.get("phone") or (s.get("id_number") if s.get("id_type") == "Mobile Phone Number" else None)
            if ph:
                add_id("PHONE", ph, normalize_phone(ph))
            if s.get("account") and "@" in str(s.get("account")):
                add_id("UPI", s["account"], normalize_upi(s["account"]))
            if s.get("name") and s["name"] != "unknown":
                add_id("PERSONA", s["name"], s["name"].strip().lower())

        # Suspect phones from entities
        for ph in entities.get("suspect_phones", []):
            add_id("PHONE", ph, normalize_phone(ph))

        # Suspect UPI from transactions and entities
        for st in stxns:
            acct = st.get("account_no") or st.get("account_number")
            if acct and "@" in str(acct):
                add_id("UPI", acct, normalize_upi(acct))
            elif acct:
                add_id("ACCOUNT", acct, normalize_account(acct))

        if entities.get("upi_id"):
            add_id("UPI", entities["upi_id"], normalize_upi(entities["upi_id"]))

        # Primary UTR
        if primary_utr:
            add_id("UTR", primary_utr, primary_utr.strip())

        # Insert identifiers
        if identifiers_to_insert:
            conn.executemany("""
                INSERT INTO identifiers (case_reference, id_type, raw_value, normalized_value)
                VALUES (?, ?, ?, ?)
            """, identifiers_to_insert)


def sync_all_case_files(dir_path: str = "case_files", db_path: str = _DEFAULT_DB_PATH) -> int:
    """Scan case files directory and index all valid JSON cases."""
    if not os.path.exists(dir_path):
        return 0
    count = 0
    for fname in os.listdir(dir_path):
        if fname.endswith(".json"):
            fpath = os.path.join(dir_path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    index_case(data, json_path=fpath, db_path=db_path)
                    count += 1
            except Exception as e:
                pass
    return count


# =============================================================================
# 4. CROSS-CASE CORRELATION & LINK ANALYSIS
# =============================================================================

def find_linked_cases(case_ref_or_dict: Any, db_path: str = _DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Given a case reference or case dictionary, find all other linked cases
    sharing suspect identifiers (phone, UPI, account, UTR) or campaign patterns.

    Returns:
      - target_reference: str
      - total_cases_linked: int
      - total_amount_defrauded: float (combined across target + linked cases)
      - linked_cases: List[Dict] with match reason, strength, and case particulars
      - shared_identifiers: List of common phones, UPI handles, etc.
      - geographic_spread: List of affected cities
      - syndicate_summary: Plain English synopsis for the Investigating Officer
    """
    init_db(db_path)

    if isinstance(case_ref_or_dict, dict):
        ref = case_ref_or_dict.get("reference", "")
        # Index on the fly if not already indexed
        index_case(case_ref_or_dict, db_path=db_path)
    else:
        ref = str(case_ref_or_dict)

    with get_connection(db_path) as conn:
        # 1. Fetch target case details
        target_case = conn.execute("SELECT * FROM cases WHERE reference = ?", (ref,)).fetchone()
        target_amount = target_case["amount"] if target_case else 0.0

        # 2. Fetch all identifiers for target case
        target_ids = conn.execute("""
            SELECT id_type, normalized_value, raw_value
            FROM identifiers
            WHERE case_reference = ?
        """, (ref,)).fetchall()

        if not target_ids:
            return {
                "target_reference": ref,
                "total_cases_linked": 0,
                "total_amount_defrauded": target_amount,
                "linked_cases": [],
                "shared_identifiers": [],
                "geographic_spread": [target_case["citizen_city"]] if target_case and target_case["citizen_city"] else [],
                "syndicate_summary": "No cross-case linkages detected yet. This appears to be an isolated incident or first recorded complaint."
            }

        # 3. Query all other cases sharing ANY identifier
        matches: Dict[str, Dict[str, Any]] = {}
        shared_ids_set = set()

        for tid in target_ids:
            id_type, norm_val = tid["id_type"], tid["normalized_value"]
            hits = conn.execute("""
                SELECT c.*, i.id_type, i.raw_value
                FROM identifiers i
                JOIN cases c ON c.reference = i.case_reference
                WHERE i.id_type = ? AND i.normalized_value = ? AND i.case_reference != ?
            """, (id_type, norm_val, ref)).fetchall()

            for hit in hits:
                hit_ref = hit["reference"]
                shared_ids_set.add(f"{id_type}: {norm_val}")

                weight = 0.95 if id_type in ("PHONE", "UPI", "ACCOUNT") else 0.85
                reason_str = f"Matches suspect {id_type.lower()}: '{tid['raw_value']}'"

                if hit_ref not in matches:
                    matches[hit_ref] = {
                        "reference": hit["reference"],
                        "citizen_name": hit["citizen_name"],
                        "citizen_city": hit["citizen_city"],
                        "citizen_state": hit["citizen_state"],
                        "sub_category": hit["sub_category"],
                        "amount": hit["amount"],
                        "incident_date": hit["incident_date"],
                        "match_reasons": [reason_str],
                        "confidence_score": weight
                    }
                else:
                    if reason_str not in matches[hit_ref]["match_reasons"]:
                        matches[hit_ref]["match_reasons"].append(reason_str)
                        matches[hit_ref]["confidence_score"] = min(1.0, matches[hit_ref]["confidence_score"] + 0.1)

        linked_list = list(matches.values())
        linked_list.sort(key=lambda x: (x["confidence_score"], x["amount"]), reverse=True)

        total_linked_amount = target_amount + sum(item["amount"] for item in linked_list)
        geo_cities = list(set([target_case["citizen_city"]] + [item["citizen_city"] for item in linked_list if item["citizen_city"] not in (None, "", "not supplied")])) if target_case else []

        # Build syndicate executive summary for IO
        if linked_list:
            syn_summary = (
                f"🚨 **ORGANIZED SCAM CAMPAIGN DETECTED**: This grievance is connected to {len(linked_list)} "
                f"other registered cybercrime complaints across {len(geo_cities)} cities ({', '.join(geo_cities[:4])}). "
                f"Total cumulative loss siphoned by this suspect network: ₹{total_linked_amount:,.2f}. "
                f"Shared indicators: {', '.join(list(shared_ids_set)[:3])}."
            )
        else:
            syn_summary = "No cross-case linkages detected yet with existing registered records."

        return {
            "target_reference": ref,
            "total_cases_linked": len(linked_list),
            "total_amount_defrauded": total_linked_amount,
            "linked_cases": linked_list,
            "shared_identifiers": list(shared_ids_set),
            "geographic_spread": geo_cities,
            "syndicate_summary": syn_summary
        }


# =============================================================================
# 5. SUSPECT CRIMINAL DOSSIER BUILDER
# =============================================================================

def build_suspect_dossier(identifier_value: str, db_path: str = _DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Generate an intelligence dossier on a suspect phone, UPI ID, or account number
    across all complaints in the database.
    """
    init_db(db_path)
    clean_val = str(identifier_value).strip()
    norm_phone = normalize_phone(clean_val)
    norm_upi = normalize_upi(clean_val)

    with get_connection(db_path) as conn:
        cases_rows = conn.execute("""
            SELECT DISTINCT c.*
            FROM identifiers i
            JOIN cases c ON c.reference = i.case_reference
            WHERE i.normalized_value = ? OR i.normalized_value = ? OR i.raw_value = ?
        """, (norm_phone or clean_val, norm_upi or clean_val, clean_val)).fetchall()

        if not cases_rows:
            return {"found": False, "identifier": identifier_value, "message": "No complaints recorded against this suspect."}

        case_refs = [r["reference"] for r in cases_rows]
        total_defrauded = sum(r["amount"] for r in cases_rows)
        cities = list(set(r["citizen_city"] for r in cases_rows if r["citizen_city"] not in ("not supplied", "")))
        mo_names = list(set(r["mo_name"] for r in cases_rows if r["mo_name"]))

        # Get all co-occurring identifiers used by this suspect
        placeholders = ",".join("?" * len(case_refs))
        co_ids = conn.execute(f"""
            SELECT DISTINCT id_type, raw_value
            FROM identifiers
            WHERE case_reference IN ({placeholders})
        """, case_refs).fetchall()

        phones = list(set(r["raw_value"] for r in co_ids if r["id_type"] == "PHONE"))
        upis = list(set(r["raw_value"] for r in co_ids if r["id_type"] == "UPI"))
        accounts = list(set(r["raw_value"] for r in co_ids if r["id_type"] == "ACCOUNT"))

        return {
            "found": True,
            "suspect_key": identifier_value,
            "total_complaints": len(cases_rows),
            "total_amount_defrauded": total_defrauded,
            "total_amount_formatted": f"₹{total_defrauded:,.2f}",
            "linked_case_references": case_refs,
            "associated_phones": phones,
            "associated_upi_vpash": upis,
            "associated_bank_accounts": accounts,
            "victim_geographies": cities,
            "primary_modi_operandi": mo_names,
            "threat_level": "CRITICAL" if len(cases_rows) >= 5 or total_defrauded >= 500000 else "HIGH" if len(cases_rows) >= 2 else "MODERATE"
        }


# ---------------------------------------------------------------------------
# Self-Check & Testing CLI
# ---------------------------------------------------------------------------

def _run_self_test() -> bool:
    """Run automated verification of Pattern Engine cross-case correlation."""
    print("[Pattern-Engine] Running multi-case correlation test...")

    test_db = os.path.join(_PROJECT_ROOT, "test_pattern_index.db")
    if os.path.exists(test_db):
        os.remove(test_db)

    # 1. Create two complaints sharing the same suspect UPI and Phone
    case1 = {
        "reference": "NCRP/2026/000101",
        "complainant": {"name": "Victim One", "city": "Pune", "phone": "9111111111"},
        "incident": {"category": "Financial Fraud", "sub_category_reported": "UPI Related Frauds", "modus_operandi": "Electricity Bill Scam"},
        "transactions": [{"amount": 30000.0, "transaction_id": "UTR101010101010"}],
        "suspects": [{"phone": "9876543210", "name": "Fake MSEDCL"}],
        "extracted_entities": {"upi_id": "fraudster99@paytm", "amount": 30000.0}
    }

    case2 = {
        "reference": "NCRP/2026/000102",
        "complainant": {"name": "Victim Two", "city": "Mumbai", "phone": "9222222222"},
        "incident": {"category": "Financial Fraud", "sub_category_reported": "UPI Related Frauds", "modus_operandi": "Electricity Bill Scam"},
        "transactions": [{"amount": 45000.0, "transaction_id": "UTR202020202020"}],
        "suspects": [{"phone": "9876543210", "name": "Electricity Dept Caller"}],
        "extracted_entities": {"upi_id": "fraudster99@paytm", "amount": 45000.0}
    }

    index_case(case1, db_path=test_db)
    index_case(case2, db_path=test_db)

    # 2. Correlate from Case 1
    links = find_linked_cases("NCRP/2026/000101", db_path=test_db)
    assert links["total_cases_linked"] == 1
    assert links["linked_cases"][0]["reference"] == "NCRP/2026/000102"
    assert links["total_amount_defrauded"] == 75000.0
    assert "9876543210" in str(links["shared_identifiers"]) or "fraudster99@paytm" in str(links["shared_identifiers"])

    # 3. Build Suspect Dossier
    dossier = build_suspect_dossier("9876543210", db_path=test_db)
    assert dossier["found"] is True
    assert dossier["total_complaints"] == 2
    assert dossier["total_amount_defrauded"] == 75000.0

    print("  [PASS] Successfully indexed and linked two distinct grievances.")
    print(f"  [PASS] Aggregate loss computed correctly (Rs. {links['total_amount_defrauded']:,.2f}).")
    print("  [PASS] Suspect dossier compiled multi-city victim footprint.")

    # Cleanup test db
    if os.path.exists(test_db):
        os.remove(test_db)
    return True


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv or len(sys.argv) == 1:
        success = _run_self_test()
        # Also sync current case_files
        synced = sync_all_case_files()
        print(f"[Pattern-Engine] Synced {synced} real case files into primary case_index.db.")
        sys.exit(0 if success else 1)
    elif sys.argv[1] == "--sync":
        c = sync_all_case_files()
        print(f"Synced {c} cases into index.")
    elif sys.argv[1] == "--dossier" and len(sys.argv) > 2:
        dos = build_suspect_dossier(sys.argv[2])
        print(json.dumps(dos, indent=2, ensure_ascii=False))
    else:
        ref_arg = sys.argv[1]
        res = find_linked_cases(ref_arg)
        print(json.dumps(res, indent=2, ensure_ascii=True))
