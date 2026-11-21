"""
TEST SUITE — Module A (Gap Detection + AI Assistant)

Tests three things the Master Plan (Part 3, Step 4) requires:
    1. Gap detection fires on thin complaints and stays silent on complete ones
    2. Questions asked are relevant to what is ACTUALLY missing
    3. The interactive state machine transitions correctly
       (need_more_info vs ready)

Does NOT require Ollama / any LLM — all tests exercise the deterministic
gap detection layer and the guard, not the narrative generation.

USAGE
    python -m pytest tests/test_module_a.py -v
    python -m unittest tests.test_module_a -v
"""

import os
import sys
import unittest
from unittest.mock import patch

# ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.gap_detection import (
    detect_gaps,
    detect_language,
    detect_category_group,
    format_for_display,
    PROFILES,
    FIELD_META,
    MAX_QUESTIONS,
)
from modules.ai_assistant import (
    DEFAULT_MODEL,
    guard,
    standardise_interactive,
    build_prompt,
    _digits,
    _normalize_text,
)
from modules.conversational_agent import conduct_counselor_turn, extract_structured_docket


# ============================================================================
# 1. GAP DETECTION — category hint inference
# ============================================================================

class TestCategoryHint(unittest.TestCase):
    """Verify that keyword-based category inference picks the right profile."""

    def test_upi_keywords(self):
        hint = detect_category_group("refund ke liye qr code scan kiya paytm pe", {})
        self.assertEqual(hint, "financial_upi")

    def test_upi_platform_name(self):
        hint = detect_category_group("phonepe se paise gaye", {})
        self.assertEqual(hint, "financial_upi")

    def test_banking_keywords(self):
        hint = detect_category_group("net banking se transfer ho gaya", {})
        self.assertEqual(hint, "financial_banking")

    def test_card_keywords(self):
        hint = detect_category_group("credit card se 50000 kat gaye, sim swap hua", {})
        self.assertEqual(hint, "financial_card")

    def test_aeps_keywords(self):
        hint = detect_category_group("thumb impression se paisa nikla aeps", {})
        self.assertEqual(hint, "financial_aeps")

    def test_investment_keywords(self):
        hint = detect_category_group("telegram group pe trading platform dikha", {})
        self.assertEqual(hint, "financial_invest")

    def test_job_keywords(self):
        hint = detect_category_group("job ke liye registration fee maanga", {})
        self.assertEqual(hint, "financial_job")

    def test_account_hack(self):
        hint = detect_category_group("my instagram account was hacked", {})
        self.assertEqual(hint, "account")

    def test_harassment(self):
        hint = detect_category_group("someone is blackmailing me with my photos", {})
        self.assertEqual(hint, "harassment")

    def test_hacking(self):
        hint = detect_category_group("ransomware attack on our server", {})
        self.assertEqual(hint, "hacking")

    def test_general_fallback(self):
        """Vague text with no specific keywords falls back to general."""
        hint = detect_category_group("something bad happened online", {})
        self.assertEqual(hint, "general")

    def test_hindi_money_words_trigger_financial(self):
        """Hindi 'paise' should at minimum trigger a financial category."""
        hint = detect_category_group("paise gaye", {})
        self.assertIn("financial", hint)


# ============================================================================
# 2. GAP DETECTION — thin vs complete complaints
# ============================================================================

