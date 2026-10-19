"""
MODULE M — Statutory Investigation Document Generator

Investigator Automation Suite:
Generates certified, pre-filled procedural notices and court-ready documents under:
  - Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS, Act No. 46 of 2023)
  - Information Technology Act, 2000 (Act No. 21 of 2000 as amended)
  - Bharatiya Sakshya Adhiniyam, 2023 (BSA, Act No. 47 of 2023)

AVAILABLE TEMPLATES:
  1. BANK_FREEZE_NOTICE:
     Section 91 BNSS 2023 & RBI Mandate requisition to Beneficiary Bank for Immediate Debit Lien
  2. TELECOM_CDR_NOTICE:
     Section 91 BNSS 2023 requisition to Telecom Service Provider for CDR, CAF, IMEI & Tower Logs
  3. PLATFORM_PRESERVATION_NOTICE:
     Section 79(3)(b) IT Act & Sec 91 BNSS 2023 Preservation Order to WhatsApp / Meta / Telegram
  4. BSA_63_CERTIFICATE:
     Section 63 BSA 2023 Mandatory Digital Evidence Certificate for Court Admissibility
  5. CHARGE_SHEET_SYNOPSIS:
     Section 193 BNSS 2023 Investigation Report & Charge-Sheet Draft Synopsis

USAGE:
    from modules.doc_generator import generate_investigation_document, list_available_templates

    doc = generate_investigation_document(
        doc_type="BANK_FREEZE_NOTICE",
        case_data=case_record,
        io_name="Inspector R. K. Patil",
        police_station="Cyber Crime Police Station, Pune"
    )
    print(doc["document_text"])
"""

import os
import sys
import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.legal_mapping import map_sections


DOCUMENT_TEMPLATES = {
    "BANK_FREEZE_NOTICE": {
        "title": "Requisition for Immediate Debit Lien & Transaction Trail (Section 91 BNSS 2023)",
        "statute": "Section 91, Bharatiya Nagarik Suraksha Sanhita, 2023 & RBI Master Circular on Fraud Risk Management",
        "recipient_type": "Nodal Officer / Fraud Risk Management (FRM) Cell, Beneficiary Bank / UPI PSP",
        "urgency": "IMMEDIATE / GOLDEN HOUR PRIORITY"
    },
    "TELECOM_CDR_NOTICE": {
        "title": "Requisition for Call Detail Records (CDR), CAF & Tower Locations (Section 91 BNSS 2023)",
        "statute": "Section 91, Bharatiya Nagarik Suraksha Sanhita, 2023 & Indian Telegraph Act, 1885",
        "recipient_type": "Nodal Officer, Telecom Service Provider (Jio / Airtel / Vi / BSNL)",
        "urgency": "HIGH PRIORITY (CRIMINAL INVESTIGATION)"
    },
    "PLATFORM_PRESERVATION_NOTICE": {
        "title": "Emergency Digital Record Preservation Order (Section 79(3)(b) IT Act & Sec 91 BNSS 2023)",
        "statute": "Section 79(3)(b), Information Technology Act 2000 & Section 91 BNSS 2023",
        "recipient_type": "Grievance Officer / Law Enforcement Response Team, Social Media Intermediary",
        "urgency": "URGENT (WITHIN 24 HOURS OF RECEIPT)"
    },
    "BSA_63_CERTIFICATE": {
        "title": "Certificate of Admissibility for Electronic Records (Section 63 Bharatiya Sakshya Adhiniyam 2023)",
        "statute": "Section 63(4), Bharatiya Sakshya Adhiniyam, 2023 (Act No. 47 of 2023)",
        "recipient_type": "Learned Judicial Magistrate / Competent Court of Jurisdiction",
        "urgency": "STATUTORY JUDICIAL FILING"
    },
    "CHARGE_SHEET_SYNOPSIS": {
        "title": "Police Investigation Report & Charge-Sheet Draft Synopsis (Section 193 BNSS 2023)",
        "statute": "Section 193, Bharatiya Nagarik Suraksha Sanhita, 2023",
        "recipient_type": "Court of Competent Jurisdiction",
        "urgency": "STATUTORY CHARGE-SHEET STAGE"
    }
}


