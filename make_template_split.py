"""
Template-based re-split of the dataset.

WHY: the original splits were random, so the same template skeletons appear in
train and test. A model can score 100% by memorising template fingerprints
without learning anything about the offences. That number is not reportable.

WHAT THIS DOES: for each sub-category, whole TEMPLATES are assigned to train,
val or test. No template appears in more than one split, so every test complaint
uses a sentence structure the model has never seen.

Run from the classifier_project/ folder:
    python make_template_split.py

Reads : dataset/generated/*_all.jsonl   (the 500-sample master copies)
Writes: dataset/splits_template/{train,val,test}/
The original dataset/splits/ is left untouched.
"""

import glob, json, os, random
from collections import defaultdict, Counter

SEED = 20260825
random.seed(SEED)

SRC = os.path.join("dataset", "generated")
DST = os.path.join("dataset", "splits_template")

# Target proportion of TEMPLATES (not rows) held out.
VAL_FRAC, TEST_FRAC = 0.15, 0.15


def split_one(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]

    by_template = defaultdict(list)
    for r in rows:
        by_template[r["template_id"]].append(r)

    templates = sorted(by_template)          # sort first for determinism
    random.shuffle(templates)

    n = len(templates)
    n_test = max(1, round(n * TEST_FRAC))
    n_val = max(1, round(n * VAL_FRAC))

    test_t = templates[:n_test]
    val_t = templates[n_test:n_test + n_val]
    train_t = templates[n_test + n_val:]

    out = {
        "train": [r for t in train_t for r in by_template[t]],
        "val":   [r for t in val_t   for r in by_template[t]],
        "test":  [r for t in test_t  for r in by_template[t]],
    }
    counts = {k: len(v) for k, v in out.items()}
    tmpl = {"train": len(train_t), "val": len(val_t), "test": len(test_t)}
    return out, counts, tmpl, n


def main():
    for s in ("train", "val", "test"):
        os.makedirs(os.path.join(DST, s), exist_ok=True)

    files = sorted(glob.glob(os.path.join(SRC, "*_all.jsonl")))
    if not files:
        raise SystemExit(f"No master files found in {SRC}")

    totals = Counter()
    print(f"{'sub-category':<40} {'templates (tr/va/te)':<22} {'rows (tr/va/te)'}")
    print("-" * 88)

    for path in files:
        base = os.path.basename(path).replace("_all.jsonl", "")
        out, counts, tmpl, n = split_one(path)

        for s in ("train", "val", "test"):
            dest = os.path.join(DST, s, f"{base}_{s}.jsonl")
            with open(dest, "w", encoding="utf-8") as f:
                for r in out[s]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            totals[s] += counts[s]

        print(f"{base:<40} "
              f"{tmpl['train']:>3}/{tmpl['val']:>2}/{tmpl['test']:>2} of {n:<10} "
              f"{counts['train']:>3}/{counts['val']:>3}/{counts['test']:>3}")

    print("-" * 88)
    print(f"TOTAL  train={totals['train']}  val={totals['val']}  test={totals['test']}")

    # ---- verification: no template may appear in two splits ----
    print("\nVerifying template disjointness...")
    seen = defaultdict(set)
    for s in ("train", "val", "test"):
        for p in glob.glob(os.path.join(DST, s, "*.jsonl")):
            for line in open(p, encoding="utf-8"):
                r = json.loads(line)
                seen[(r["sub_category"], r["template_id"])].add(s)

    leaks = {k: v for k, v in seen.items() if len(v) > 1}
    if leaks:
        print(f"  FAIL: {len(leaks)} templates appear in more than one split")
        for k, v in list(leaks.items())[:5]:
            print(f"    {k} -> {sorted(v)}")
    else:
        print(f"  OK: all {len(seen)} templates are confined to a single split")

    print(f"\nWritten to {DST}/")
    print("Point train_baseline.py at this folder to get an honest score:")
    print('    SPLITS_DIR = os.path.join("dataset", "splits_template")')


if __name__ == "__main__":
    main()
