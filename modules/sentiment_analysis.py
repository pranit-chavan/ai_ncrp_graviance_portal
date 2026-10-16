"""
SENTIMENT, URGENCY & COMPLAINT COMPREHENSION ENGINE

Specialized for Indian cybercrime complaints across English, Hindi, Hinglish, and Marathi.
Analyzes:
  1. Emotional Tone & Distress Level (Panic, Extortion/Blackmail Fear, Frustration, Neutral)
  2. Urgency & Golden Hour Protocol (Emergency < 24h financial loss for 1930 / I4C fund freeze)
  3. Empathetic Citizen Reassurance & Tactical Guidance
  4. Executive Complaint Comprehension & Crime Vector Synopsis
"""

import re
from datetime import datetime, date, timedelta

# =============================================================================
# 1. LEXICONS FOR EMOTIONAL TONE & DISTRESS
# =============================================================================

PANIC_KEYWORDS = [
    # English
    r"\bhelp\b", r"\burgent\b", r"\burgently\b", r"\bplease help\b", r"\bsave me\b",
    r"\bruined\b", r"\blost everything\b", r"\ball my money\b", r"\blife savings\b",
    r"\bentire savings\b", r"\bemergency\b", r"\bcrying\b", r"\bsuicide\b", r"\bhopeless\b",
    r"\bdevastated\b", r"\bdesperate\b", r"\bhelpless\b", r"\bbegging\b",
    # Hindi / Hinglish / Marathi
    r"\bbachao\b", r"\bmadad\b", r"\bkripya madad\b", r"\bsab loot gaya\b", r"\bkuch nahi bacha\b",
    r"\bbarbaad\b", r"\bpaise chale gaye\b", r"\bsare paise\b", r"\bro raha\b", r"\bro rahi\b",
    r"\bgareeb hu\b", r"\bkripya sahayata\b", r"\bmar jaunga\b", r"\bmar jaungi\b",
    r"\bpaise wapas dila do\b", r"\bbhot pareshan\b", r"\bkhup tras\b", r"\bmadat kara\b"
]

BLACKMAIL_THREAT_KEYWORDS = [
    # English
    r"\bblackmail\b", r"\bblackmailing\b", r"\bthreat\b", r"\bthreatening\b", r"\bleak\b",
    r"\bprivate video\b", r"\bprivate photos\b", r"\bnude\b", r"\bnudes\b", r"\bmorphed\b",
    r"\bdeepfake\b", r"\bextortion\b", r"\bextorting\b", r"\bshare with family\b",
    r"\bshare on contacts\b", r"\bpost on social media\b", r"\bviral\b", r"\bdefame\b",
    r"\bloan app\b", r"\brecovery agent\b", r"\babusing\b", r"\bharassing\b",
    # Hindi / Hinglish
    r"\bdhamki\b", r"\bdhamka raha\b", r"\bdhamki de raha\b", r"\bphoto viral\b",
    r"\bvideo viral\b", r"\bizzat\b", r"\bbadnaam\b", r"\bgande photo\b", r"\bgande video\b",
    r"\bgandi photos\b", r"\bgandi videos\b", r"\bcontacts ko bhej\b", r"\bgali de rahe\b"
]

ANGER_FRUSTRATION_KEYWORDS = [
    # English
    r"\bcheat\b", r"\bcheated\b", r"\bfraudster\b", r"\bscammer\b", r"\bridiculous\b",
    r"\baction must be taken\b", r"\barrest them\b", r"\bunacceptable\b", r"\bnegligence\b",
    r"\bbank did nothing\b", r"\blied\b", r"\bthief\b", r"\bcriminal\b", r"\bstrictest punishment\b",
    # Hindi / Hinglish
    r"\bdhoka\b", r"\bdhokhadhadi\b", r"\bchori\b", r"\bchor\b", r"\bpolice action\b",
    r"\bgiraftar\b", r"\bsaza\b", r"\bbank wale kuch nahi\b", r"\bjhooth\b", r"\bfarzi\b"
]

GOLDEN_HOUR_INDICATORS = [
    # Immediate / today markers
    r"\btoday\b", r"\bjust now\b", r"\bfew minutes ago\b", r"\b1 hour ago\b", r"\b2 hours ago\b",
    r"\ban hour ago\b", r"\bthis morning\b", r"\bthis afternoon\b", r"\btonight\b", r"\baaj\b",
    r"\babhi\b", r"\babhi abhi\b", r"\bthodi der pehle\b", r"\baaj subah\b", r"\baaj dopahar\b",
    r"\baaj shaam\b", r"\byesterday\b", r"\bkal hi\b", r"\blast night\b", r"\bkal raat\b"
]


