"""
TEST SUITE — Sentiment Analysis, Urgency & Complaint Comprehension

Tests:
  1. Emotional tone categorization (Panicked, Anxious/Threatened, Frustrated, Neutral)
  2. Urgency triage & Golden Hour fund freeze protocol (<24h financial loss)
  3. Empathetic citizen reassurance & protective guidance generation
  4. Crime vector & modus operandi comprehension
  5. Interactive Q&A flow (answering gaps improves narrative & completeness)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.sentiment_analysis import (
    analyze_sentiment_and_urgency,
    _detect_crime_vector,
    _extract_amount,
)
from modules.gap_detection import detect_gaps
from modules.ai_assistant import standardise_interactive


class TestSentimentAnalysis(unittest.TestCase):
    """Verify emotion, distress, and tone detection."""

    def test_panic_detection_hinglish(self):
        text = "Sir please help urgently, sab loot gaya, paise chale gaye 40000 bachao kripya madad karo!"
        res = analyze_sentiment_and_urgency(text)
        self.assertEqual(res["tone"], "PANICKED_DISTRESSED")
        self.assertGreater(res["distress_score"], 0.5)
        self.assertIn("Financial Panic", res["emotion_tags"])

    def test_extortion_blackmail_tone(self):
        text = "Someone is blackmailing me on Instagram saying they have a private video and threatening to leak it to my family and contacts if I do not pay."
        res = analyze_sentiment_and_urgency(text)
        self.assertEqual(res["tone"], "ANXIOUS_THREATENED")
        self.assertEqual(res["urgency_level"], "HIGH_URGENCY")
        self.assertIn("Extortion/Blackmail Anxiety", res["emotion_tags"])
        # Verify protective advice warns not to pay
        self.assertTrue(any("DO NOT transfer" in step for step in res["reassurance"]["immediate_steps"]))

    def test_anger_frustration_tone(self):
        text = "I have been cheated by this criminal scammer on a fake job portal. Strictest punishment and police action must be taken, bank did nothing."
        res = analyze_sentiment_and_urgency(text)
        self.assertEqual(res["tone"], "FRUSTRATED_ANGRY")

    def test_neutral_reporting(self):
        text = "On 15 January 2026, an unauthorized debit of Rs. 15,000 occurred via net banking. Please look into this matter."
        res = analyze_sentiment_and_urgency(text)
        self.assertEqual(res["tone"], "NEUTRAL_INFORMATIONAL")


class TestUrgencyAndGoldenHour(unittest.TestCase):
    """Verify Golden Hour triage (<24h fund freeze priority)."""

    def test_golden_hour_flag_triggered(self):
        text = "Today morning I clicked a refund link and Rs. 50,000 was debited just now without OTP. Help me freeze the account!"
        res = analyze_sentiment_and_urgency(text)
        self.assertTrue(res["is_golden_hour"])
        self.assertEqual(res["urgency_level"], "EMERGENCY_GOLDEN_HOUR")
        self.assertGreaterEqual(res["urgency_score"], 0.9)
        self.assertIn("1930", res["reassurance"]["message"])

    def test_golden_hour_with_entities(self):
        text = "Abhi thodi der pehle paise kat gaye"
        ents = {"amount": "Rs. 25,000"}
        res = analyze_sentiment_and_urgency(text, entities=ents)
        self.assertTrue(res["is_golden_hour"])
        self.assertEqual(res["urgency_level"], "EMERGENCY_GOLDEN_HOUR")

    def test_standard_urgency_for_older_cases(self):
        text = "Last month on 3 August 2025 I received a spam call claiming lottery."
        res = analyze_sentiment_and_urgency(text)
        self.assertFalse(res["is_golden_hour"])
        self.assertIn(res["urgency_level"], ["MODERATE_URGENCY", "LOW_URGENCY"])


class TestCrimeVectorComprehension(unittest.TestCase):
    """Verify crime vector extraction and executive summary."""

    def test_qr_code_phishing(self):
        text = "Refund ke liye QR code scan kiya paytm pe aur paise chale gaye"
        vector = _detect_crime_vector(text, {})
        self.assertIn("QR", vector)

    def test_digital_arrest(self):
        text = "Someone called claiming to be CBI police officer and kept me under digital arrest on Skype call"
        vector = _detect_crime_vector(text, {})
        self.assertIn("Digital Arrest", vector)

    def test_loan_app_extortion(self):
        text = "Instant loan app recovery agents are abusing and calling all contacts"
        vector = _detect_crime_vector(text, {})
        self.assertIn("Loan App", vector)

    def test_amount_extraction(self):
        self.assertEqual(_extract_amount("Kat gaye Rs. 75,000 via UPI"), "Rs. 75,000")
        self.assertEqual(_extract_amount("50000 kat gaye"), "Rs. 50000")


class TestInteractiveQAFlow(unittest.TestCase):
    """Verify the interactive Q&A state machine and completeness progression."""

    def test_interactive_progression(self):
        thin_story = "paise chale gaye 40000"
        initial_gaps = detect_gaps(thin_story)
        initial_score = initial_gaps["completeness_score"]
        self.assertTrue(initial_gaps["is_thin"])
        self.assertGreaterEqual(len(initial_gaps["questions"]), 1)

        # Citizen answers follow-up questions in round 1
        answers = {
            "transaction_ref": "428391756201",
            "date": "10 February 2026",
            "suspect_upi": "scammer@okhdfcbank",
        }
        updated_story = thin_story + "\n[Additional Details]: UTR: 428391756201, Date: 10 February 2026, Suspect UPI: scammer@okhdfcbank"

        # Re-evaluate
        updated_gaps = detect_gaps(updated_story)
        updated_score = updated_gaps["completeness_score"]

        # Completeness should improve significantly
        self.assertGreater(updated_score, initial_score)

        # Standardise interactive transitions properly
        res = standardise_interactive(updated_story, round_count=1)
        self.assertIn("status", res)
        self.assertIn("sentiment", res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