def list_available_templates() -> List[Dict[str, str]]:
    """Return list of available statutory document templates."""
    return [{"doc_type": k, "title": v["title"], "statute": v["statute"]} for k, v in DOCUMENT_TEMPLATES.items()]


def generate_investigation_document(
    doc_type: str,
    case_data: Dict[str, Any],
    io_name: str = "Investigating Officer",
    io_designation: str = "Inspector of Police (Cyber Crime)",
    police_station: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate an official statutory procedural document for an investigating officer.

    Parameters:
      doc_type: One of DOCUMENT_TEMPLATES keys
      case_data: Complete case file dictionary
      io_name: Name of the Investigating Officer
      io_designation: Official police designation / rank
      police_station: Cyber police station name / jurisdiction
    """
    doc_type_upper = doc_type.strip().upper()
    if doc_type_upper not in DOCUMENT_TEMPLATES:
        raise ValueError(f"Unknown document type '{doc_type}'. Available: {list(DOCUMENT_TEMPLATES.keys())}")

    meta = DOCUMENT_TEMPLATES[doc_type_upper]
    ref = case_data.get("reference", f"NCRP/{datetime.now().year}/XXXXXX")
    c = case_data.get("complainant", {})
    inc = case_data.get("incident", {})
    txns = case_data.get("transactions", [])
    stxns = case_data.get("suspect_transactions", [])
    suspects = case_data.get("suspects", [])
    ps_name = police_station or c.get("police_station") or "Cyber Crime Police Station"

    # Extract primary transaction identifiers
    utr_val = "Not Recorded"
    amount_val = "Not Recorded"
    victim_bank = "Complainant Bank"
    suspect_acc = "Under Tracing"
    suspect_phone = "Under Tracing"

    for t in txns:
        if t.get("transaction_id") or t.get("utr_number"):
            utr_val = str(t.get("transaction_id") or t.get("utr_number"))
        if t.get("amount"):
            amount_val = f"Rs. {t.get('amount'):,}" if isinstance(t.get('amount'), (int, float)) else str(t.get('amount'))
        if t.get("bank") or t.get("bank_name"):
            victim_bank = t.get("bank") or t.get("bank_name")

    for st in stxns:
        acc = st.get("account_no") or st.get("account_number")
        if acc:
            suspect_acc = str(acc)

    for s in suspects:
        ph = s.get("phone") or (s.get("id_number") if s.get("id_type") == "Mobile Phone Number" else None)
        if ph:
            suspect_phone = str(ph)
        if suspect_acc == "Under Tracing" and s.get("account"):
            suspect_acc = str(s.get("account"))

    # Resolve legal sections
    sub_cat = inc.get("sub_category_reported") or case_data.get("classification", {}).get("sub_category", "UPI Related Frauds")
    try:
        sections_dict = map_sections(sub_cat, complainant_age=c.get("age"))
        bns_sections = ", ".join(f"Section {s['section']} BNS" for s in sections_dict.get("bns", []))
        it_sections = ", ".join(f"Section {s['section']} IT Act" for s in sections_dict.get("it_act", []))
        combined_sections = f"{bns_sections}, {it_sections}".strip(", ")
    except Exception:
        combined_sections = "Section 318(4) BNS 2023, Section 66D IT Act 2000"

    today_str = date.today().strftime("%d-%m-%Y")

    # Generate document text based on doc_type
    if doc_type_upper == "BANK_FREEZE_NOTICE":
        doc_text = _build_bank_freeze_notice(
            ref=ref, today_str=today_str, ps_name=ps_name, io_name=io_name,
            io_designation=io_designation, c_name=c.get("name", "Victim"),
            victim_bank=victim_bank, amount_val=amount_val, utr_val=utr_val,
            suspect_acc=suspect_acc, combined_sections=combined_sections,
            incident_date=inc.get("datetime", today_str)
        )
    elif doc_type_upper == "TELECOM_CDR_NOTICE":
        doc_text = _build_telecom_cdr_notice(
            ref=ref, today_str=today_str, ps_name=ps_name, io_name=io_name,
            io_designation=io_designation, suspect_phone=suspect_phone,
            combined_sections=combined_sections, incident_date=inc.get("datetime", today_str)
        )
    elif doc_type_upper == "PLATFORM_PRESERVATION_NOTICE":
        doc_text = _build_platform_preservation_notice(
            ref=ref, today_str=today_str, ps_name=ps_name, io_name=io_name,
            io_designation=io_designation, suspect_phone=suspect_phone,
            suspect_acc=suspect_acc, combined_sections=combined_sections
        )
    elif doc_type_upper == "BSA_63_CERTIFICATE":
        doc_text = _build_bsa_63_certificate(
            ref=ref, today_str=today_str, ps_name=ps_name, io_name=io_name,
            io_designation=io_designation, c_name=c.get("name", "Victim"),
            utr_val=utr_val, amount_val=amount_val
        )
    else:  # CHARGE_SHEET_SYNOPSIS
        doc_text = _build_charge_sheet_synopsis(
            ref=ref, today_str=today_str, ps_name=ps_name, io_name=io_name,
            io_designation=io_designation, c_name=c.get("name", "Victim"),
            amount_val=amount_val, utr_val=utr_val, suspect_phone=suspect_phone,
            suspect_acc=suspect_acc, combined_sections=combined_sections,
            mo_title=inc.get("modus_operandi", "Cyber Crime Incident"),
            narrative=case_data.get("complaint", {}).get("standardised_narrative") or inc.get("modus_operandi", "")
        )

    return {
        "doc_type": doc_type_upper,
        "title": meta["title"],
        "statute": meta["statute"],
        "recipient": meta["recipient_type"],
        "urgency": meta["urgency"],
        "case_reference": ref,
        "generated_date": today_str,
        "document_text": doc_text
    }


# =============================================================================
# DOCUMENT BUILDERS
# =============================================================================

def _build_bank_freeze_notice(ref, today_str, ps_name, io_name, io_designation, c_name, victim_bank, amount_val, utr_val, suspect_acc, combined_sections, incident_date) -> str:
    return f"""OFFICE OF THE INVESTIGATING OFFICER
CYBER CRIME POLICE STATION, {ps_name.upper()}
GOVERNMENT OF INDIA / STATE POLICE

Dispatch No: CR/{ref.replace('/', '-')}/BNSS-91/BANK
Date: {today_str}
Operational Priority: IMMEDIATE (CRIMINAL PROCEEDINGS / GOLDEN HOUR)

TO,
The Nodal Officer / Head (Fraud Risk Management Cell),
Concerned Beneficiary Bank / Payment Service Provider (PSP) / NPCI.

SUBJECT: REQUISITION UNDER SECTION 91 OF BHARATIYA NAGARIK SURAKSHA SANHITA (BNSS) 2023
         FOR IMMEDIATE DEBIT LIEN & SUBMISSION OF COMPLETE ACCOUNT TRANSACTION TRAIL.

CASE CRIME REFERENCE : {ref}
APPLICABLE OFFENCES  : {combined_sections}
COMPLAINANT          : {c_name}

Sir/Madam,

1. WHEREAS, an official investigation has been instituted at this Police Station into a cognizable cyber offence reported under {combined_sections}, wherein valuable funds totaling {amount_val} were dishonestly and fraudulently siphoned from the account of the complainant ({victim_bank}) into your bank's beneficiary account / UPI VPA.

2. PARTICULARS OF DISHONEST FINANCIAL DEBIT:
   - Unique Transaction Reference (UTR / RRN) : {utr_val}
   - Amount Debited                           : {amount_val}
   - Date & Time of Incident                 : {incident_date}
   - Beneficiary Account / UPI VPA            : {suspect_acc}

3. NOW THEREFORE, by virtue of statutory powers conferred under Section 91 of the Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) and the Master Directions of the Reserve Bank of India on Fraud Risk Management, you are HEREBY DIRECTED TO:
   a. Immediately place an unreserved DEBIT LIEN / FREEZE on the suspect beneficiary account / UPI handle: {suspect_acc} to the extent of {amount_val} or current credit balance, whichever is higher, to prevent onward layering.
   b. Provide complete Customer Acquisition Form (CAF), KYC documents, verified mobile number, and registered address of the beneficiary account holder within 24 hours.
   c. Furnish the complete bank statement of the beneficiary account for the period covering 7 days prior and 7 days subsequent to the transaction, showing subsequent transfer/ATM withdrawal legs.

