"""OCR entity extraction checks that do not require a Tesseract install."""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from modules.ocr_extract import extract_entities, format_entity_reading


class TestOcrEntityExtraction(unittest.TestCase):
    def test_ocr_readings_format_mixed_scalar_and_list_values_for_tables(self):
        values = [
            "4500",
            ["4500", "9000"],
            [{"value": "TEST-UPI-001", "confidence": 0.9}],
            None,
        ]

        readings = [format_entity_reading(value) for value in values]

        self.assertEqual(readings, ["4500", "4500; 9000", "TEST-UPI-001", "Not detected"])
        self.assertTrue(all(isinstance(reading, str) for reading in readings))

    def test_transaction_reference_label_is_not_captured_as_the_value(self):
        text = "Transaction reference TEST-UPI-20261015-001"

        found = extract_entities(text)

        self.assertEqual(found["transaction_ref"][0]["value"], "TEST-UPI-20261015-001")

    def test_utr_label_extracts_the_number(self):
        found = extract_entities("UTR: 326712345678")

        self.assertEqual(found["transaction_ref"][0]["value"], "326712345678")

    def test_upi_is_recognized_as_a_payment_platform(self):
        found = extract_entities("Payment method UPI")

        self.assertEqual(found["platform"][0]["value"], "UPI")


if __name__ == "__main__":
    unittest.main()
