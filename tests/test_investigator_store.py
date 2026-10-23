import json
import tempfile
import unittest
from pathlib import Path

from modules.investigator_store import (
    add_activity,
    import_case_file,
    load_cases,
    resolve_evidence_path,
    save_case,
    save_received_evidence,
)


class TestInvestigatorStore(unittest.TestCase):
    def test_import_creates_review_record_without_loading_citizen_drafts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp_dir:
            case = import_case_file(
                json.dumps({
                    "reference": "NCRP/2026/TEST-001",
                    "complaint": {"raw_text": "Synthetic test case."},
                    "classification": {"sub_category": "UPI Related Frauds"},
                }).encode(),
                temp_dir,
            )

            cases, errors = load_cases(temp_dir)

            self.assertFalse(errors)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["status"], "RECEIVED - AWAITING REVIEW")
            self.assertEqual(cases[0]["reference"], "NCRP/2026/TEST-001")

    def test_import_rejects_duplicate_reference_without_overwriting(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp_dir:
            data = json.dumps({"reference": "TEST-002", "incident": {"category": "test"}}).encode()
            import_case_file(data, temp_dir)

            with self.assertRaises(FileExistsError):
                import_case_file(data, temp_dir)

    def test_received_evidence_is_saved_and_path_checked(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp_dir:
            case = import_case_file(
                json.dumps({"reference": "TEST-003", "complaint": {"raw_text": "Synthetic."}}).encode(),
                temp_dir,
            )
            saved = save_received_evidence(case, [("receipt.png", b"test image bytes")], temp_dir)
            path = resolve_evidence_path(case, saved[0]["path"], temp_dir)

            self.assertEqual(path.read_bytes(), b"test image bytes")
            with self.assertRaises(ValueError):
                resolve_evidence_path(case, "../outside.txt", temp_dir)

    def test_activity_updates_are_persisted(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp_dir:
            case = import_case_file(
                json.dumps({"reference": "TEST-004", "complaint": {"raw_text": "Synthetic."}}).encode(),
                temp_dir,
            )
            add_activity(case, "AB", "Workflow updated", "Moved to review.")
            save_case(case, temp_dir)
            persisted = json.loads(Path(case["_path"]).read_text(encoding="utf-8"))

            self.assertEqual(persisted["_activity_log"][-1]["actor"], "AB")
            self.assertEqual(persisted["_activity_log"][-1]["action"], "Workflow updated")


if __name__ == "__main__":
    unittest.main()
