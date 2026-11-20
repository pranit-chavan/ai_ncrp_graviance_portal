"""Regression tests for grounded fields and reviewed category/legal mapping."""
import unittest
from unittest.mock import patch
from modules.guided_intake import GuidedTurn, GuidedReview, guided_turn, guided_review


class TestGuidedIntake(unittest.TestCase):
    def test_missing_model_preserves_grounded_intake(self):
        with patch('modules.conversational_agent.ollama_chat', side_effect=RuntimeError('unavailable')):
            result = guided_turn(GuidedTurn(message='Someone created a fake Instagram profile using my photos.'))
        self.assertTrue(result['ok'])
        self.assertFalse(result['docket']['llm_used'])
        self.assertIsNone(result['docket']['date_time_of_incident'])
        self.assertIsNone(result['docket']['financial_loss_amount'])
        self.assertIn('?', result['reply'])

    def test_local_model_acknowledgement_is_used(self):
        with patch('modules.conversational_agent.ollama_chat', return_value='{"reply":"I understand."}'):
            result = guided_turn(GuidedTurn(message='Someone created a fake Instagram profile using my photos.'))
        self.assertTrue(result['docket']['llm_used'])
        self.assertIn('I understand.', result['reply'])
        self.assertEqual(result['reply'].count('?'), 1)

    def test_job_fee_prompt_checks_for_loss_without_inventing_a_payment(self):
        result = guided_turn(GuidedTurn(message='Someone sent me a fake job offer and asked me to pay a fee.'))
        self.assertEqual(result['docket']['pending_field'], 'amount')
        self.assertIsNone(result['docket']['financial_loss_amount'])
        self.assertIn('If no money was taken', result['reply'])

    def test_model_question_and_unrelated_reassurance_are_removed(self):
        with patch('modules.conversational_agent.ollama_chat', return_value='{"reply":"I understand. I am here if you need to talk. Do you have a suspect profile?"}'):
            result = guided_turn(GuidedTurn(message='Someone sent me a fake job offer and asked me to pay a fee.'))
        self.assertTrue(result['docket']['llm_used'])
        self.assertIn('I understand.', result['reply'])
        self.assertNotIn('talk', result['reply'].lower())
        self.assertEqual(result['reply'].count('?'), 1)

    def test_review_uses_corrected_category_and_age(self):
        with patch('modules.guided_intake.classify_complaint_text', return_value={'predicted_category':'UPI Related Frauds'}), patch('modules.guided_intake.map_sections', return_value={}) as law:
            result = guided_review(GuidedReview(narrative='A fictional account of online harassment.', age=16, category='Cyber Bullying / Stalking / Sexting'))
        self.assertEqual(result['category'], 'Cyber Bullying / Stalking / Sexting')
        law.assert_called_once_with('Cyber Bullying / Stalking / Sexting', complainant_age=16)

    def test_unrecognized_category_cannot_override_classifier(self):
        with patch('modules.guided_intake.classify_complaint_text', return_value={'predicted_category':'Online Job Fraud'}):
            result = guided_review(GuidedReview(narrative='Someone requested a fee for a fictional job offer.', category='invented category'))
        self.assertEqual(result['category'], 'Online Job Fraud')

    def test_zero_loss_is_retained_as_an_explicit_fact(self):
        with patch('modules.guided_intake.classify_complaint_text', return_value={'predicted_category':'Email Phishing'}) as classify:
            guided_review(GuidedReview(narrative='I received a suspicious email but did not pay.', fields={'financial_loss_amount':0}))
        self.assertIn('financial loss amount: 0', classify.call_args.args[0])