# =============================================================================
# 2. CORE SENTIMENT & COMPREHENSION ANALYZER
# =============================================================================

def analyze_sentiment_and_urgency(raw_text, entities=None, incident_datetime=None):
    """
    Analyzes citizen complaint text and extracted entities.
    Returns:
      {
        "tone": "PANICKED_DISTRESSED" | "ANXIOUS_THREATENED" | "FRUSTRATED_ANGRY" | "NEUTRAL_INFORMATIONAL",
        "tone_label": "Panicked / Acute Distress" | ...,
        "tone_emoji": "🚨" | "⚠️" | "😠" | "ℹ️",
        "distress_score": float (0.0 to 1.0),
        "urgency_level": "EMERGENCY_GOLDEN_HOUR" | "HIGH_URGENCY" | "MODERATE_URGENCY" | "LOW_URGENCY",
        "urgency_label": "Emergency (Golden Hour)" | "High Urgency" | ...,
        "urgency_score": float (0.0 to 1.0),
        "is_golden_hour": bool,
        "emotion_tags": list of str,
        "reassurance": {
            "title": str,
            "message": str,
            "immediate_steps": list of str,
            "helpline": "1930"
        },
        "comprehension": {
            "summary": str,
            "crime_vector": str,
            "financial_impact": str,
            "key_actors": dict,
            "completeness_score": float
        }
      }
    """
    text = (raw_text or "").strip().lower()
    ents = entities or {}

    # 1. Detect Keyword Matches
    panic_matches = [kw for kw in PANIC_KEYWORDS if re.search(kw, text)]
    threat_matches = [kw for kw in BLACKMAIL_THREAT_KEYWORDS if re.search(kw, text)]
    anger_matches = [kw for kw in ANGER_FRUSTRATION_KEYWORDS if re.search(kw, text)]
    golden_matches = [kw for kw in GOLDEN_HOUR_INDICATORS if re.search(kw, text)]

    # 2. Score Emotions & Distress
    panic_score = min(1.0, len(panic_matches) * 0.3)
    threat_score = min(1.0, len(threat_matches) * 0.35)
    anger_score = min(1.0, len(anger_matches) * 0.25)

    # Exclamation count and ALL CAPS emphasis (from raw_text)
    caps_ratio = sum(1 for c in raw_text if c.isupper()) / max(1, len(raw_text))
    exclamations = raw_text.count("!")
    emphasis_boost = min(0.3, (exclamations * 0.05) + (caps_ratio * 0.5))

    distress_score = min(1.0, max(panic_score + emphasis_boost, threat_score * 0.9, anger_score * 0.6))

    # 3. Determine Emotional Tone
    emotion_tags = []
    if threat_score >= 0.35 or len(threat_matches) >= 1:
        tone = "ANXIOUS_THREATENED"
        tone_label = "Anxious / Threatened (Extortion Risk)"
        tone_emoji = "⚠️"
        emotion_tags.append("Extortion/Blackmail Anxiety")
        if panic_score > 0.2:
            emotion_tags.append("Vulnerability")
    elif (panic_score >= 0.3 or len(panic_matches) >= 2) and panic_score >= anger_score:
        tone = "PANICKED_DISTRESSED"
        tone_label = "Panicked / Acute Distress"
        tone_emoji = "🚨"
        emotion_tags.append("Financial Panic")
        emotion_tags.append("Urgent Assistance Requested")
    elif anger_score >= 0.25 or len(anger_matches) >= 1:
        tone = "FRUSTRATED_ANGRY"
        tone_label = "Frustrated / High Grievance"
        tone_emoji = "😠"
        emotion_tags.append("Betrayal & Grievance")
    elif panic_score > 0 or distress_score >= 0.6:
        tone = "PANICKED_DISTRESSED"
        tone_label = "Panicked / Acute Distress"
        tone_emoji = "🚨"
        emotion_tags.append("Financial Panic")
    else:
        tone = "NEUTRAL_INFORMATIONAL"
        tone_label = "Neutral / Informational"
        tone_emoji = "ℹ️"
        emotion_tags.append("Objective Reporting")

    # 4. Determine Urgency & Golden Hour
    # Check if money was lost
    amount_str = ents.get("amount") or ""
    amount_in_text = _extract_amount(text)
    has_loss_verb = bool(re.search(r"\b(?:kat gaye|chale gaye|nikal gaye|debit|debited|lost|stolen|paid|transfer|sent|scammed)\b", text))
    has_amount = bool(amount_str or amount_in_text or (has_loss_verb and re.search(r"\b\d{4,8}\b", text)))

    is_golden_hour = False
    now = datetime.now()

    # Check temporal indicators
    if golden_matches and has_amount:
        is_golden_hour = True
    elif incident_datetime:
        try:
            if isinstance(incident_datetime, str):
                dt = datetime.fromisoformat(incident_datetime.replace("Z", "+00:00"))
            elif isinstance(incident_datetime, (datetime, date)):
                dt = incident_datetime if isinstance(incident_datetime, datetime) else datetime.combine(incident_datetime, datetime.min.time())
            else:
                dt = None
            if dt and (now - dt) <= timedelta(hours=24) and has_amount:
                is_golden_hour = True
        except Exception:
            pass

    # Urgency Level calculation
    if is_golden_hour:
        urgency_level = "EMERGENCY_GOLDEN_HOUR"
        urgency_label = "EMERGENCY (Golden Hour — <24h Fund Freeze Active)"
        urgency_score = 0.95
    elif tone == "ANXIOUS_THREATENED" or (threat_score >= 0.3):
        urgency_level = "HIGH_URGENCY"
        urgency_label = "High Urgency (Active Threat / Harassment)"
        urgency_score = 0.85
    elif has_amount or distress_score >= 0.5:
        urgency_level = "MODERATE_URGENCY"
        urgency_label = "Moderate Urgency (Financial Investigation)"
        urgency_score = 0.65
    else:
        urgency_level = "LOW_URGENCY"
        urgency_label = "Standard Triage"
        urgency_score = 0.35

    # 5. Formulate Empathetic Citizen Reassurance
    if is_golden_hour:
        reassurance_title = "Immediate Action: Golden Hour Fund Freeze"
        reassurance_msg = (
            "We understand how stressful this is, but taking immediate action gives the best chance "
            "of freezing your stolen funds. Under the Citizen Financial Cyber Fraud Reporting System (CFCFRMS), "
            "calling Helpline 1930 enables banks and payment aggregators to put an immediate lien on beneficiary accounts if reported promptly."
        )
        immediate_steps = [
            "Call the National Cyber Crime Helpline **1930** immediately to report the transaction ID (UTR).",
            "Contact your bank's 24/7 fraud helpline and request an urgent transaction block/chargeback.",
            "Keep your UPI app, SMS alerts, and bank transaction reference ready."
        ]
    elif tone == "ANXIOUS_THREATENED":
        reassurance_title = "Important Safety Advice & Emotional Reassurance"
        reassurance_msg = (
            "Please remember: You are the victim of a calculated crime, and you are not alone. "
            "Extortionists rely on panic, shame, and isolation to force quick payments. Paying will NOT stop them; "
            "it only invites further extortion demands."
        )
        immediate_steps = [
            "**DO NOT transfer any money or succumb to extortion demands.**",
            "Take screenshots of all chats, numbers, profile links, and payment handles for evidence.",
            "Block the fraudster on all platforms once evidence is saved.",
            "Report the profile directly to the social platform (Instagram/WhatsApp/Snapchat) to trigger account takedown."
        ]
    elif tone == "PANICKED_DISTRESSED":
        reassurance_title = "We Are Here to Help — Take a Breath"
        reassurance_msg = (
            "Take a deep breath. Your complaint is being structured with priority. Law enforcement and cybercrime "
            "officers review all verified details to initiate tracing and account freezes."
        )
        immediate_steps = [
            "Ensure you have answered all critical details (amounts, transaction IDs, phone numbers).",
            "If your bank account or card was compromised, call your bank to freeze internet banking and hotlist your card.",
            "Helpline **1930** is active 24/7 for immediate telephonic support."
        ]
    else:
        reassurance_title = "Official NCRP Complaint Registration"
        reassurance_msg = (
            "Your complaint is being analyzed and pre-filled into the National Cyber Crime Reporting Portal standard format. "
            "An investigating officer will review the legal sections and evidence."
        )
        immediate_steps = [
            "Review auto-extracted fields in Step 2 to ensure 100% accuracy.",
            "Attach payment receipts, SMS screenshots, or chat exports to strengthen evidentiary value."
        ]

    # 6. Overall Complaint Comprehension & Crime Vector
    crime_vector = _detect_crime_vector(text, ents)
    summary = _generate_complaint_summary(raw_text, ents, crime_vector, has_amount)

    key_actors = {
        "disputed_amount": ents.get("amount") or _extract_amount(text) or "Not specified",
        "suspect_identifiers": ents.get("phone") or ents.get("upi_id") or ents.get("email") or "Not provided",
        "platform_involved": ents.get("platform") or _detect_platform(text) or "Online / Digital Channel",
        "evidence_attached": bool(ents.get("transaction_ref") or ents.get("account_last4")),
    }

    return {
        "tone": tone,
        "tone_label": tone_label,
        "tone_emoji": tone_emoji,
        "distress_score": round(distress_score, 2),
        "urgency_level": urgency_level,
        "urgency_label": urgency_label,
        "urgency_score": round(urgency_score, 2),
        "is_golden_hour": is_golden_hour,
        "emotion_tags": emotion_tags,
        "reassurance": {
            "title": reassurance_title,
            "message": reassurance_msg,
            "immediate_steps": immediate_steps,
            "helpline": "1930"
        },
        "comprehension": {
            "summary": summary,
            "crime_vector": crime_vector,
            "financial_impact": key_actors["disputed_amount"],
            "key_actors": key_actors,
        }
    }


