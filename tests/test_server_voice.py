"""Voice upload endpoint wiring checks using an isolated server data root."""

import asyncio
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException

from starlette.datastructures import Headers, UploadFile


class TestServerVoiceEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = tempfile.mkdtemp(prefix="cyberassist-voice-api-")

        import modules.database as database
        import modules.pattern_engine as pattern_engine
        original_db_path = database.DB_PATH
        original_sync = pattern_engine.sync_all_case_files
        database.DB_PATH = os.path.join(cls.test_root, "complaints.db")
        pattern_engine.sync_all_case_files = lambda _path: original_sync(
            os.path.join(cls.test_root, "case_files"),
            db_path=os.path.join(cls.test_root, "case_index.db"),
        )
        try:
            import server
        finally:
            database.DB_PATH = original_db_path
            pattern_engine.sync_all_case_files = original_sync
        server.CASE_DIR = os.path.join(cls.test_root, "case_files")
        server.UPLOAD_DIR = os.path.join(cls.test_root, "uploads")
        server.INVESTIGATOR_INBOX_DIR = os.path.join(cls.test_root, "investigator_inbox")
        cls.server = server

    def test_transcribe_endpoint_forwards_upload_and_language(self):
        audio_bytes = b"fictional audio bytes"
        upload = UploadFile(filename="recording.webm", file=io.BytesIO(audio_bytes))
        mocked_result = {
            "ok": True,
            "text": "My bank account was debited.",
            "language": "mr",
            "latency_seconds": 0.1,
        }

        with patch.object(
            self.server,
            "transcribe_audio_bytes",
            return_value=mocked_result,
        ) as transcribe:
            response = asyncio.run(
                self.server.transcribe_endpoint(file=upload, language="mr")
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body)["text"], mocked_result["text"])
        transcribe.assert_called_once_with(
            audio_bytes,
            filename="recording.webm",
            language="mr",
            model_name="tiny",
        )

    def test_evidence_upload_returns_ocr_data_without_leaking_local_path(self):
        upload = UploadFile(
            filename="fictional-payment.png",
            file=io.BytesIO(b"fictional image bytes"),
            headers=Headers({"content-type": "image/png"}),
        )
        mocked_ocr = {
            "per_image": [{"chars": 18, "raw_text": "Rs. 4,500"}],
            "entities": {"amount": "4,500"},
            "errors": [],
        }

        with patch.object(self.server, "extract_from_images", return_value=mocked_ocr):
            response = asyncio.run(self.server.upload_evidence_endpoint(file=upload))

        result = json.loads(response.body)
        self.assertTrue(result["ok"])
        self.assertEqual(result["entities"]["amount"], "4,500")
        self.assertEqual(result["raw_snippet"], "Rs. 4,500")
        self.assertNotIn("file_path", result)
        self.assertTrue(os.path.isfile(os.path.join(self.server.UPLOAD_DIR, result["filename"])))

    def test_uploaded_evidence_can_be_opened_by_investigator(self):
        os.makedirs(self.server.UPLOAD_DIR, exist_ok=True)
        filename = "evid_fictional-proof.png"
        path = os.path.join(self.server.UPLOAD_DIR, filename)
        with open(path, "wb") as evidence_file:
            evidence_file.write(b"fictional image bytes")

        response = asyncio.run(self.server.get_evidence_endpoint(filename))

        self.assertEqual(response.path, path)

    def test_case_submission_keeps_attached_evidence_and_ocr_entities(self):
        fake_evidence = [{"filename": "evid_fictional-payment.png", "chars_read": 18}]
        os.makedirs(self.server.UPLOAD_DIR, exist_ok=True)
        with open(os.path.join(self.server.UPLOAD_DIR, fake_evidence[0]["filename"]), "wb") as evidence_file:
            evidence_file.write(b"fictional evidence bytes")
        payload = {
            "intake_session_id": "CYB-2026-123456",
            "investigator_consent": True,
            "complainant": {"state": "Maharashtra", "district": "Pune"},
            "incident": {"datetime": "2026-10-20T12:00", "category": "Online Financial Fraud"},
            "incident_text": "A fictional complainant reports a suspicious payment request.",
            "standardised_narrative": "NOT AVAILABLE - Module A did not run",
            "sub_category": "UPI Related Frauds",
            "entities": {"amount": "4500", "transaction_ref": "TEST-UPI-001"},
            "evidence": fake_evidence,
            "transactions": [
                {"amount": 4500, "bank_name": "Fictional Bank", "utr_number": "TEST-UPI-001"},
                {"amount": 1200, "bank_name": "Fictional Wallet", "utr_number": "TEST-UPI-002"},
            ],
            "suspect_transactions": [{"method": "UPI", "account_no": "demo@ybl", "amount": 4500}],
        }

        with patch.object(self.server, "classify_complaint_text", return_value={
            "predicted_category": "UPI Related Frauds", "confidence": 0.9,
        }), patch.object(self.server, "write_pdf"):
            response = asyncio.run(self.server.submit_case_endpoint(payload))

        result = json.loads(response.body)
        self.assertTrue(result["ok"])
        self.assertEqual(result["case"]["complaint"]["standardised_narrative"], payload["incident_text"])
        self.assertEqual(result["case"]["complaint"]["raw_text"], payload["incident_text"])
        self.assertEqual(result["case"]["intake_metadata"]["session_id"], payload["intake_session_id"])
        self.assertEqual(result["case"]["intake_metadata"]["evidence_count"], 1)
        self.assertEqual(result["case"]["extracted_entities"]["transaction_ref"], "TEST-UPI-001")
        self.assertEqual(result["case"]["evidence"]["attachments"], fake_evidence)
        self.assertEqual(len(result["case"]["transactions"]), 2)
        from modules.investigator_store import _safe_reference
        inbox_path = os.path.join(self.server.INVESTIGATOR_INBOX_DIR, f"{_safe_reference(result['reference'])}.json")
        self.assertTrue(os.path.isfile(inbox_path))
        with open(inbox_path, encoding="utf-8") as case_file:
            inbox_case = json.load(case_file)
        self.assertEqual(len(inbox_case["transactions"]), 2)
        self.assertEqual(len(inbox_case["suspect_transactions"]), 1)
        self.assertEqual(len(inbox_case["received_evidence_files"]), 1)
        self.assertTrue(os.path.isfile(os.path.join(self.server.INVESTIGATOR_INBOX_DIR, inbox_case["received_evidence_files"][0]["path"])))

        workflow = asyncio.run(self.server.update_case_workflow(self.server.WorkflowUpdateRequest(
            reference=result["reference"], status="IN REVIEW", assigned_to="Investigator A", reviewer="AB", note="Checked fictional evidence."
        )))
        self.assertEqual(workflow.status_code, 200)
        with open(inbox_path, encoding="utf-8") as case_file:
            updated_inbox_case = json.load(case_file)
        self.assertEqual(updated_inbox_case["status"], "IN REVIEW")
        self.assertIn("Checked fictional evidence.", updated_inbox_case["_activity_log"][-1]["details"])

    def test_case_submission_requires_local_investigator_consent(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(self.server.submit_case_endpoint({
                "incident_text": "Fictional report without consent.",
                "standardised_narrative": "Fictional report without consent.",
            }))
        self.assertEqual(raised.exception.status_code, 422)

    def test_case_submission_rejects_missing_complaint_text(self):
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(self.server.submit_case_endpoint({
                "investigator_consent": True,
                "standardised_narrative": "NOT AVAILABLE - Module A did not run",
                "incident_text": "",
            }))
        self.assertEqual(raised.exception.status_code, 422)

    def test_citizen_can_track_saved_local_case_reference(self):
        os.makedirs(self.server.CASE_DIR, exist_ok=True)
        reference = "CYB-TEST-20261024-001"
        path = os.path.join(self.server.CASE_DIR, f"{reference}.json")
        with open(path, "w", encoding="utf-8") as case_file:
            json.dump({"reference": reference, "status": "IN REVIEW", "complainant": {"city": "Pune"}, "classification": {"sub_category": "UPI Related Frauds"}}, case_file)

        response = asyncio.run(self.server.track_case_endpoint(self.server.TrackRequest(reference=reference)))

        result = json.loads(response.body)
        self.assertTrue(result["found"])
        self.assertEqual(result["status"], "IN REVIEW")
        self.assertEqual(result["category"], "UPI Related Frauds")

    def test_investigator_workflow_update_persists_status_assignment_and_note(self):
        os.makedirs(self.server.CASE_DIR, exist_ok=True)
        reference = "CYB-TEST-WORKFLOW-001"
        path = os.path.join(self.server.CASE_DIR, f"{reference}.json")
        with open(path, "w", encoding="utf-8") as case_file:
            json.dump({"reference": reference, "status": "RECEIVED - AWAITING REVIEW", "complainant": {}}, case_file)

        response = asyncio.run(self.server.update_case_workflow(self.server.WorkflowUpdateRequest(
            reference=reference, status="IN REVIEW", assigned_to="Investigator A", reviewer="AB", note="Reviewed the submitted screenshot."
        )))

        result = json.loads(response.body)
        self.assertTrue(result["ok"])
        with open(path, encoding="utf-8") as case_file:
            saved = json.load(case_file)
        self.assertEqual(saved["status"], "IN REVIEW")
        self.assertEqual(saved["assigned_to"], "Investigator A")
        self.assertIn("Reviewed the submitted screenshot.", saved["_activity_log"][-1]["details"])

    def test_separate_frontend_and_assets_are_served(self):
        from pathlib import Path

        page = asyncio.run(self.server.serve_index())
        app_script = Path(self.server.STATIC_DIR, "citizen.js").read_text(encoding="utf-8")
        stylesheet = Path(self.server.STATIC_DIR, "citizen.css").read_text(encoding="utf-8")

        self.assertIn('/static/citizen.js', page)
        self.assertIn("/api/upload_evidence", app_script)
        self.assertIn("/api/cases/submit", app_script)
        self.assertIn("/api/evidence/", app_script)
        self.assertIn(".reading", stylesheet)


if __name__ == "__main__":
    unittest.main()
