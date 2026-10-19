"""
MODULE H — Agent Orchestrator & Autonomous Intake Controller

An autonomous conversational state machine that takes a victim's single spoken
or typed grievance, orchestrates all NCRP intelligence modules, and produces an
official, pre-filled, court-ready complaint case file with zero manual form-filling.

WORKFLOW STATES:
    INIT -> INGEST -> PARSE_NER -> MATCH_MO -> RECONCILE ->
    CHECK_GAPS (asks max 2-3 focused questions if critical data missing) ->
    AUTO_FILL -> CLASSIFY -> LEGAL_MAP -> NARRATIVE -> BUILD_CASE -> REVIEW_READY -> SUBMITTED

USAGE:
    from modules.agent_orchestrator import AgentSession

    session = AgentSession(user_profile={"name": "Pranit Chavan", "city": "Pune"})
    response = session.process_input(
        "On 17 Oct 2026, ₹25,000 was debited from my HDFC A/c ending 1234 via UPI UTR 326712345678 to fraudster@paytm"
    )

    if response["status"] == "READY_FOR_SUBMISSION":
        case_file = session.submit_complaint()
        print("Generated NCRP Case:", case_file["reference"])
"""

import os
import sys
import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.entity_extractor import extract_entities_v2
from modules.mo_knowledge_base import match_mo, get_critical_fields
from modules.auto_fill import generate_autofill_payload
from modules.victim_guidance import generate_victim_guidance
from modules.sentiment_analysis import analyze_sentiment_and_urgency
from modules.reconcile import reconcile
from modules.legal_mapping import map_sections
from modules.case_file import build_case_file, write_json, write_pdf


