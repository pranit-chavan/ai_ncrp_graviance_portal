"""
Comprehensive End-to-End System Integration Test for NCRP v2.0 Architecture

Verifies that all 7 new modules function cohesively:
  1. Module H.1 (MO Knowledge Base): Matches attack patterns
  2. Module H.2 (NER v2): Extracts financial entities from Hindi/Hinglish speech
  3. Module I (Auto-Fill Engine): Pre-populates complaint forms
  4. Module J (Victim Guidance): Produces emergency bank and BSA directives
  5. Module H (Agent Orchestrator): Turn-based intake and case submission
  6. Module L (Pattern Engine): Multi-case correlation & syndicate linking
  7. Module M (Doc Generator): Procedural notices under BNSS 2023 & BSA 2023
"""

import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.mo_knowledge_base import match_mo, get_critical_fields, get_victim_guidance
from modules.entity_extractor import extract_entities_v2
from modules.auto_fill import generate_autofill_payload
from modules.victim_guidance import generate_victim_guidance
from modules.agent_orchestrator import AgentSession
from modules.pattern_engine import index_case, find_linked_cases, build_suspect_dossier
from modules.doc_generator import generate_investigation_document, list_available_templates


class TestNCRPv2System(unittest.TestCase):

    def setUp(self):
        self.sample_speech = (
            "On 17 Oct 2026, ₹45,000 was fraudulently debited from my HDFC Bank account (A/c ending 1234) "
            "via UPI UTR: 326712345678 to msedcl.desk98@paytm. Scammer called from 9876543210 "
            "threatening electricity disconnection tonight."
        )
        self.user_profile = {
            "name": "Pranit Chavan",
            "city": "Pune",
            "state": "Maharashtra",
            "phone": "9123456789"
        }

    def test_01_mo_knowledge_base(self):
        match = match_mo(self.sample_speech)
        self.assertIsNotNone(match)
        self.assertEqual(match["mo_id"], "MO-FIN-001")
        self.assertIn("Electricity", match["name"])
        critical = get_critical_fields(match["mo_id"])
        self.assertIn("utr", critical)

    def test_02_entity_extractor(self):
        ent = extract_entities_v2(self.sample_speech)
        self.assertEqual(ent["amount"], 45000)
        self.assertEqual(ent["bank_name"], "HDFC")
        self.assertEqual(ent["account_last4"], "1234")
        self.assertEqual(ent["utr"], "326712345678")
        self.assertEqual(ent["upi_id"], "msedcl.desk98@paytm")
        self.assertIn("9876543210", ent["all_phones"])

    def test_03_auto_fill_engine(self):
        payload = generate_autofill_payload(self.sample_speech, user_profile=self.user_profile)
        self.assertEqual(payload["complainant"]["name"], "Pranit Chavan")
        self.assertEqual(len(payload["transactions"]), 1)
        self.assertEqual(payload["transactions"][0]["amount"], 45000)
        self.assertEqual(payload["transactions"][0]["transaction_id"], "326712345678")
        self.assertGreaterEqual(payload["completion_percentage"], 90.0)

    def test_04_victim_guidance(self):
        guidance = generate_victim_guidance(
            bank_name="HDFC",
            mo_id="MO-FIN-001",
            amount=45000,
            utr="326712345678",
            incident_date=date.today().isoformat()
        )
        self.assertTrue(guidance["golden_hour_active"])
        self.assertEqual(guidance["bank_details"]["name"], "HDFC Bank")
        self.assertIn("1930", guidance["advisory_markdown"])
        self.assertIn("Section 63 BSA 2023", guidance["advisory_markdown"])

    def test_05_agent_orchestrator(self):
        session = AgentSession(user_profile=self.user_profile)
        res = session.process_input(self.sample_speech)
        self.assertEqual(res["status"], "READY_FOR_SUBMISSION")
        case = session.submit_complaint(output_dir="case_files")
        self.assertTrue(case["reference"].startswith("NCRP/"))
        self.assertTrue(os.path.exists(case["json_path"]))

    def test_06_pattern_engine(self):
        test_db = "test_system_index.db"
        if os.path.exists(test_db):
            os.remove(test_db)

        c1 = {
            "reference": "NCRP/2026/9001",
            "complainant": {"name": "Victim A", "city": "Pune"},
            "incident": {"category": "Financial Fraud", "sub_category_reported": "UPI Related Frauds"},
            "transactions": [{"amount": 25000.0, "transaction_id": "UTR999"}],
            "suspects": [{"phone": "9999999999"}],
            "extracted_entities": {"upi_id": "scam99@paytm"}
        }
        c2 = {
            "reference": "NCRP/2026/9002",
            "complainant": {"name": "Victim B", "city": "Mumbai"},
            "incident": {"category": "Financial Fraud", "sub_category_reported": "UPI Related Frauds"},
            "transactions": [{"amount": 50000.0, "transaction_id": "UTR888"}],
            "suspects": [{"phone": "9999999999"}],
            "extracted_entities": {"upi_id": "scam99@paytm"}
        }

        index_case(c1, db_path=test_db)
        index_case(c2, db_path=test_db)

        links = find_linked_cases("NCRP/2026/9001", db_path=test_db)
        self.assertEqual(links["total_cases_linked"], 1)
        self.assertEqual(links["total_amount_defrauded"], 75000.0)

        dos = build_suspect_dossier("9999999999", db_path=test_db)
        self.assertTrue(dos["found"])
        self.assertEqual(dos["total_complaints"], 2)

        if os.path.exists(test_db):
            os.remove(test_db)

    def test_07_doc_generator(self):
        case = {
            "reference": "NCRP/2026/9001",
            "complainant": {"name": "Test Citizen", "police_station": "Cyber Cell Pune"},
            "incident": {"sub_category_reported": "UPI Related Frauds", "datetime": "2026-10-19 10:00"},
            "transactions": [{"amount": 25000.0, "transaction_id": "326712345678", "bank": "HDFC"}],
            "suspect_transactions": [{"account_no": "fraud99@paytm"}],
            "suspects": [{"phone": "9876543210"}]
        }
        templates = list_available_templates()
        self.assertEqual(len(templates), 5)

        for t in templates:
            doc = generate_investigation_document(
                doc_type=t["doc_type"],
                case_data=case,
                io_name="Inspector Patil",
                police_station="Cyber Police Station Pune"
            )
            self.assertIn("NCRP/2026/9001", doc["document_text"])


if __name__ == "__main__":
    unittest.main()
