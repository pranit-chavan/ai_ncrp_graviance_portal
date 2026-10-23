"""
Export the baseline Cybercrime Complaint Classifier to joblib files.
Preserves the exact preprocessing pipeline: TfidfVectorizer(ngram_range=(1, 2)) + LinearSVC(C=1.0).
Saves:
  models/classifier.joblib
  models/vectorizer.joblib
  models/label_encoder.joblib
  models/label_map.json
"""

import os
import glob
import json
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.preprocessing import LabelEncoder

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLITS_DIR = os.path.join(BASE_DIR, "dataset", "splits")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def export_model():
    print("[EXPORT] Loading training split from dataset/splits/train/*.jsonl...")
    texts, labels = [], []
    train_pattern = os.path.join(SPLITS_DIR, "train", "*.jsonl")
    for path in sorted(glob.glob(train_pattern)):
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                texts.append(r["complaint_text"])
                labels.append(r["sub_category"])

    if not texts:
        raise RuntimeError("No training data found in " + train_pattern)

    print(f"[EXPORT] Loaded {len(texts)} training samples across {len(set(labels))} classes.")

    le = LabelEncoder().fit(labels)
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=50000,
        sublinear_tf=True,
        min_df=2
    )
    
    print("[EXPORT] Fitting TF-IDF Vectorizer...")
    X_train = vec.fit_transform(texts)
    
    print("[EXPORT] Training LinearSVC(C=1.0)...")
    clf = LinearSVC(C=1.0, max_iter=10000)
    clf.fit(X_train, le.transform(labels))

    clf_path = os.path.join(MODELS_DIR, "classifier.joblib")
    vec_path = os.path.join(MODELS_DIR, "vectorizer.joblib")
    le_path = os.path.join(MODELS_DIR, "label_encoder.joblib")
    map_path = os.path.join(MODELS_DIR, "label_map.json")

    print(f"[EXPORT] Saving artifacts to {MODELS_DIR}...")
    joblib.dump(clf, clf_path)
    joblib.dump(vec, vec_path)
    joblib.dump(le, le_path)

    label_map = {label: int(idx) for idx, label in enumerate(le.classes_)}
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(label_map, f, indent=2)

    print("✓ Successfully exported all model artifacts:")
    print("  -", clf_path)
    print("  -", vec_path)
    print("  -", le_path)
    print("  -", map_path)

if __name__ == "__main__":
    export_model()
