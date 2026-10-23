"""
Build train/val/test splits from the paraphrased data.

TWO RULES, both needed for an honest score:

1. TEMPLATE-DISJOINT - a template belongs to exactly one split, so test
   complaints use sentence structures never seen in training.

2. FAMILY-INTACT - an original and all of its rewrites stay in the SAME split.
   Otherwise the model sees a complaint in training and its reworded twin in
   test, which is leakage wearing a disguise.

Run from the classifier_project folder:
    python make_para_split.py

Reads : dataset/paraphrased/*_para.jsonl
Writes: dataset/splits_para/{train,val,test}/
"""

import glob, json, os, random
from collections import defaultdict, Counter

SEED = 20260825
random.seed(SEED)

SRC = os.path.join("dataset", "paraphrased")
DST = os.path.join("dataset", "splits_para")
VAL_FRAC, TEST_FRAC = 0.15, 0.15


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*_para.jsonl")))
    if not files:
        raise SystemExit(f"No files in {SRC}/ - run paraphrase.py first.")

    for s in ("train", "val", "test"):
        os.makedirs(os.path.join(DST, s), exist_ok=True)

    totals = Counter()
    style_totals = Counter()

    print(f"{'sub-category':<42} {'rows tr/va/te':<20} {'orig/para'}")
    print("-" * 84)

    for path in files:
        base = os.path.basename(path).replace("_para.jsonl", "")
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]

        # group by template so whole templates move together
        by_template = defaultdict(list)
        for r in rows:
            by_template[r["template_id"]].append(r)
            style_totals[r.get("style", "original")] += 1

        templates = sorted(by_template)
        random.shuffle(templates)

        n = len(templates)
        n_test = max(1, round(n * TEST_FRAC))
        n_val = max(1, round(n * VAL_FRAC))

        assign = {}
        for t in templates[:n_test]:
            assign[t] = "test"
        for t in templates[n_test:n_test + n_val]:
            assign[t] = "val"
        for t in templates[n_test + n_val:]:
            assign[t] = "train"

        out = defaultdict(list)
        for t, rs in by_template.items():
            out[assign[t]].extend(rs)      # family stays together automatically:
                                           # a rewrite carries its original's template_id

        for s in ("train", "val", "test"):
            dest = os.path.join(DST, s, f"{base}_{s}.jsonl")
            with open(dest, "w", encoding="utf-8") as f:
                for r in out[s]:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            totals[s] += len(out[s])

        n_orig = sum(1 for r in rows if r.get("style", "original") == "original")
        print(f"{base:<42} {len(out['train']):>4}/{len(out['val']):>4}/{len(out['test']):>4}"
              f"      {n_orig}/{len(rows)-n_orig}")

    print("-" * 84)
    print(f"TOTAL  train={totals['train']}  val={totals['val']}  test={totals['test']}")
    print("\nStyle mix:", dict(style_totals))

    # ---- verification ----
    print("\nVerifying...")
    seen_t = defaultdict(set)
    seen_family = defaultdict(set)
    for s in ("train", "val", "test"):
        for p in glob.glob(os.path.join(DST, s, "*.jsonl")):
            for line in open(p, encoding="utf-8"):
                r = json.loads(line)
                seen_t[(r["sub_category"], r["template_id"])].add(s)
                fam = r.get("paraphrase_of") or r["id"]
                seen_family[(r["sub_category"], fam)].add(s)

    bad_t = {k: v for k, v in seen_t.items() if len(v) > 1}
    bad_f = {k: v for k, v in seen_family.items() if len(v) > 1}
    print(f"  templates in >1 split : {len(bad_t)}  {'OK' if not bad_t else 'FAIL'}")
    print(f"  families  in >1 split : {len(bad_f)}  {'OK' if not bad_f else 'FAIL'}")
    print(f"\nWritten to {DST}/")
    print("Next:  python train_baseline_para.py")


if __name__ == "__main__":
    main()