4. Failure to comply with this statutory requisition within the stipulated time frame shall attract penal proceedings under Section 223 of the Bharatiya Nyaya Sanhita, 2023 (Disobedience to order duly promulgated by public servant).

Given under my hand and official seal on this {today_str}.

[OFFICIAL SEAL]

____________________________________
({io_name})
{io_designation}
{ps_name}
Email: cybercell@{ps_name.lower().replace(' ', '')}.gov.in
"""


def _build_telecom_cdr_notice(ref, today_str, ps_name, io_name, io_designation, suspect_phone, combined_sections, incident_date) -> str:
    return f"""OFFICE OF THE INVESTIGATING OFFICER
CYBER CRIME POLICE STATION, {ps_name.upper()}

Dispatch No: CR/{ref.replace('/', '-')}/BNSS-91/LE-TEL
Date: {today_str}

TO,
The Nodal Officer (Law Enforcement Cell),
Concerned Telecom Service Provider (TSP).

SUBJECT: STATUTORY REQUISITION UNDER SECTION 91 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023
         FOR CALL DETAIL RECORDS (CDR), SUBSCRIBER CAF, AND CELL TOWER IDENTIFICATION.

CRIME REFERENCE: {ref}
PENAL SECTIONS : {combined_sections}
TARGET MOBILE  : {suspect_phone}

