# Cybercrime Complaint Classifier — Dataset & Baseline

## Folder structure

```
classifier_project/
├── train_baseline.py            <- baseline on RANDOM splits
├── train_baseline_template.py   <- baseline on TEMPLATE-DISJOINT splits (honest)
├── make_template_split.py       <- regenerates splits_template/ (already run)
├── README.md
├── models/                      <- label_map.json written here on run
└── dataset/
    ├── splits/                  random splits  (21 files per split)
    │   ├── train/   7350 rows
    │   ├── val/     1575 rows
    │   └── test/    1575 rows
    ├── splits_template/         template-disjoint splits (21 files per split)
    │   ├── train/   7149 rows
    │   ├── val/     1680 rows
    │   └── test/    1671 rows
    ├── generated/               master copies — NEVER train on these
    └── generators/              vocab / templates / config per sub-category
```

Filenames carry a `MainCat_SubCat` prefix so they sort in taxonomy order:
- `1_xx` Online and Social Media Related Crime (10 sub-categories)
- `2_xx` Online Financial Fraud (6 built; 02 BEC and 06 Vishing parked)
- `3_xx` Hacking / Damage to Computer (5 sub-categories)

## Run

```
pip install scikit-learn

python train_baseline.py            # random splits
python train_baseline_template.py   # template-disjoint splits
```

Both run from this folder. Paths are relative, so open `classifier_project`
directly in VS Code (not its parent).

## The two split sets

`splits/` is random: the same template skeletons appear in train and test.

`splits_template/` assigns WHOLE TEMPLATES to one split only, so every test
complaint uses a sentence structure never seen in training. Verified: all 801
templates are confined to a single split.

## Current result

Both score macro-F1 = 1.0000 with zero errors on 21 classes.

The template-disjoint result rules out template memorisation. The cause is
vocabulary: each category contains words that appear in it and nowhere else
(Job Fraud 333 such words, Internet Banking 13 — the thinnest). TF-IDF needs
only a few to separate 21 classes.

This is a consequence of the leak checks applied during generation, which made
category vocabularies disjoint by construction.

INTERPRETATION — report as two separate findings:
1. Class separability: CONFIRMED. No two categories are duplicates.
2. Real-world accuracy: NOT YET MEASURED. Lexical cues are sufficient, so the
   dataset does not currently test semantic understanding.

Next step: LLM paraphrase pass to replace category-exclusive vocabulary with
natural synonyms, then a hand-written gold test set.

## Important

`dataset/generated/` holds the pre-split master copies. Both loaders are scoped
to their own splits folder and cannot reach them — do not move them into a
splits directory, or test data will leak into training.

Only `complaint_text` is used as a model input. `id`, `scenario`, `template_id`
are loaded as metadata for error analysis and never become features.
