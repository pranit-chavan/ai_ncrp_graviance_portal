"""
MODULE H.1 — Modus Operandi (MO) Knowledge Base & Incident Intent Engine

A curated, deterministic repository of Indian cybercrime attack patterns aligned
with the NCRP / I4C framework. Provides instant MO matching from unstructured
victim speech/text, identifies missing critical investigation fields, and generates
tailored victim and investigator advisory guidance.

USAGE:
    from modules.mo_knowledge_base import match_mo, get_mo_by_id, get_victim_guidance

    match = match_mo("mere whatsapp pe bijli bill cut hone ka message aaya tha")
    print(match["mo_id"], match["name"], match["score"])

    guidance = get_victim_guidance(match["mo_id"])
"""

import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON_PATH = os.path.join(_HERE, "mo_knowledge_base.json")

_CACHE: Optional[Dict[str, Any]] = None


def load_knowledge_base() -> Dict[str, Any]:
    """Load and cache the MO knowledge base JSON."""
    global _CACHE
    if _CACHE is None:
        if not os.path.exists(_JSON_PATH):
            raise FileNotFoundError(f"MO knowledge base file not found at {_JSON_PATH}")
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            _CACHE = json.load(f)
    return _CACHE


def list_all_mos() -> List[Dict[str, str]]:
    """Return a list of all registered MO patterns with ID and name."""
    kb = load_knowledge_base()
    return [{"mo_id": p["mo_id"], "name": p["name"], "category": p["category"]} for p in kb.get("patterns", [])]


def get_mo_by_id(mo_id: str) -> Optional[Dict[str, Any]]:
    """Fetch an MO entry by its identifier (e.g. 'MO-FIN-001')."""
    kb = load_knowledge_base()
    for pattern in kb.get("patterns", []):
        if pattern["mo_id"].upper() == mo_id.strip().upper():
            return pattern
    return None


def match_mo(
    text: str,
    entities: Optional[Dict[str, Any]] = None,
    threshold: float = 0.15
) -> Optional[Dict[str, Any]]:
    """
    Match unstructured text and extracted entities to the most probable MO pattern.

    Returns the best matching pattern dictionary augmented with:
      - 'match_score': normalized score between 0.0 and 1.0
      - 'matched_keywords': list of matched phrases/terms
      - 'matched_aliases': list of matched aliases
    Returns None if no pattern satisfies the threshold.
    """
    ranked = rank_mos(text, entities=entities, limit=1)
    if ranked and ranked[0]["match_score"] >= threshold:
        return ranked[0]
    return None


