"""
TEST SUITE: Module D - Statutory Legal Mapping & Audit Framework
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.legal_mapping import (
    CATEGORIES,
    map_sections,
    get_audit_framework,
    is_verified,
    get_statutory_elements,
    UnknownCategory,
)
from modules.case_file import build_case_file, write_pdf


class TestLegalMappingAudit(unittest.TestCase):

    def test_all_21_categories_present_and_verified(self):
        """Verify exactly 21 NCRP categories exist and every single one is certified."""
        self.assertEqual(len(CATEGORIES), 21, f"Expected 21 categories, got {len(CATEGORIES)}")
        for cat in CATEGORIES:
            res = map_sections(cat)
            self.assertTrue(res.get("verified"), f"Category '{cat}' is not marked verified!")
            self.assertEqual(res.get("statute_year"), 2023)
            self.assertTrue(is_verified(cat))

    def test_struck_down_section_66a_strictly_omitted(self):
        """Verify that unconstitutional Section 66A IT Act is nowhere present."""
        for cat in CATEGORIES:
            res = map_sections(cat)
            for it in res.get("it_act", []):
                self.assertNotEqual(
                    it.get("section"),
                    "66A",
                    f"Struck-down Section 66A IT Act found in category '{cat}'!"
                )

    def test_bns_sections_have_legacy_ipc_equivalents(self):
        """Verify all BNS penal provisions contain legacy IPC cross-references."""
        for cat in CATEGORIES:
            res = map_sections(cat)
            for bns in res.get("bns", []):
                self.assertIn(
                    "ipc_equivalent",
                    bns,
                    f"Missing ipc_equivalent in BNS provision {bns} for '{cat}'"
                )
                self.assertTrue(
                    len(bns["ipc_equivalent"]) > 0,
                    f"Empty ipc_equivalent in BNS provision {bns} for '{cat}'"
                )

    def test_statutory_proof_elements_populated(self):
        """Verify every category provides essential ingredients for IO charge-sheeting."""
        for cat in CATEGORIES:
            elements = get_statutory_elements(cat)
            self.assertGreaterEqual(
                len(elements),
                2,
                f"Category '{cat}' must have at least 2 statutory proof ingredients"
            )

    def test_audit_framework_metadata(self):
        """Verify the root audit framework metadata."""
        meta = get_audit_framework()
        self.assertEqual(meta.get("jurisdiction"), "Republic of India")
        self.assertEqual(meta.get("audit_status"), "CERTIFIED_CURRENT")
        self.assertIn("Bharatiya Nyaya Sanhita, 2023", meta.get("primary_penal_statute", ""))
        self.assertIn("Information Technology Act, 2000", meta.get("primary_cyber_statute", ""))

    def test_pocso_conditional_adult(self):
        """Verify POCSO and 67B do not apply to adult complainant."""
        res = map_sections("Cyber Bullying / Stalking / Sexting", complainant_age=25)
        pocso = [o for o in res["other"] if "POCSO" in o.get("act", "") or "67B" in o.get("section", "")]
        self.assertEqual(len(pocso), 0)
        self.assertEqual(res["conditional_applied"][0]["status"], "not applicable")

    def test_pocso_conditional_minor(self):
        """Verify POCSO and IT Act 67B strictly apply when complainant is a minor."""
        res = map_sections("Cyber Bullying / Stalking / Sexting", complainant_age=16)
        pocso = [o for o in res["other"] if "POCSO" in o.get("act", "") or "67B" in o.get("section", "")]
        self.assertEqual(len(pocso), 4)
        self.assertEqual(res["conditional_applied"][0]["status"], "APPLIED")

    def test_pocso_conditional_age_omitted(self):
        """Verify advisory when age is omitted for child protection category."""
        res = map_sections("Cyber Bullying / Stalking / Sexting", complainant_age=None)
        self.assertTrue(res["conditional_applied"][0]["status"].startswith("NOT EVALUATED"))

    def test_unknown_category_raises(self):
        """Verify UnknownCategory exception is raised for invalid category name."""
        with self.assertRaises(UnknownCategory):
            map_sections("Nonexistent Cyber Crime Offence")

    def test_case_file_and_pdf_rendering(self):
        """Verify that case file builds with verified legal sections and generates valid PDF."""
        case = build_case_file(
            complainant={"name": "Test Citizen", "age": 28, "phone": "9876543210", "city": "Pune", "state": "Maharashtra"},
            raw_complaint="Fake job offer sent via WhatsApp asking for registration fee",
            narrative="The complainant received a fraudulent job offer on WhatsApp and was cheated of Rs 15,000.",
            sub_category="Online Job Fraud",
            confidence=0.92,
        )
        self.assertEqual(case["legal_sections"]["verified"], True)
        self.assertGreater(len(case["legal_sections"]["bns"]), 0)
        pdf_path = write_pdf(case)
        self.assertIsNotNone(pdf_path)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 5000)


if __name__ == "__main__":
    unittest.main()
