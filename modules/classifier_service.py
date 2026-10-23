"""
MODULE — Scikit-Learn Classifier Service
Loads the pre-trained TF-IDF Vectorizer and LinearSVC model saved as .joblib files.
Executes deterministic prediction with decision margin confidence scoring.
No retraining, original preprocessing pipeline preserved.
"""

import os
import joblib
import numpy as np
from typing import Dict, Any, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

CLF_PATH = os.path.join(MODELS_DIR, "classifier.joblib")
VEC_PATH = os.path.join(MODELS_DIR, "vectorizer.joblib")
LE_PATH = os.path.join(MODELS_DIR, "label_encoder.joblib")

_LOADED_MODEL = {
    "clf": None,
    "vec": None,
    "le": None
}

def load_model():
    """Load the serialized scikit-learn models from disk."""
    if _LOADED_MODEL["clf"] is not None:
        return True

    if not (os.path.exists(CLF_PATH) and os.path.exists(VEC_PATH) and os.path.exists(LE_PATH)):
        return False

    try:
        _LOADED_MODEL["clf"] = joblib.load(CLF_PATH)
        _LOADED_MODEL["vec"] = joblib.load(VEC_PATH)
        _LOADED_MODEL["le"] = joblib.load(LE_PATH)
        return True
    except Exception as e:
        print(f"[CLASSIFIER] Failed to load joblib models: {e}")
        return False

def classify_complaint_text(complaint_text: str) -> Dict[str, Any]:
    """
    Run raw confirmed complaint narrative through the scikit-learn preprocessing pipeline.
    
    Returns structured result:
      {
        "predicted_category": "UPI Related Frauds",
        "confidence": 0.94,
        "decision_margin": 2.18,
        "runner_up": "Internet Banking Related Fraud",
        "runner_up_margin": 0.42,
        "top_alternatives": [
           {"category": "...", "margin": 2.18},
           {"category": "...", "margin": 0.42}
        ],
        "caveat": "LinearSVC decision margin confidence. Decision support only, not a legal ruling."
      }
    """
    if not load_model():
        raise RuntimeError("Classifier models not found in models/ directory. Run scripts/export_classifier.py first.")

    clf = _LOADED_MODEL["clf"]
    vec = _LOADED_MODEL["vec"]
    le = _LOADED_MODEL["le"]

    # Original preprocessing pipeline: TF-IDF vectorization
    X = vec.transform([complaint_text])
    margins = clf.decision_function(X)[0]

    # Rank classes by margin
    sorted_indices = np.argsort(margins)[::-1]
    top_idx = int(sorted_indices[0])
    runner_up_idx = int(sorted_indices[1]) if len(sorted_indices) > 1 else top_idx

    top_label = str(le.inverse_transform([top_idx])[0])
    runner_up_label = str(le.inverse_transform([runner_up_idx])[0])

    top_margin = float(margins[top_idx])
    runner_up_margin = float(margins[runner_up_idx])

    # Margin gap to 0.0 - 1.0 confidence mapping
    margin_gap = top_margin - runner_up_margin
    # Sigmoidal/linear bounded confidence mapping
    confidence = float(min(0.99, max(0.50, 0.50 + (margin_gap / 4.0))))

    top_3 = []
    for idx in sorted_indices[:3]:
        top_3.append({
            "category": str(le.inverse_transform([idx])[0]),
            "margin": round(float(margins[idx]), 3)
        })

    return {
        "predicted_category": top_label,
        "confidence": round(confidence, 2),
        "decision_margin": round(top_margin, 3),
        "runner_up": runner_up_label,
        "runner_up_margin": round(runner_up_margin, 3),
        "top_alternatives": top_3,
        "caveat": "Automated ML prediction based on TF-IDF + LinearSVC margin analysis. For intake decision support only."
    }

if __name__ == "__main__":
    # Self-test
    test_text = "I received a phone call claiming to be electricity department threatening disconnection. I transferred 65000 from PNB account without OTP."
    res = classify_complaint_text(test_text)
    print("Self-test result:")
    print(res)
