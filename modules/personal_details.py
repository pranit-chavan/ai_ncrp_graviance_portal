"""Validate guided contact details against the bundled offline LGD directory."""
import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def location_directory():
    path = Path(__file__).resolve().parents[1] / 'static' / 'data' / 'india-locations.json'
    return json.loads(path.read_text(encoding='utf-8'))['states']


def validate_personal_details(person):
    result = dict(person)
    if not str(result.get('name') or '').strip():
        raise ValueError('Please enter your full name.')
    phone = str(result.get('phone') or '').strip()
    if not re.fullmatch(r'[+\d\s()-]*', phone):
        raise ValueError('Please enter a 10-digit Indian phone number.')
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]
    if not re.fullmatch(r'[1-9]\d{9}', digits):
        raise ValueError('Please enter a 10-digit Indian phone number.')
    result['phone'] = '+91 ' + digits
    age = str(result.get('age') or '')
    if not re.fullmatch(r'\d{1,3}', age) or not 1 <= int(age) <= 120:
        raise ValueError('Please enter your age in completed years, from 1 to 120.')
    result['age'] = int(age)
    state = next((item for item in location_directory() if item['name'] == result.get('state')), None)
    if not state:
        raise ValueError('Please choose your state or union territory from the list.')
    if not any(item['name'] == result.get('district') for item in state['districts']):
        raise ValueError('Please choose a district for your selected state or union territory.')
    if not re.fullmatch(r'[1-9]\d{5}', str(result.get('pincode') or '')):
        raise ValueError('Please enter a six-digit PIN code.')
    result['pincode'] = str(result['pincode'])
    return result