Sir/Madam,

WHEREAS, a criminal investigation has been initiated into an organized cyber fraud and impersonation syndicate operating via mobile communication number: {suspect_phone}.

In exercise of the powers vested under Section 91 of Bharatiya Nagarik Suraksha Sanhita (BNSS) 2023, you are strictly required to produce the following electronic records in password-protected digital format within forty-eight (48) hours of receipt:

1. Certified Customer Application Form (CAF) along with uploaded proof of identity (PoI) and proof of address (PoA) submitted at the time of SIM activation.
2. Complete Call Detail Records (CDR) including incoming/outgoing voice calls and SMS logs for the period 30 days prior to {incident_date} to date, with First Cell ID, Last Cell ID, and Azimuth coordinates.
3. IMEI history associated with the target MSISDN and all other SIM cards inserted into the said IMEI handset during the last 90 days.
4. GPRS / IP Data Usage Records (IPDR) showing source IP, destination IP, and port allocations.
5. Mandatory Certificate under Section 63 of Bharatiya Sakshya Adhiniyam, 2023 certifying the authenticity of the extracted computer records.

Please treat this notice as strictly confidential.

____________________________________
({io_name})
{io_designation}
{ps_name}
"""


def _build_platform_preservation_notice(ref, today_str, ps_name, io_name, io_designation, suspect_phone, suspect_acc, combined_sections) -> str:
    return f"""OFFICE OF THE INVESTIGATING OFFICER
CYBER CRIME POLICE STATION, {ps_name.upper()}

Dispatch No: CR/{ref.replace('/', '-')}/IT-79/PRESERVE
Date: {today_str}