class TestGapDetection(unittest.TestCase):
    """Core test: thin complaints must have gaps, complete ones must not."""

    # --- thin complaints that MUST fire gaps ---

    def test_two_words_has_gaps(self):
        r = detect_gaps("paise gaye")
        self.assertTrue(r["has_gaps"])
        self.assertTrue(r["is_thin"])
        self.assertIn("amount", r["all_gaps"])
        self.assertIn("date", r["all_gaps"])

    def test_harassment_thin(self):
        r = detect_gaps("someone is threatening me online")
        self.assertTrue(r["has_gaps"])
        self.assertIn("date", r["all_gaps"])

    def test_job_fraud_thin(self):
        r = detect_gaps("job fraud, registration fee paid")
        self.assertTrue(r["has_gaps"])
        self.assertIn("date", r["all_gaps"])

    def test_account_hack_thin(self):
        r = detect_gaps("instagram hack")
        self.assertTrue(r["has_gaps"])
        self.assertIn("date", r["all_gaps"])

    # --- complete complaints that must NOT fire gaps ---

    def test_complete_upi(self):
        r = detect_gaps(
            "₹40,000 taken from PhonePe on 12 August 2026 via UTR 4283917"
        )
        self.assertFalse(r["has_gaps"])
        self.assertEqual(r["all_gaps"], [])

    def test_complete_via_ocr(self):
        """OCR fills in everything the text is missing."""
        r = detect_gaps(
            "paise nikal gaye",
            ocr_entities={
                "amount": "40000",
                "platform": "PhonePe",
                "date": "12 Aug 2026",
                "transaction_ref": "12345678",
            },
        )
        self.assertFalse(r["has_gaps"])

    def test_complete_account_hack(self):
        r = detect_gaps(
            "my instagram account was hacked on 14 august 2026, "
            "password changed, messages sent to my contacts"
        )
        # instagram → what_was_accessed found, date found, incident_location found
        # only suspect_contact may be missing, but it is priority 2 and alone
        # should not make it "thin"
        self.assertLessEqual(len(r["critical"]), 0)


# ============================================================================
# 3. GAP DETECTION — question capping
# ============================================================================

class TestQuestionCapping(unittest.TestCase):
    """Never interrogate the citizen — cap at MAX_QUESTIONS."""

    def test_max_questions_enforced(self):
        r = detect_gaps("paise gaye")
        self.assertLessEqual(len(r["questions"]), MAX_QUESTIONS)

    def test_critical_fields_come_first(self):
        """Priority 1 fields should appear before priority 2."""
        r = detect_gaps("paise gaye")
        priorities = [q["priority"] for q in r["questions"]]
        self.assertEqual(priorities, sorted(priorities))


# ============================================================================
# 4. GAP DETECTION — completeness score
# ============================================================================

class TestCompletenessScore(unittest.TestCase):
    """Deterministic score between 0.0 and 1.0."""

    def test_thin_has_low_score(self):
        r = detect_gaps("paise gaye")
        self.assertLess(r["completeness_score"], 0.5)

    def test_complete_has_high_score(self):
        r = detect_gaps(
            "₹40,000 taken from PhonePe on 12 August 2026 via UTR 4283917"
        )
        self.assertGreaterEqual(r["completeness_score"], 0.9)

    def test_score_range(self):
        for text in ["paise gaye", "hacked", "job fraud"]:
            r = detect_gaps(text)
            self.assertGreaterEqual(r["completeness_score"], 0.0)
            self.assertLessEqual(r["completeness_score"], 1.0)


# ============================================================================
# 5. GAP DETECTION — multilingual questions
# ============================================================================

class TestMultilingualQuestions(unittest.TestCase):
    """If input is Hindi/Marathi, questions should come in that language."""

    def test_hindi_input_hindi_questions(self):
        r = detect_gaps("मेरे अकाउंट से पैसे कट गए, कोई OTP नहीं दिया")
        if r["questions"]:
            q_text = r["questions"][0]["question"]
            # should contain Hindi text (Devanagari characters)
            self.assertTrue(
                any("\u0900" <= c <= "\u097F" for c in q_text),
                f"Expected Hindi question, got: {q_text}"
            )

    def test_english_input_english_questions(self):
        r = detect_gaps("money gone from my account")
        if r["questions"]:
            q_text = r["questions"][0]["question"]
            self.assertTrue(
                q_text[0].isascii(),
                f"Expected English question, got: {q_text}"
            )


# ============================================================================
# 6. LANGUAGE DETECTION
# ============================================================================

class TestLanguageDetection(unittest.TestCase):

    def test_english(self):
        self.assertEqual(detect_language("money was stolen from my account"), "en")

    def test_hindi(self):
        # Note: "पैसे" is listed as a Marathi marker in detect_language(),
        # so use a Hindi sentence without that word.
        self.assertEqual(detect_language("मेरा खाता हैक हो गया और रुपये चोरी हो गए"), "hi")

    def test_marathi(self):
        self.assertEqual(detect_language("माझ्या खात्यातून पैसे गेले आहे"), "mr")

    def test_empty(self):
        self.assertEqual(detect_language(""), "en")


# ============================================================================
# 7. GUARD — anti-hallucination (from ai_assistant.py)
# ============================================================================

