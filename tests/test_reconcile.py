"""
Tests for Reconciliation Layer (modules/reconcile.py) and its integration
with case_file and pipeline.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.reconcile import reconcile, _extract_numbers, _digits_of
from modules.case_file import build_case_file, write_json, write_pdf


class TestReconciliationCore(unittest.TestCase):
    """Test core reconcile() logic."""

    def test_clean_agreement(self):
        """When typed text and OCR entity have the exact same number."""
        typed = "Fraud of Rs 40,000 on PhonePe on 12 Aug 2026"
        ocr = {
            "amount": "40,000",
            "upi_id": "merchant@okaxis",
            "date": "12 Aug 2026",
            "transaction_ref": "428391756201"
        }
        res = reconcile(typed, ocr)
        self.assertFalse(res["has_conflicts"])
        self.assertEqual(len(res["conflicts"]), 0)
        self.assertTrue(any(item[0] == "amount" for item in res["agreements"]))
        self.assertIn("Details confirmed from attached evidence", res["merged_text"])
        self.assertIn("high", res["confidence_note"].lower())

    def test_amount_conflict_ocr_wins(self):
        """When typed text says 40000 but OCR screenshot proves 42,000."""
        typed = "paise gaye account se around 40000"
        ocr = {
            "amount": "Rs. 42,000",
            "transaction_ref": "428391756201",
            "upi_id": "fraudster@ybl"
        }
        res = reconcile(typed, ocr)
        self.assertTrue(res["has_conflicts"])
        self.assertEqual(len(res["conflicts"]), 1)
        conflict = res["conflicts"][0]
        self.assertEqual(conflict["field"], "amount")
        self.assertEqual(conflict["ocr_value"], "Rs. 42,000")
        self.assertIn("40000", conflict["typed_mentions"])
        self.assertIn("OCR value used", conflict["resolution"])
        self.assertIn("disagree", res["confidence_note"].lower())

    def test_devanagari_numerals_normalization(self):
        """Typed text using Marathi / Hindi numerals (४००००)."""
        typed = "माझे ४०००० रुपये गेले"
        ocr = {"amount": "40000"}
        res = reconcile(typed, ocr)
        self.assertFalse(res["has_conflicts"])
        self.assertTrue(any(item[0] == "amount" for item in res["agreements"]))

    def test_gaps_identification(self):
        """Neither typed text nor OCR has amount or date."""
        typed = "someone created a fake profile and is harassing me"
        ocr = {"platform": "Instagram"}
        res = reconcile(typed, ocr)
        self.assertIn("amount", res["gaps"])
        self.assertIn("date", res["gaps"])

    def test_graceful_on_none_and_empty(self):
        """Reconciliation must never crash on empty inputs."""
        res1 = reconcile("", None)
        self.assertEqual(res1["merged_text"], "")
        self.assertFalse(res1["has_conflicts"])

        res2 = reconcile(None, {})
        self.assertEqual(res2["merged_text"], "")
        self.assertFalse(res2["has_conflicts"])

    def test_narrative_entity_merging(self):
        """Platform, email, etc. are narrative-adjacent and added cleanly."""
        typed = "I received a phishing email claiming my account was suspended"
        ocr = {"email": "alert@phishing-bank-update.com", "platform": "Gmail"}
        res = reconcile(typed, ocr)
        self.assertIn("alert@phishing-bank-update.com", res["merged_text"])
        self.assertIn("platform: Gmail", res["merged_text"])


class TestReconciliationCaseFileIntegration(unittest.TestCase):
    """Test how reconciliation integrates into Module E (case file and PDF)."""

    def test_case_file_with_reconciliation_conflict(self):
        typed = "Lost 50000 in job fraud"
        ocr = {"amount": "52000", "transaction_ref": "123456789012"}
        recon = reconcile(typed, ocr)

        case = build_case_file(
            complainant={"name": "Test User", "age": 28},
            raw_complaint=typed,
            narrative="The victim was defrauded of Rs. 52,000 under the pretext of online employment.",
            sub_category="Online Job Fraud",
            confidence=0.95,
            entities=ocr,
            reconciliation=recon
        )

        self.assertIn("reconciliation", case)
        self.assertTrue(case["reconciliation"]["has_conflicts"])
        self.assertEqual(len(case["reconciliation"]["conflicts"]), 1)
        self.assertEqual(case["data_provenance"]["reconciliation_source"], "Reconciliation Layer")

    def test_pdf_build_with_reconciliation(self):
        """Ensure PDF can be generated with reconciliation notes without error."""
        import tempfile
        typed = "paise gaye 40000"
        ocr = {"amount": "42000", "upi_id": "scam@upi"}
        recon = reconcile(typed, ocr)

        case = build_case_file(
            complainant={"name": "Citizen A", "age": 30},
            raw_complaint=typed,
            narrative="Unauthorised debit of Rs. 42,000 reported.",
            sub_category="UPI Related Frauds",
            confidence=0.92,
            entities=ocr,
            reconciliation=recon
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            out_pdf = write_pdf(case, path=tmp_path)
            self.assertTrue(os.path.exists(out_pdf))
            self.assertGreater(os.path.getsize(out_pdf), 1000)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
