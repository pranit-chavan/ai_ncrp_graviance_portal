"""
TF-IDF + LinearSVC baseline for cybercrime complaint classification.

Run from the classifier_project/ folder:
    python train_baseline.py

Requires: pip install scikit-learn
"""

import glob, json, os
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, f1_score

SPLITS_DIR = os.path.join("dataset", "splits_para")

# ── 1. Load data ──────────────────────────────────────────────
# Only complaint_text reaches the model. id / scenario / template_id are kept
# separately as metadata for error analysis and are NEVER used as features.

def load_split(split):
    texts, labels, meta = [], [], []
    pattern = os.path.join(SPLITS_DIR, split, "*.jsonl")
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"No .jsonl files found in {os.path.join(SPLITS_DIR, split)}")
    for path in files:
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            texts.append(r["complaint_text"])
            labels.append(r["sub_category"])
            meta.append({
                "id":          r.get("id"),
                "scenario":    r.get("scenario"),
                "template_id": r.get("template_id"),
                "category":    r.get("category"),
                "style":       r.get("style", "original"),
            })
    return texts, labels, meta

X_train, y_train, meta_train = load_split("train")
X_val,   y_val,   meta_val   = load_split("val")
X_test,  y_test,  meta_test  = load_split("test")

print("=" * 70)
print("DATA")
print("=" * 70)
print(f"train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")
print(f"classes={len(set(y_train))}\n")

for cat, n in sorted(Counter(m["category"] for m in meta_train).items()):
    print(f"  {n:5}  {cat}")
print()

# ── 2. Encode labels (fit on train only) ──────────────────────

le = LabelEncoder()
le.fit(y_train)
y_train_enc = le.transform(y_train)
y_val_enc   = le.transform(y_val)
y_test_enc  = le.transform(y_test)

os.makedirs("models", exist_ok=True)
json.dump({l: int(i) for i, l in enumerate(le.classes_)},
          open(os.path.join("models", "label_map.json"), "w"), indent=2)

# ── 3. Vectorize ──────────────────────────────────────────────

vectorizer = TfidfVectorizer(
    ngram_range=(1, 2),   # unigrams + bigrams
    max_features=50000,   # room for 21+ classes
    sublinear_tf=True,    # log-scale term frequency
    min_df=2,             # drop terms appearing in a single document
)

X_train_vec = vectorizer.fit_transform(X_train)   # fit on TRAIN only
X_val_vec   = vectorizer.transform(X_val)
X_test_vec  = vectorizer.transform(X_test)

print(f"vocabulary={len(vectorizer.vocabulary_)}  matrix={X_train_vec.shape}\n")

# ── 4. Train ──────────────────────────────────────────────────

model = LinearSVC(C=1.0, max_iter=10000)
model.fit(X_train_vec, y_train_enc)
print("Training complete.\n")

# ── 5. Validation ─────────────────────────────────────────────

val_preds = model.predict(X_val_vec)
print("=" * 70)
print("VALIDATION")
print("=" * 70)
print(classification_report(y_val_enc, val_preds,
                            target_names=le.classes_, zero_division=0))

# ── 6. Test ───────────────────────────────────────────────────

test_preds = model.predict(X_test_vec)
print("=" * 70)
print("TEST")
print("=" * 70)
print(classification_report(y_test_enc, test_preds,
                            target_names=le.classes_, zero_division=0))

# ── 7. Confusion pairs — which classes get mixed up? ──────────

print("=" * 70)
print("CONFUSION PAIRS  (true -> predicted)")
print("=" * 70)

confusions = Counter()
for true, pred in zip(y_test_enc, test_preds):
    if true != pred:
        confusions[(le.classes_[true], le.classes_[pred])] += 1

if not confusions:
    print("  No misclassifications on the test set.")
else:
    for (true, pred), n in confusions.most_common(25):
        print(f"  {n:3}x  {true}")
        print(f"        -> {pred}")

# ── 8. Which scenarios fail most? ─────────────────────────────

print("\n" + "=" * 70)
print("TOP FAILING SCENARIOS")
print("=" * 70)

scen_fail = Counter()
for m, true, pred in zip(meta_test, y_test_enc, test_preds):
    if true != pred:
        scen_fail[(le.classes_[true], m["scenario"])] += 1

if not scen_fail:
    print("  None.")
else:
    for (cls, scen), n in scen_fail.most_common(15):
        print(f"  {n:3}x  {cls}  [{scen}]")

# ── 9. Headline number ────────────────────────────────────────

# accuracy split by writing style - the key diagnostic
print("\n" + "=" * 70)
print("ACCURACY BY WRITING STYLE")
print("=" * 70)
by_style = Counter(); ok_style = Counter()
for m, true, pred in zip(meta_test, y_test_enc, test_preds):
    s = m["style"]; by_style[s] += 1
    if true == pred: ok_style[s] += 1
for s in sorted(by_style):
    n, ok = by_style[s], ok_style[s]
    print(f"  {s:<12} {ok:>5}/{n:<5}  {ok/n:.1%}")
print("\n  'original' = generator wording (easy).")
print("  others     = rewritten in natural language (the real test).")

macro = f1_score(y_test_enc, test_preds, average="macro")
errors = int(sum(confusions.values()))

print("\n" + "=" * 70)
print(f"MACRO-F1 (headline) : {macro:.4f}")
print(f"Test errors         : {errors} / {len(y_test_enc)}")
print("=" * 70)
print("\nNOTE: if run against dataset/splits/ the score is inflated by shared")
print("templates. Against dataset/splits_template/ templates are disjoint,")
print("but vocabulary is still category-exclusive by design.")