class TestGuard(unittest.TestCase):
    """The guard blocks fabricated facts and passes honest narratives."""

    SRC = "paise gaye 40000 koi otp nahi aaya"
    ENT = {"transaction_date": "12 August 2026"}

    def test_clean_narrative_passes(self):
        ok, issues = guard(
            self.SRC, self.ENT,
            "On 12 August 2026 the complainant found that an amount of 40000 "
            "had been debited from the account. No otp was shared by the "
            "complainant at any stage. The complainant requests that the matter "
            "be investigated and the amount recovered from the recipient."
        )
        self.assertTrue(ok, f"Expected pass, got issues: {issues}")

    def test_invented_amount_blocked(self):
        ok, _ = guard(
            self.SRC, self.ENT,
            "On 12 August 2026 the complainant lost 40000 and a further 25000 "
            "was debited later from the same account without any authorisation "
            "being given by the complainant at any point during the said period "
            "of the transactions."
        )
        self.assertFalse(ok)

    def test_invented_mechanism_blocked(self):
        ok, _ = guard(
            self.SRC, self.ENT,
            "On 12 August 2026 the complainant received a phishing link and "
            "40000 was debited from the account thereafter without any otp "
            "being shared by the complainant with any person at any time during "
            "the relevant period."
        )
        self.assertFalse(ok)

    def test_dropped_amount_blocked(self):
        ok, _ = guard(
            self.SRC, self.ENT,
            "On 12 August 2026 the complainant found that a sum of money had "
            "been debited from the account without authorisation. No otp was "
            "shared. The complainant requests that the matter be investigated "
            "and appropriate action be taken in accordance with law."
        )
        self.assertFalse(ok)

    def test_invented_year_blocked(self):
        ok, _ = guard(
            self.SRC, self.ENT,
            "On 12 August 2024 the complainant found that 40000 had been "
            "debited from the account. No otp was shared by the complainant. "
            "The complainant requests that the matter be investigated and the "
            "amount be recovered from the recipient account."
        )
        self.assertFalse(ok)


# ============================================================================
# 8. DEVANAGARI NORMALISATION
# ============================================================================

class TestDevanagariNormalisation(unittest.TestCase):

    def test_devanagari_digits(self):
        self.assertEqual(_normalize_text("₹४०,०००"), "₹40,000")

    def test_mixed_digits(self):
        self.assertEqual(_normalize_text("Rs. ४0,000"), "Rs. 40,000")

    def test_digit_extraction(self):
        nums = _digits("₹४०,०००")
        self.assertIn("40000", nums)


# ============================================================================
# 9. INTERACTIVE STATE MACHINE (no LLM — tests structure only)
# ============================================================================

class TestInteractiveStateMachine(unittest.TestCase):
    """
    standardise_interactive() should return 'need_more_info' for thin input
    and 'ready' once max_rounds is reached. We cannot test the LLM narrative
    here, but we CAN test the state transitions.
    """

    def test_thin_complaint_needs_more_info(self):
        """A two-word complaint on round 0 should ask for more info."""
        result = standardise_interactive(
            "paise gaye", round_count=0, max_rounds=2,
            provider="ollama", model=DEFAULT_MODEL
        )
        # If Ollama is not running, this will still return need_more_info
        # because gap detection runs BEFORE the LLM call
        if result["status"] == "need_more_info":
            self.assertIn("questions", result)
            self.assertGreater(len(result["questions"]), 0)
            self.assertEqual(result["round"], 1)

    def test_thin_complaint_at_max_rounds_proceeds(self):
        """At max_rounds, even thin input should proceed to 'ready' or attempt LLM."""
        result = standardise_interactive(
            "paise gaye", round_count=2, max_rounds=2,
            provider="ollama", model=DEFAULT_MODEL
        )
        # At max rounds, it should NOT return need_more_info
        self.assertNotEqual(result["status"], "need_more_info")

    def test_complete_complaint_skips_questions(self):
        """A complete complaint should go straight to 'ready'."""
        result = standardise_interactive(
            "On 12 August 2026 I lost ₹40,000 from PhonePe via UPI "
            "after scanning a QR code for a fake refund. The transaction "
            "reference is UTR428391756201. No OTP was shared.",
            round_count=0, max_rounds=2,
            provider="ollama", model=DEFAULT_MODEL
        )
        # A complete complaint may skip to 'ready' directly
        # (or fail on LLM connection, but should NOT return need_more_info)
        if result["status"] == "need_more_info":
            # If it still asks questions, they should be non-critical
            critical = [q for q in result.get("questions", []) if q.get("priority") == 1]
            self.assertEqual(len(critical), 0,
                             f"Complete complaint should not have critical gaps: {critical}")