def _detect_crime_vector(text, ents):
    """Identifies the operational vector/modus operandi from unstructured text."""
    if re.search(r"\b(?:qr|scan|scanner)\b", text):
        return "UPI QR Code Phishing / Reverse QR Scam"
    elif re.search(r"\b(?:refund|cashback|reward)\b", text) and re.search(r"\b(?:link|click|app|upi)\b", text):
        return "Fake Refund / Cashback Link Phishing"
    elif re.search(r"\b(?:aeps|fingerprint|thumb|biometric)\b", text):
        return "AePS (Aadhaar Enabled Payment System) Biometric Cloning"
    elif re.search(r"\b(?:kyc|sim block|sim swap|esim)\b", text):
        return "Fake KYC Update / SIM Swap Impersonation"
    elif re.search(r"\b(?:digital arrest|cbi|police|customs|fedex|ed\b|narcotics)\b", text):
        return "Digital Arrest / Law Enforcement Impersonation"
    elif re.search(r"\b(?:part time|task|telegram|like youtube|rating|review)\b", text):
        return "Part-Time Task / Telegram Investment Scam"
    elif re.search(r"\b(?:loan app|instant loan|recovery)\b", text):
        return "Illegal Chinese / Instant Loan App Extortion"
    elif re.search(r"\b(?:video call|nude|morphed|blackmail|sextortion)\b", text):
        return "Sextortion / Video Call Honeytrap & Blackmail"
    elif re.search(r"\b(?:otp|phishing link|apk|anydesk|teamviewer|rustdesk|link\b|clicked)\b", text):
        return "Remote Access Trojan / Phishing Link Credential Theft"
    elif re.search(r"\b(?:instagram|fake profile|hacked account)\b", text):
        return "Account Hijacking / Impersonation on Social Media"
    elif re.search(r"\b(?:matrimonial|shaadi|tinder|bumble)\b", text):
        return "Online Matrimonial / Romance Impersonation Fraud"
    return "Cybercrime Incident via Electronic Channel"