class AgentSession:
    """Manages an active conversational intake session for a cybercrime grievance."""

    def __init__(self, session_id: Optional[str] = None, user_profile: Optional[Dict[str, Any]] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.user_profile = user_profile or {}
        self.state = "INIT"
        self.accumulated_text = ""
        self.attachments: List[str] = []
        self.ocr_entities: Dict[str, Any] = {}
        self.extracted_entities: Dict[str, Any] = {}
        self.mo_match: Optional[Dict[str, Any]] = None
        self.reconciliation: Optional[Dict[str, Any]] = None
        self.sentiment: Optional[Dict[str, Any]] = None
        self.autofill_payload: Optional[Dict[str, Any]] = None
        self.sub_category: str = "UPI Related Frauds"
        self.confidence: float = 0.95
        self.legal_sections: Optional[Dict[str, Any]] = None
        self.victim_guidance: Optional[Dict[str, Any]] = None
        self.case_file: Optional[Dict[str, Any]] = None
        self.conversation_log: List[Dict[str, str]] = []

    def process_input(
        self,
        user_utterance: str,
        attachments: Optional[List[str]] = None,
        ocr_entities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user input turn (spoken transcription or typed message).
        Orchestrates all intelligence layers autonomously.
        """
        if not user_utterance and not attachments:
            return {"status": "AWAITING_INPUT", "message": "Please describe what happened."}

        # 1. Update text & attachments
        if self.accumulated_text:
            self.accumulated_text += f"\n{user_utterance.strip()}"
        else:
            self.accumulated_text = user_utterance.strip()

        if attachments:
            self.attachments.extend([a for a in attachments if a not in self.attachments])
        if ocr_entities:
            self.ocr_entities.update(ocr_entities)

        self.conversation_log.append({"role": "user", "text": user_utterance})

        # 2. Run NER v2
        self.extracted_entities = extract_entities_v2(
            self.accumulated_text,
            ocr_entities=self.ocr_entities
        )

        # 3. Match Modus Operandi (MO-KB)
        self.mo_match = match_mo(self.accumulated_text, entities=self.extracted_entities)
        if self.mo_match:
            self.sub_category = self.mo_match["primary_ncrp_subcategory"]
            self.confidence = float(self.mo_match["match_score"])

        # 4. Reconciliation audit
        self.reconciliation = reconcile(self.accumulated_text, self.ocr_entities)

        # 5. Sentiment & Golden Hour Urgency
        self.sentiment = analyze_sentiment_and_urgency(self.accumulated_text, entities=self.extracted_entities)

        # 6. Auto-Fill Payload Generation
        self.autofill_payload = generate_autofill_payload(
            self.accumulated_text,
            ocr_entities=self.ocr_entities,
            user_profile=self.user_profile
        )

        # 7. Check for Critical Missing Gaps
        critical_missing = self.autofill_payload.get("missing_critical_fields", [])
        
        # If crucial fields like UTR or Amount are completely absent for financial crimes, ask focused questions
        if critical_missing and len(self.conversation_log) <= 2:
            self.state = "ASKING_GAPS"
            followup_questions = self._build_followup_questions(critical_missing)
            agent_msg = (
                "Main aapki complaint register karne ke liye tayyar hoon. "
                "Turant bank me fund freeze karwane ke liye bas yeh ek-do details confirm kar dijiye:"
            )
            self.conversation_log.append({"role": "agent", "text": agent_msg})
            return {
                "status": "NEED_CLARIFICATION",
                "message": agent_msg,
                "questions": followup_questions,
                "current_completion": self.autofill_payload["completion_percentage"],
                "identified_crime": self.mo_match["name"] if self.mo_match else self.sub_category,
                "golden_hour": self.sentiment.get("golden_hour_active", True)
            }

        # 8. All sufficient facts gathered -> Transition to REVIEW_READY
        self.state = "REVIEW_READY"

        # Resolve Legal Sections
        try:
            self.legal_sections = map_sections(
                self.sub_category,
                complainant_age=self.autofill_payload["complainant"].get("age")
            )
        except Exception:
            self.legal_sections = None

        # Build Victim Tactical Guidance
        self.victim_guidance = generate_victim_guidance(
            bank_name=self.extracted_entities.get("bank_name"),
            mo_id=self.mo_match["mo_id"] if self.mo_match else None,
            amount=self.extracted_entities.get("amount"),
            utr=self.extracted_entities.get("utr"),
            incident_date=self.extracted_entities.get("date")
        )

        agent_msg = (
            "Aapki complaint successfully analyze aur prepare ho chuki hai. "
            f"Crime type: '{self.mo_match['name'] if self.mo_match else self.sub_category}'. "
            f"Form completion: {self.autofill_payload['completion_percentage']}%. "
            "Kripya niche pre-filled details verify karke confirm karein."
        )
        self.conversation_log.append({"role": "agent", "text": agent_msg})

        return {
            "status": "READY_FOR_SUBMISSION",
            "message": agent_msg,
            "session_id": self.session_id,
            "autofill_payload": self.autofill_payload,
            "mo_match": self.mo_match,
            "sentiment": self.sentiment,
            "victim_guidance": self.victim_guidance,
            "reconciliation": self.reconciliation
        }

    def _build_followup_questions(self, missing_fields: List[str]) -> List[Dict[str, str]]:
        """Construct gentle, localized follow-up questions for missing fields (capped at 2)."""
        questions = []
        for field in missing_fields[:2]:
            if "UTR" in field:
                questions.append({
                    "field": "utr",
                    "question_en": "What is the 12-digit UTR or Transaction Reference number from your bank debit SMS?",
                    "question_hi": "Aapke bank debit SMS me jo 12-digit ka UTR ya Ref number hai, wo kya hai?"
                })
            elif "UPI" in field or "Account" in field:
                questions.append({
                    "field": "beneficiary",
                    "question_en": "What was the suspect's UPI ID (e.g. name@bank) or beneficiary bank account?",
                    "question_hi": "Fraudster ka UPI ID (jaise name@paytm) ya bank account number kya tha?"
                })
            elif "Phone" in field:
                questions.append({
                    "field": "suspect_phone",
                    "question_en": "What was the mobile number from which the scammer called or messaged?",
                    "question_hi": "Scammer ka phone number kya tha jisse call ya WhatsApp message aaya tha?"
                })
            elif "Name" in field:
                questions.append({
                    "field": "name",
                    "question_en": "Please provide your full legal name as registered in bank records.",
                    "question_hi": "Kripya apna poora naam batayein jo bank me darj hai."
                })
            elif "APK" in field:
                questions.append({
                    "field": "app_name",
                    "question_en": "What was the name of the app installed (e.g. AnyDesk, QuickSupport, or APK name)?",
                    "question_hi": "Aapse kaunsi app download karwayi gayi thi (jaise AnyDesk ya koi APK)?"
                })
        return questions

    def submit_complaint(self, output_dir: str = "case_files") -> Dict[str, Any]:
        """Finalize, lock, write JSON and render court-ready PDF case file."""
        if not self.autofill_payload:
            raise ValueError("No processed grievance payload available to submit.")

        p = self.autofill_payload
        c = p["complainant"]
        inc = p["incident"]

        self.case_file = build_case_file(
            complainant=c,
            narrative=self.accumulated_text,
            sub_category=inc["sub_category_reported"],
            confidence=self.confidence,
            entities=self.extracted_entities,
            attachments=self.attachments,
            raw_complaint=self.accumulated_text,
            incident_datetime=inc["datetime"],
            category=inc["category"],
            modus_operandi=inc["modus_operandi"],
            incident_location=inc["location"],
            transactions=p["transactions"],
            suspect_transactions=p["suspect_transactions"],
            suspects=p["suspects"],
            reconciliation=self.reconciliation,
            sentiment=self.sentiment
        )

        os.makedirs(output_dir, exist_ok=True)
        ref_slug = self.case_file["reference"].replace("/", "-")
        json_path = os.path.join(output_dir, f"{ref_slug}.json")
        pdf_path = os.path.join(output_dir, f"{ref_slug}.pdf")

        write_json(self.case_file, json_path)
        try:
            write_pdf(self.case_file, pdf_path)
            self.case_file["pdf_path"] = pdf_path
        except Exception as e:
            self.case_file["pdf_path"] = None
            self.case_file["pdf_error"] = str(e)

        self.case_file["json_path"] = json_path
        self.state = "SUBMITTED"

        return self.case_file


# ---------------------------------------------------------------------------
# Self-Check & Testing CLI
# ---------------------------------------------------------------------------

def _run_self_test() -> bool:
    """Run automated verification of Agent Orchestrator end-to-end."""
    print("[Agent-Orchestrator] Running autonomous session verification test...")

    session = AgentSession(user_profile={"name": "Pranit Chavan", "city": "Pune", "phone": "9876543210"})

    # Test Turn 1: Partial complaint
    resp1 = session.process_input("Mere account se paise cut ho gaye bijli bill ke naam pe WhatsApp pe message aaya tha")
    assert resp1["status"] in ["NEED_CLARIFICATION", "READY_FOR_SUBMISSION"]
    print(f"  [PASS] Turn 1: Session state transitioned to '{resp1['status']}'.")

    # Test Turn 2: Provide transaction details
    resp2 = session.process_input("Amount ₹45,000 tha HDFC account se debit hua, UTR: 326712345678 to msedcl@paytm")
    assert resp2["status"] == "READY_FOR_SUBMISSION"
    assert resp2["mo_match"]["mo_id"] == "MO-FIN-001"
    assert resp2["autofill_payload"]["transactions"][0]["amount"] == 45000
    print(f"  [PASS] Turn 2: Ready for submission. MO: {resp2['mo_match']['name']}")

    # Test Submission
    case = session.submit_complaint()
    assert case["reference"].startswith("NCRP/")
    assert os.path.exists(case["json_path"])
    print(f"  [PASS] Final Submission: Case file created at '{case['json_path']}'.")
    return True


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv or len(sys.argv) == 1:
        success = _run_self_test()
        sys.exit(0 if success else 1)
    else:
        text = " ".join(sys.argv[1:])
        s = AgentSession(user_profile={"name": "Test Citizen", "phone": "9800000000"})
        r = s.process_input(text)
        print("Agent Response Status:", r["status"])
        print("Message:", r["message"])
        if r["status"] == "READY_FOR_SUBMISSION":
            c = s.submit_complaint()
            print("Generated Case Reference:", c["reference"])
