"""Reproducible evaluation of executable models on dataset/splits_para.

This script evaluates only models with trainable implementations in the
repository benchmark. It intentionally does not import the benchmark script,
which contains a hard-coded DistilBERT reference row and deployment claims.
"""

import csv
import hashlib
import glob
import json
import os
import platform
import sys
from datetime import datetime, timezone

import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.naive_bayes import ComplementNB
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLIT_DIR = os.path.join(ROOT, "dataset", "splits_para")
OUT_DIR = os.path.join(ROOT, "reports", "s3_evaluation")
SPLITS = ("train", "val", "test")


def load_split(name):
    records = []
    for path in sorted(glob.glob(os.path.join(SPLIT_DIR, name, "*.jsonl"))):
        with open(path, encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    if not records:
        raise RuntimeError(f"No records found for split {name}")
    return records


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = {name: load_split(name) for name in SPLITS}
    train, test = data["train"], data["test"]
    encoder = LabelEncoder().fit([r["sub_category"] for r in train])
    labels = list(encoder.classes_)
    y_train = encoder.transform([r["sub_category"] for r in train])
    y_test = encoder.transform([r["sub_category"] for r in test])
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), max_features=50000, sublinear_tf=True, min_df=2
    )
    X_train = vectorizer.fit_transform([r["complaint_text"] for r in train])
    X_test = vectorizer.transform([r["complaint_text"] for r in test])

    models = {
        "LinearSVC": LinearSVC(C=1.0, max_iter=10000, random_state=42),
        "Logistic Regression (L2)": LogisticRegression(
            C=10.0, max_iter=1000, random_state=42
        ),
        "Complement Naive Bayes": ComplementNB(alpha=0.5),
    }
    result = {
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "scikit_learn": sklearn.__version__,
            "vectorizer": {
                "ngram_range": [1, 2], "max_features": 50000,
                "sublinear_tf": True, "min_df": 2,
            },
            "seed": {"split": 20260825, "LinearSVC": 42,
                     "Logistic Regression (L2)": 42,
                     "Complement Naive Bayes": "not applicable"},
            "counts": {name: len(rows) for name, rows in data.items()},
            "classes": labels,
            "vocabulary_size": len(vectorizer.vocabulary_),
        },
        "models": {},
        "linear_svc": {},
    }
    predictions_by_model = {}
    for name, model in models.items():
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        predictions_by_model[name] = predictions
        report = classification_report(
            y_test, predictions, labels=range(len(labels)), target_names=labels,
            output_dict=True, zero_division=0,
        )
        result["models"][name] = {
            "accuracy": float(accuracy_score(y_test, predictions)),
            "macro_f1": float(f1_score(y_test, predictions, average="macro")),
            "per_class": {
                label: {
                    "precision": float(report[label]["precision"]),
                    "recall": float(report[label]["recall"]),
                    "f1": float(report[label]["f1-score"]),
                    "support": int(report[label]["support"]),
                }
                for label in labels
            },
        }

    svc_predictions = predictions_by_model["LinearSVC"]
    result["linear_svc"]["confusion_matrix"] = confusion_matrix(
        y_test, svc_predictions, labels=range(len(labels))
    ).tolist()
    errors = []
    prediction_rows = []
    for record, truth, pred in zip(test, y_test, svc_predictions):
        prediction_rows.append({
            "id": record.get("id"),
            "true_label": labels[truth],
            "predicted_label": labels[pred],
        })
        if truth != pred:
            errors.append({**record, "true_label": labels[truth],
                           "predicted_label": labels[pred]})
    result["linear_svc"]["misclassified_count"] = len(errors)
    result["linear_svc"]["prediction_count"] = len(prediction_rows)
    result["linear_svc"]["prediction_generated_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    out_json = os.path.join(OUT_DIR, "s3_metrics.json")
    with open(out_json, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "linear_svc_misclassified_records.json"),
              "w", encoding="utf-8") as handle:
        json.dump(errors, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "linear_svc_predictions.json"),
              "w", encoding="utf-8") as handle:
        json.dump(prediction_rows, handle, ensure_ascii=False, indent=2)
    prediction_path = os.path.join(OUT_DIR, "linear_svc_predictions.json")
    with open(prediction_path, "rb") as handle:
        prediction_sha256 = hashlib.sha256(handle.read()).hexdigest()
    with open(os.path.join(OUT_DIR, "linear_svc_predictions_metadata.json"),
              "w", encoding="utf-8") as handle:
        json.dump({
            "generated_at_utc": result["linear_svc"]["prediction_generated_at_utc"],
            "row_count": len(prediction_rows),
            "unique_id_count": len({row["id"] for row in prediction_rows}),
            "sha256": prediction_sha256,
        }, handle, indent=2)
    with open(os.path.join(OUT_DIR, "linear_svc_confusion_matrix.csv"),
              "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true \\ predicted", *labels])
        for label, row in zip(labels, result["linear_svc"]["confusion_matrix"]):
            writer.writerow([label, *row])

    print(json.dumps({
        "counts": result["environment"]["counts"],
        "labels": len(labels),
        "vocabulary_size": result["environment"]["vocabulary_size"],
        "models": {name: {"accuracy": metrics["accuracy"],
                          "macro_f1": metrics["macro_f1"]}
                   for name, metrics in result["models"].items()},
        "LinearSVC_misclassified": len(errors),
        "outputs": OUT_DIR,
    }, indent=2))


if __name__ == "__main__":
    main()