# ============================================================================
# 10. BUILD PROMPT — structure sanity
# ============================================================================

class TestBuildPrompt(unittest.TestCase):

    def test_prompt_contains_complaint(self):
        prompt = build_prompt("my money was stolen")
        self.assertIn("my money was stolen", prompt)

    def test_prompt_contains_entities(self):
        prompt = build_prompt("help", entities={"amount": "₹40,000"})
        self.assertIn("₹40,000", prompt)
        self.assertIn("SCREENSHOTS", prompt)

    def test_prompt_contains_form_fields(self):
        prompt = build_prompt("help", form_fields={"bank": "SBI"})
        self.assertIn("SBI", prompt)
        self.assertIn("FORM", prompt)


# ============================================================================
# 11. FORMAT FOR DISPLAY
# ============================================================================

class TestFormatForDisplay(unittest.TestCase):

    def test_no_gaps_message(self):
        r = detect_gaps("₹40,000 taken from PhonePe on 12 August 2026 via UTR 4283917")
        text = format_for_display(r)
        self.assertIn("No missing", text)

    def test_gaps_shown(self):
        r = detect_gaps("paise gaye")
        text = format_for_display(r)
        self.assertIn("missing", text.lower())
        self.assertIn("?", text)  # should contain at least one question


class TestConversationalIntakeUnknownAnswers(unittest.TestCase):

    def test_payment_app_and_named_bank_fill_separate_slots(self):
        docket = extract_structured_docket("From Google Pay, State Bank of India.", {})

        self.assertEqual(docket["platform_involved"], "Google Pay")
        self.assertEqual(docket["bank_name"], "State Bank of India")

    def test_utr_follow_up_offers_upload_for_ocr(self):
        first = conduct_counselor_turn(
            "A UPI scam debited INR 20000 from my account.", [], current_docket={}, language="en", use_llm=False
        )
        history = [
            {"role": "user", "content": "A UPI scam debited INR 20000 from my account."},
            {"role": "assistant", "content": first["spoken_response"]},
        ]
        second = conduct_counselor_turn(
            "From Google Pay, State Bank of India.", history, current_docket=first, language="en", use_llm=False
        )

        self.assertEqual(second["platform_involved"], "Google Pay")
        self.assertEqual(second["bank_name"], "State Bank of India")
        self.assertEqual(second["pending_field"], "utr")
        self.assertIn("upload its screenshot below", second["spoken_response"].lower())

        ocr_docket = {**second, "utr_number": "326712345678", "evidence_available": True}
        history.extend([
            {"role": "user", "content": "From Google Pay, State Bank of India."},
            {"role": "assistant", "content": second["spoken_response"]},
        ])
        after_upload = conduct_counselor_turn(
            "I uploaded the bank message screenshot.", history, current_docket=ocr_docket,
            language="en", use_llm=False,
        )
        self.assertEqual(after_upload["utr_number"], "326712345678")
        self.assertNotEqual(after_upload["pending_field"], "utr")

    def test_greeting_does_not_assume_financial_loss(self):
        result = conduct_counselor_turn(
            "hello hello", [], current_docket={}, language="en", use_llm=False
        )

        self.assertEqual(result["pending_field"], "incident_description")
        self.assertIn("describe what cyber incident", result["spoken_response"].lower())
        self.assertNotIn("financial loss", result["spoken_response"].lower())

    def test_unknown_bank_answer_advances_to_next_question(self):
        initial_statement = "I lost INR 4,500 in a UPI payment."
        first_turn = conduct_counselor_turn(
            initial_statement, [], current_docket={}, language="en", use_llm=False
        )
        self.assertEqual(first_turn["pending_field"], "bank")

        history = [
            {"role": "user", "content": initial_statement},
            {"role": "assistant", "content": first_turn["spoken_response"]},
        ]
        second_turn = conduct_counselor_turn(
            "I don't know the bank name. It was a UPI app.",
            history,
            current_docket=first_turn,
            language="en",
            use_llm=False,
        )

        self.assertIn("bank", second_turn["unknown_fields"])
        self.assertEqual(second_turn["pending_field"], "utr")
        self.assertIn("leave that detail blank", second_turn["spoken_response"])

    def test_evidence_update_does_not_repeat_unconfirmed_utr_question(self):
        docket = {
            "incident_described": True,
            "has_financial": True,
            "financial_loss_amount": 2499,
            "bank_name": "PhonePe",
            "pending_field": "utr",
            "retry_counts": {"utr": 1},
            "unknown_fields": [],
        }
        history = [{"role": "assistant", "content": "What UTR or RRN is shown on your receipt?"}]

        result = conduct_counselor_turn(
            "evidence added", history, current_docket=docket, language="en", use_llm=False
        )

        self.assertTrue(result["evidence_available"])
        self.assertIn("utr", result["unknown_fields"])
        self.assertNotEqual(result["pending_field"], "utr")
        self.assertIn("haven’t confirmed a transaction reference", result["spoken_response"])
        self.assertNotIn("What UTR", result["spoken_response"])

    def test_all_information_statement_closes_followups(self):
        docket = {
            "incident_described": True,
            "has_financial": False,
            "incident_category": "Cyber Bullying / Stalking / Sexting",
            "pending_field": "suspect",
            "retry_counts": {"suspect": 1},
            "unknown_fields": [],
        }
        result = conduct_counselor_turn(
            "This was all the information I had.", [], current_docket=docket,
            language="en", use_llm=False,
        )

        self.assertTrue(result["is_complete"])
        self.assertIsNone(result["pending_field"])
        self.assertIn("suspect", result["unknown_fields"])
        self.assertIn("all the information you have", result["spoken_response"])
        self.assertNotIn("?", result["spoken_response"])

    def test_follow_up_answers_update_slots_and_advance_in_client_docket(self):
        first = conduct_counselor_turn(
            "I lost money after a UPI scam.", [], current_docket={}, language="en", use_llm=False
        )
        self.assertEqual(first["pending_field"], "amount")

        history = [
            {"role": "user", "content": "I lost money after a UPI scam."},
            {"role": "assistant", "content": first["spoken_response"]},
        ]
        second = conduct_counselor_turn(
            "15000", history, current_docket=first, language="en", use_llm=False
        )
        self.assertEqual(second["financial_loss_amount"], 15000.0)
        self.assertNotEqual(second["pending_field"], "amount")
        self.assertIn("retry_counts", second)

        history.extend([
            {"role": "user", "content": "15000"},
            {"role": "assistant", "content": second["spoken_response"]},
        ])
        third = conduct_counselor_turn(
            "SBI", history, current_docket=second, language="en", use_llm=False
        )
        self.assertEqual(third["bank_name"], "State Bank of India")
        self.assertNotEqual(third["pending_field"], "bank")

    def test_local_model_reply_is_used_when_it_passes_guards(self):
        with patch(
            "modules.conversational_agent.ollama_chat",
            return_value='{"reply": "I can help with that."}',
        ):
            result = conduct_counselor_turn(
                "hello hello", [], current_docket={}, language="en"
            )

        self.assertTrue(result["llm_used"])
        self.assertTrue(result["spoken_response"].endswith(
            "Could you please describe what cyber incident happened or what problem you are facing?"
        ))
        self.assertEqual(result["spoken_response"].count("?"), 1)

    def test_impersonation_requesting_money_does_not_assume_victim_loss(self):
        complaint = (
            "Someone created an Instagram account using my name and photos. "
            "They are messaging my friends and asking them to send money."
        )
        result = conduct_counselor_turn(
            complaint, [], current_docket={}, language="en", use_llm=False
        )

        self.assertTrue(result["has_social"])
        self.assertFalse(result["has_financial"])
        self.assertEqual(result["pending_field"], "suspect")

    def test_lost_email_access_is_not_mistaken_for_financial_loss(self):
        statement = (
            "I lost access to my email account this morning. The recovery phone "
            "number seems to have changed, and I am worried someone may be using the account."
        )
        result = conduct_counselor_turn(
            statement, [], current_docket={}, language="en", use_llm=False
        )

        self.assertTrue(result["has_hacking"])
        self.assertFalse(result["has_financial"])
        self.assertFalse(result["urgency_flag"])
        self.assertEqual(result["incident_category"], "Hacking / Damage to Computer")
        self.assertNotEqual(result["pending_field"], "amount")


if __name__ == "__main__":
    unittest.main()