TO,
Law Enforcement Response Team / Grievance Officer,
Meta Platforms Inc. / WhatsApp LLC / Telegram FZ-LLC / Social Media Intermediary.

SUBJECT: PRESERVATION ORDER UNDER SECTION 79(3)(b) OF THE INFORMATION TECHNOLOGY ACT, 2000
         READ WITH SECTION 91 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023.

CRIME NUMBER     : {ref}
STATUTORY CHARGES: {combined_sections}
TARGET IDENTIFIER: Mobile: {suspect_phone} | Account/Handle: {suspect_acc}

Sir/Madam,

1. This Law Enforcement Agency is investigating an organized cybercrime complaint involving extortion, impersonation, and fraudulent inducement conducted via your platform services.

2. In accordance with Section 79(3)(b) of the Information Technology Act 2000 (as amended) and Rule 3(1)(j) of Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules 2021, you are hereby ORDERED TO PRESERVE all digital evidence and telemetric records relating to the target identifiers for a period of not less than ninety (90) days pending formal court process.

3. REQUIRED PRESERVED ITEMS:
   - Account creation date, registration mobile number, recovery email address.
   - Complete IP login history with timestamps (UTC) and source port numbers.
   - Device identifiers, IMEI, operating system version, and client telemetry.
   - Subscriber profile information and public activity metadata.

4. Do NOT disclose the existence of this preservation order to the account holder or any third party, as disclosure would jeopardize ongoing criminal investigations and risk destruction of evidence.

Issued on this {today_str} under official authority.

____________________________________
({io_name})
{io_designation}
{ps_name}
"""


def _build_bsa_63_certificate(ref, today_str, ps_name, io_name, io_designation, c_name, utr_val, amount_val) -> str:
    return f"""IN THE COURT OF THE LEARNED JUDICIAL MAGISTRATE FIRST CLASS
AT {ps_name.upper()}

CASE REF NO: {ref}

CERTIFICATE OF ADMISSIBILITY FOR ELECTRONIC EVIDENCE
[UNDER SECTION 63 OF THE BHARATIYA SAKSHYA ADHINIYAM, 2023]
(Act No. 47 of 2023 - Substituted for legacy Section 65B of Indian Evidence Act 1872)

I, {io_name}, aged adult, residing in official capacity at {ps_name}, do hereby state and solemnly affirm as follows:

1. I am the designated Investigating Officer in Cyber Crime Case Reference No. {ref} registered on the complaint of {c_name} regarding fraudulent cyber debit of {amount_val} under transaction reference UTR: {utr_val}.

2. In the course of official duties and investigation, I have secured computer printouts, digital logs, CDR exhibits, bank statement extracts, and electronic screenshots forming the Electronic Record Exhibit Annexures.

3. In compliance with the statutory conditions laid down under Section 63(2) and Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023, I hereby certify that:
   a. The computer system and official terminals from which the electronic printouts and case files were generated were under lawful and regular operational control throughout the material period.
   b. During the said period, information of the kind contained in the electronic record was regularly recorded and fed into the computer systems in the ordinary course of official cyber intake activities.
   c. The computer terminal and output printers were operating properly and securely, and there was no unauthorized interference or technical malfunction that could have affected the integrity or accuracy of the electronic exhibits.
   d. The printouts and optical media enclosed herewith are true, accurate, and unedited reproductions of the original electronic data received from the official National Cyber Crime Reporting Portal (NCRP) server and bank nodal reporting networks.

4. I identify the annexed digital printouts and electronic exhibits as genuine and admissible in evidence under Section 63 of Bharatiya Sakshya Adhiniyam, 2023.

Certified and affirmed at {ps_name} on this {today_str}.

DEPONENT / CERTIFYING OFFICER

____________________________________
({io_name})
{io_designation}
{ps_name}
"""


def _build_charge_sheet_synopsis(ref, today_str, ps_name, io_name, io_designation, c_name, amount_val, utr_val, suspect_phone, suspect_acc, combined_sections, mo_title, narrative) -> str:
    return f"""BEFORE THE HON'BLE COURT OF COMPETENT JURISDICTION