def rank_mos(
    text: str,
    entities: Optional[Dict[str, Any]] = None,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Rank all MO patterns for the given text and entities."""
    if not text and not entities:
        return []

    kb = load_knowledge_base()
    text_lower = (text or "").lower()
    entities = entities or {}

    # Extract extra context terms from entities
    entity_str = " ".join(str(v).lower() for v in entities.values() if v)
    combined_search_space = f"{text_lower} {entity_str}"

    scored_patterns = []

    for pattern in kb.get("patterns", []):
        score = 0.0
        matched_kw = []
        matched_al = []

        # 1. Alias matching (High weight: +3.0 per hit)
        for alias in pattern.get("aliases", []):
            al_lower = alias.lower()
            if al_lower in text_lower:
                score += 3.0
                matched_al.append(alias)
            elif al_lower in combined_search_space:
                score += 1.5
                matched_al.append(alias)

        # 2. Keyword regex matching (Medium weight: +1.5 per hit)
        for kw in pattern.get("keywords", []):
            pattern_regex = r"\b" + re.escape(kw.lower()) + r"\b"
            if re.search(pattern_regex, text_lower):
                score += 1.5
                matched_kw.append(kw)
            elif kw.lower() in combined_search_space:
                score += 0.8
                matched_kw.append(kw)

        # 3. Platform affinity (+1.0 if mentioned platform matches MO platforms)
        platform_hint = entities.get("platform") or entities.get("app_name") or ""
        for plat in pattern.get("common_platforms", []):
            plat_lower = plat.lower()
            if plat_lower in text_lower or (platform_hint and plat_lower in str(platform_hint).lower()):
                score += 1.0
                break

        # 4. Attack chain phrase overlap (+0.5 per distinct step keyword)
        for step in pattern.get("attack_chain", []):
            step_words = [w for w in re.findall(r"\w+", step.lower()) if len(w) > 4]
            overlap = sum(1 for w in step_words if w in text_lower)
            if overlap >= 2:
                score += 0.5

        if score > 0:
            # Normalize score against a realistic maximum (e.g. 10.0 cap)
            norm_score = round(min(1.0, score / 6.0), 3)
            result = dict(pattern)
            result["match_score"] = norm_score
            result["raw_score"] = round(score, 2)
            result["matched_keywords"] = matched_kw
            result["matched_aliases"] = matched_al
            scored_patterns.append(result)

    scored_patterns.sort(key=lambda x: (x["match_score"], x["raw_score"]), reverse=True)
    return scored_patterns[:limit]


def get_critical_fields(mo_id: str) -> List[str]:
    """Retrieve the list of critical investigation fields required for a specific MO."""
    mo = get_mo_by_id(mo_id)
    if not mo:
        return ["amount", "date", "utr", "suspect_contact"]
    return mo.get("critical_for_investigation", [])


def get_victim_guidance(mo_id: str) -> Dict[str, Any]:
    """Retrieve actionable citizen guidance and preservation advisory for an MO."""
    mo = get_mo_by_id(mo_id)
    if not mo:
        return {
            "immediate_actions": ["Call 1930 Cyber Crime Helpline immediately"],
            "evidence_to_preserve": ["Transaction receipts", "Call and chat logs"],
            "helpline_contacts": ["1930"]
        }
    return mo.get("victim_guidance", {})


def get_investigation_hints(mo_id: str) -> Dict[str, Any]:
    """Retrieve tactical investigative instructions and legal charge hints for an IO."""
    mo = get_mo_by_id(mo_id)
    if not mo:
        return {
            "preliminary_action": "Verify transaction trail and issue Section 91 BNSS freeze notice",
            "notices_required": ["Section 91 BNSS to Bank"],
            "mule_pattern": "Standard mule account rotation",
            "statutory_provisions": ["BNS 318(4)", "IT Act 66D"]
        }
    return mo.get("investigation_hints", {})


# ---------------------------------------------------------------------------
# Self-Check & Testing CLI
# ---------------------------------------------------------------------------

def _run_self_test() -> bool:
    """Run automated verification across all 14 MO patterns."""
    kb = load_knowledge_base()
    patterns = kb.get("patterns", [])
    print(f"[MO-KB] Loaded {len(patterns)} patterns from knowledge base.")
    assert len(patterns) == 14, f"Expected 14 patterns, got {len(patterns)}"

    test_cases = [
        ("Mere account se 45000 cut ho gaye bijli bill ke naam pe WhatsApp pe message aaya tha", "MO-FIN-001"),
        ("OLX pe sofa bech raha tha buyer ne bola scan qr code to receive advance and paise cut gaye", "MO-FIN-002"),
        ("Telegram pe task diya tha youtube video like karne ka baad me prepaid task me 80000 phas gaye", "MO-FIN-003"),
        ("Instant loan app download kiya tha ab wo contacts ko morphed nude photos bhej rahe hain", "MO-FIN-004"),
        ("CBI officer banke Skype video call pe digital arrest karke verification account me 5 lakh transfer karwaye", "MO-FIN-005"),
        ("WhatsApp group me VIP stock tips ke naam pe fake trading app download karwayi aur withdrawal freeze kiya", "MO-FIN-006"),
        ("Unknown number se WhatsApp video call aayi aur face record karke nude video viral karne ki dhamki di", "MO-SOC-007"),
        ("SBI yono kyc update ke liye SMS aaya link pe click kiya aur pura account khali ho gaya", "MO-FIN-008"),
        ("FedEx parcel customs airport pe pakda gaya drugs ke naam pe clearance fee mang rahe hain", "MO-FIN-009"),
        ("AnyDesk download karwaya customer care support ke naam pe 9 digit code diya aur debit ho gaya", "MO-FIN-010"),
        ("Aadhaar AePS se biometric fingerprint clone karke CSP se daily 10000 nikal liye", "MO-FIN-011"),
        ("Mera fake Instagram profile banakar mere friends se emergency medical help ke paise maange", "MO-SOC-012"),
        ("Fake Flipkart sale me iPhone pe 90% discount dekhkar prepaid order kiya product nahi aaya", "MO-FIN-013"),
        ("Shaadi.com pe NRI doctor se baat hui usne bola gift customs clearance ke liye duty transfer karo", "MO-SOC-014"),
    ]

    passed = 0
    for text, expected_id in test_cases:
        match = match_mo(text)
        if match and match["mo_id"] == expected_id:
            passed += 1
            print(f"  [PASS] '{expected_id}': {match['name'][:40]}... (Score: {match['match_score']})")
        else:
            got_id = match["mo_id"] if match else "None"
            print(f"  [FAIL] Expected {expected_id}, got {got_id} for: '{text[:50]}...'")

    print(f"\n[MO-KB Self-Test] {passed}/{len(test_cases)} tests passed.")
    return passed == len(test_cases)


if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        success = _run_self_test()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        query = " ".join(sys.argv[1:])
        res = rank_mos(query, limit=3)
        print(f"Query: {query}\n")
        for i, m in enumerate(res, 1):
            print(f"{i}. [{m['mo_id']}] {m['name']} (Confidence: {m['match_score']*100:.1f}%)")
            print(f"   Category: {m['category']} | Primary NCRP: {m['primary_ncrp_subcategory']}")
            print(f"   Critical Fields: {', '.join(m['critical_for_investigation'])}")
            print(f"   Immediate Action: {m['victim_guidance']['immediate_actions'][0]}")
            print()
    else:
        _run_self_test()
