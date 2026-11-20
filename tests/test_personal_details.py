"""Guided form requirements also apply when submitting via the API."""
import unittest
from modules.personal_details import validate_personal_details


class PersonalDetailsTests(unittest.TestCase):
    def valid(self):
        return dict(name='Example Citizen', phone='9876543210', age=25,
                    state='Maharashtra', district='Pune', pincode='411001')

    def test_normalizes_phone_and_preserves_pin_for_case_pdf(self):
        result = validate_personal_details(self.valid())
        self.assertEqual(result['phone'], '+91 9876543210')
        self.assertEqual(result['pincode'], '411001')
        self.assertEqual(result['age'], 25)

    def test_missing_or_invalid_age_is_rejected(self):
        for age in (None, '', 0, 121, 20.5, True):
            with self.subTest(age=age), self.assertRaisesRegex(ValueError, 'age'):
                validate_personal_details(dict(self.valid(), age=age))

    def test_wrong_state_district_pair_and_invalid_pin_are_rejected(self):
        for change in ({'state': 'Unknown'}, {'district': 'Bengaluru Urban'},
                       {'pincode': ''}, {'pincode': '012345'}, {'phone': '+1 2125551234'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_personal_details(dict(self.valid(), **change))
