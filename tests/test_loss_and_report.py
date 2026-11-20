import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pypdf import PdfReader
from modules.loss_amount import extract_loss
from modules.conversational_agent import conduct_counselor_turn, _parse_pending_amount_answer
from modules.case_file import write_pdf


STORY = ('They offered a work from home job. They first gave me small tasks and sent 150 rs so I thought it was real. '
         'Later they said pay registration fee and I sent around 2000, actually I checked it was 2499. '
         'Then another person told me to pay 5000 to unlock my earnings but I didnt pay that.')


class LossAndReportTests(unittest.TestCase):
    def test_reward_estimate_correction_and_unpaid_demand(self):
        self.assertEqual(extract_loss(STORY), 2499)
        with patch('modules.conversational_agent._reply_with_model', return_value=''):
            result = conduct_counselor_turn(STORY, [], {}, language='en')
        self.assertEqual(result['financial_loss_amount'], 2499)

    def test_multiple_payments_decimals_and_scales(self):
        for text, amount in [('I paid Rs. 2499 and Rs. 5000.',7499), ('I paid Rs 100.25. I sent Rs 20.50.',120.75), ('I lost 1.5 lakh rupees.',150000), ('I paid 2000. Total loss was 2000.',2000), ('They asked for a fee and I paid 2499.',2499)]:
            self.assertEqual(extract_loss(text),amount,text)
        self.assertIsNone(extract_loss('I paid 2000. Total loss was 5000.'))

    def test_requested_and_received_money_not_loss(self):
        for text in ['They sent 150 rs.', 'They asked me to pay Rs 5000.', 'I did not pay Rs 5000.', 'I received 150 rupees.']:
            self.assertIsNone(extract_loss(text),text)
            self.assertIsNone(_parse_pending_amount_answer(text),text)
        self.assertEqual(_parse_pending_amount_answer('1.5 lakh'),150000)
        self.assertEqual(_parse_pending_amount_answer('none'),0)

    def test_complete_report_without_score_and_escaped_text(self):
        case = sample_case()
        with tempfile.TemporaryDirectory() as folder:
            path=write_pdf(case,str(Path(folder)/'report.pdf'))
            text='\n'.join(page.extract_text() for page in PdfReader(path).pages)
        for expected in ['INR 2,499.00','Online Job Fraud','Your original complaint','Structured complaint prepared by the system','Evidence attached','Test <Citizen>']:
            self.assertIn(expected,text)
        for jargon in ['Category match score','82 / 100','Module A','LinearSVC','Statutory Offence','Forensic Reconciliation']:
            self.assertNotIn(jargon,text)

    def test_download_timestamp_legal_sections_and_all_evidence(self):
        import io
        from datetime import datetime, timezone
        from modules.complaint_pdf import write_complaint_pdf
        case=sample_case()
        case['legal_sections']={'it_act':[{'section':'TEST-A','description':'Test IT provision'}], 'bns':[{'section':'TEST-B','description':'Test BNS provision'}], 'other':[{'act':'Test Act','section':'TEST-C'}], 'conditional_applied':[{'status':'Needs age review'}]}
        case['evidence']['table']=[{'filename':'another.txt','description':'Additional attachment'}]
        stream=io.BytesIO()
        write_complaint_pdf(case,stream,datetime(2026,11,21,9,0,tzinfo=timezone.utc))
        pages=PdfReader(stream).pages
        text='\n'.join(page.extract_text() for page in pages)
        for expected in ['02:30:00 PM IST','TEST-A','TEST-B','TEST-C','Needs age review','sample-payment.png','another.txt']:
            self.assertIn(expected,text)
        for page in pages:
            self.assertIn('System using NLP',page.extract_text())
            self.assertIn('Downloaded:',page.extract_text())


def sample_case():
    return {'reference':'TEST-REPORT-001','generated_at':'2026-11-21T10:30:00',
        'complainant':{'name':'Test <Citizen>','age':25,'state':'Maharashtra','district':'Pune','pincode':'411001'},
        'incident':{'sub_category_reported':'Online Job Fraud','location':['WhatsApp','PhonePe']},
        'complaint':{'raw_text':STORY},'classification':{'sub_category':'Online Job Fraud','confidence':0.82},
        'transactions':[{'amount':2499,'bank':'PhonePe'}], 'evidence':{'attachments':[{'name':'sample-payment.png'}]}}
