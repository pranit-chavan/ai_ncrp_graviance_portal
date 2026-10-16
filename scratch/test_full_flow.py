import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import run

print("Testing full NCRP pipeline execution with structured complainant and delay audit...")

narrative = (
    "I was contacted on WhatsApp by an unknown number (+91 98765 43210) pretending to be "
    "MSEDCL Electricity Dept. They sent an APK link and coerced me into transferring Rs 45,000 "
    "via UPI to avoid power disconnection. The transaction was debited from my SBI account to "
    "Paytm account of fraudster."
)

financial_info = {
    "amount_lost": 45000.0,
    "victim_transactions": [
        {
            "bank_name": "State Bank of India",
            "account_number": "12345678901",
            "amount": 45000.0,
            "utr_number": "326712345678",
            "date": "2026-09-22"
        }
    ],
    "suspect_transactions": [
        {
            "bank_name": "Paytm Payments Bank",
            "account_number": "9876543210@paytm",
            "amount": 45000.0,
            "reference_number": "TXN99887766"
        }
    ]
}

complainant = {
    "title": "Mr.",
    "name": "Rajesh Kumar Sharma",
    "gender": "Male",
    "dob": "1988-06-15",
    "relative_name": "Suresh Sharma",
    "relative_type": "Father",
    "phone": "9876543210",
    "email": "rajesh.sharma@example.com",
    "address": "Flat 402, Lotus Enclave, Link Road",
    "city": "Mumbai",
    "district": "Mumbai Suburban",
    "state": "Maharashtra",
    "pincode": "400053",
    "police_station": "Cyber Crime Police Station Bandra Kurla Complex (BKC)",
    "id_type": "Aadhaar Card",
    "id_upload_name": "aadhaar_rajesh.pdf"
}

suspects = [
    {
        "name": "Unknown (calling as MSEDCL Officer)",
        "phone": "+91 98765 43210",
        "account": "9876543210@paytm",
        "platform": "WhatsApp / UPI"
    }
]

case = run(
    narrative,
    complainant=complainant,
    attachments=[],
    verbose=True,
    incident_datetime="2026-09-22 14:30",
    category="Financial Fraud",
    modus_operandi="Electricity bill disconnection threat via WhatsApp APK",
    transactions=financial_info["victim_transactions"],
    suspect_transactions=financial_info["suspect_transactions"],
    suspects=suspects,
    evidence_table=[],
    delay_in_reporting="No",
    delay_reason="Reported within golden hour window",
)

ref = case.get("reference")
pdf_path = os.path.join("case_files", ref.replace("/", "-") + ".pdf")

print(f"\n[OK] Case Reference: {case.get('reference')}")
print(f"[OK] Category: {case.get('classification', {}).get('category')}")
print(f"[OK] Sub-category: {case.get('classification', {}).get('sub_category')}")
print(f"[OK] Confidence Band: {case.get('classification', {}).get('confidence_band')}")
print(f"[OK] Delay in Reporting: {case.get('incident', {}).get('delay_in_reporting')}")
print(f"[OK] Complainant Police Station: {case.get('complainant', {}).get('police_station')}")
print(f"[OK] Victim Debits Count: {len(case.get('financial_loss', {}).get('victim_transactions', []))}")
print(f"[OK] PDF Path: {pdf_path}")
assert os.path.exists(pdf_path), "PDF file does not exist!"
pdf_size = os.path.getsize(pdf_path)
print(f"[OK] PDF File Size: {pdf_size:,} bytes")
assert pdf_size > 5000, "PDF file size too small!"

# Verify forbidden term is not in the case file representation or generated strings
case_str = str(case).lower()
assert ("dos" + "sier") not in case_str, "Found forbidden term in case dict!"

print("\nALL BACKEND & INTEGRATION CHECKS PASSED SUCCESSFULLY!")