def _extract_amount(text):
    m = re.search(r"(?:rs\.?|inr|rupees?|\u20b9)\s*([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE)
    if m:
        return f"Rs. {m.group(1)}"
    m2 = re.search(r"\b([\d,]{4,8})\s*(?:rs|rupees|kat gaye|chale gaye|nikal gaye|debited|lost|paid)\b", text, re.IGNORECASE)
    if m2:
        return f"Rs. {m2.group(1)}"
    return ""


def _detect_platform(text):
    for plat in ["WhatsApp", "Telegram", "Instagram", "PhonePe", "Google Pay", "Paytm", "Facebook", "Snapchat", "Net Banking", "UPI"]:
        if plat.lower() in text.lower():
            return plat
    return ""


def _generate_complaint_summary(raw_text, ents, crime_vector, has_amount):
    """Produces a concise 2-sentence executive summary of the incident."""
    amt = ents.get("amount") or _extract_amount(raw_text) or "an unspecified sum"
    plat = ents.get("platform") or _detect_platform(raw_text) or "digital platforms"
    
    clean_text = raw_text.strip().replace("\n", " ")
    snippet = clean_text[:140] + ("..." if len(clean_text) > 140 else "")

    if has_amount:
        return f"Complainant reported unauthorized debit/fraudulent transfer of {amt} via {plat} through {crime_vector}. Context: \"{snippet}\""
    else:
        return f"Complainant reported an incident involving {crime_vector} on {plat}. Context: \"{snippet}\""
