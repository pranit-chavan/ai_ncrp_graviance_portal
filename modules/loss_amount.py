"""Conservative extraction of money actually paid, rather than money mentioned."""
import re
from decimal import Decimal

NUMBER = r'\d[\d,]*(?:\.\d{1,2})?(?:\s*(?:lakh|lac|crore|thousand|k)\b)?'
MONEY = re.compile(r'(?<![\w])(?:rs\.?\s*|inr\s*|₹\s*)?(' + NUMBER + r')(?:\s*(?:rs\.?|rupees?|inr)\b)?', re.I)


def value(text):
    match = re.fullmatch(r'([\d,.]+)\s*(lakh|lac|crore|thousand|k)?', text, re.I)
    scale = {'lakh':100000, 'lac':100000, 'crore':10000000, 'thousand':1000, 'k':1000}
    return Decimal(match[1].replace(',', '')) * scale.get((match[2] or '').lower(), 1)


def extract_loss(text):
    """Return a grounded total, or None when the account needs clarification.

    Only outgoing payments or explicit loss claims are counted. Incoming rewards,
    requested fees and unpaid amounts do not become losses. Corrections replace
    the preceding payment. Decimal arithmetic avoids floating-point sums.
    """
    payments = []
    total = None
    normalized = re.sub(r'\brs\.', 'rs', text.lower())
    clauses = re.split(r'[;!?\n]|\.(?!\d)|\b(?:then|later|but|and then)\b', normalized)
    for clause in clauses:
        matches = list(MONEY.finditer(clause))
        for index, match in enumerate(matches):
            before = clause[matches[index-1].end() if index else 0:match.start()]
            after = clause[match.end():matches[index+1].start() if index+1 < len(matches) else len(clause)]
            amount = value(match[1])
            if not 0 <= amount <= 100000000:
                continue
            correction = re.search(r'\b(?:actually(?:\s+i checked)?(?:\s+it)?(?:\s+was)?|correct amount(?:\s+was)?|i checked it was)\s*(?:rs\.?|inr|₹)?\s*$', before)
            if correction and payments:
                payments[-1] = amount
                continue
            if re.search(r'\b(?:total(?: loss)?|lost in total|overall loss)\s*(?:was|is|of|:)?\s*(?:rs\.?|inr|₹)?\s*$', before):
                total = amount
                continue
            money_reported_gone = re.search(
                r'\b(?:(?:my|our|the)\s+)?(?:money|funds|cash|amount)\s+'
                r'(?:(?:is|was|has)\s+)?(?:gone|lost|stolen|missing)\b',
                before,
            )
            outgoing = re.search(r'\b(?:i|we)\s+(?:had\s+)?(?:paid|sent|transferred|lost)\b|\b(?:debited|deducted|stolen)\b', before) or money_reported_gone
            context = before[outgoing.start():] if outgoing else before
            if re.search(r"\b(?:didn'?t|did not|never|not)\s+(?:pay|send|transfer)|\b(?:asked|told|demanded|requested|earn|salary|reward|received)\b", context):
                continue
            passive = re.search(r'\b(?:was |were )?(?:debited|deducted|stolen)\b', after)
            continuation = payments and re.fullmatch(r'\s*(?:,|and|plus|another|again|also|rs\.?|inr|₹|\s)+', before)
            if outgoing or passive or continuation:
                payments.append(amount)
    calculated = sum(payments, Decimal(0)) if payments else None
    if total is not None:
        return float(total) if calculated is None or calculated == total else None
    return float(calculated) if calculated is not None else None