POLICE INVESTIGATION CHARGE-SHEET SYNOPSIS
[UNDER SECTION 193 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023]

1. CASE IDENTIFICATION PARTICULARS:
   - Official Case Reference : {ref}
   - Police Station          : {ps_name}
   - Date of Registration    : {today_str}
   - Investigating Officer   : {io_name}, {io_designation}

2. STATUTORY PENAL CHARGES:
   - {combined_sections}
   - Procedural Mandate: Section 63 BSA 2023 electronic certificate enclosed.

3. ACCUSED PERSON(S) / SUSPECT PARTICULARS:
   - Accused No. 1 : Identity under active tracing via mobile number: {suspect_phone}
   - Beneficiary   : Holder of UPI / Bank Account: {suspect_acc}
   - Status        : Absconding / Trace via Bank KYC & Telecom CDR initiated.

4. COMPLAINANT / VICTIM:
   - Name : {c_name}
   - Loss : {amount_val} via Transaction UTR: {utr_val}

5. MODUS OPERANDI & INVESTIGATION SYNOPSIS:
   The investigation reveals an organized cyber offence categorized under '{mo_title}'.
   Brief facts:
   "{narrative}"

6. SCHEDULE OF SEIZED DIGITAL EXHIBITS:
   - Exhibit P1 : Statutory Complaint Report PDF generated via NCRP Intake Portal.
   - Exhibit P2 : Certified Bank Debit Statement confirming UTR {utr_val}.
   - Exhibit P3 : Requisition notices issued under Section 91 BNSS 2023 to Banks & TSPs.
   - Exhibit P4 : Certificate under Section 63 Bharatiya Sakshya Adhiniyam 2023.

7. PRAYER:
   It is respectfully prayed that this Hon'ble Court may be pleased to take cognizance of the offences against the accused under {combined_sections} and issue process in accordance with law.

SUBMITTED BY:

____________________________________
({io_name})
{io_designation}
{ps_name}
"""


# ---------------------------------------------------------------------------
# Self-Check & Testing CLI
# ---------------------------------------------------------------------------

def _run_self_test() -> bool:
    """Run automated verification of Investigation Document Generator."""
    print("[Doc-Generator] Verifying statutory document templates...")

    sample_case = {
        "reference": "NCRP/2026/074454",
        "complainant": {"name": "Rajesh Sharma", "police_station": "Cyber Police Station BKC Mumbai"},
        "incident": {
            "sub_category_reported": "UPI Related Frauds",
            "datetime": "2026-09-22 14:30",
            "modus_operandi": "Electricity Bill Threat via WhatsApp APK"
        },
        "transactions": [{"amount": 45000.0, "transaction_id": "326712345678", "bank": "SBI"}],
        "suspect_transactions": [{"account_no": "msedcl.desk98@paytm"}],
        "suspects": [{"phone": "9876543210"}]
    }

    templates = list_available_templates()
    assert len(templates) == 5

    for t in templates:
        doc = generate_investigation_document(
            doc_type=t["doc_type"],
            case_data=sample_case,
            io_name="Inspector R. K. Patil",
            police_station="Cyber Crime Police Station BKC Mumbai"
        )
        assert doc["case_reference"] == "NCRP/2026/074454"
        assert len(doc["document_text"]) > 200
        print(f"  [PASS] {t['doc_type']}: Generated cleanly ({len(doc['document_text'])} chars).")

    return True


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv or len(sys.argv) == 1:
        success = _run_self_test()
        sys.exit(0 if success else 1)
    else:
        doctype_arg = sys.argv[1] if len(sys.argv) > 1 else "BANK_FREEZE_NOTICE"
        res = generate_investigation_document(
            doc_type=doctype_arg,
            case_data={"reference": "NCRP/2026/074454", "complainant": {"name": "Test Complainant"}}
        )
        print(res["document_text"])
