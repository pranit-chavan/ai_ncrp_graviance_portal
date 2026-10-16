# Cybercrime Complaint Classification System

An NCRP-modelled system that takes a citizen complaint in any language, classifies
it into an NCRP sub-category, maps it to Indian law, and produces an
investigator-ready case file.

## Folder structure

```
classifier_project/
├── pipeline.py                  run a complaint end to end (A -> B -> D -> E)
│
├── modules/
│   ├── ai_assistant.py          MODULE A  messy input -> standardised narrative
│   ├── legal_mapping.py         MODULE D  sub-category -> IT Act / BNS sections
│   ├── legal_mapping.json       MODULE D  the mapping data, 21 sub-categories
│   ├── case_file.py             MODULE E  case file as JSON + PDF
│   └── README.md                per-module documentation
│
├── train_baseline.py            MODULE B  baseline on random splits
├── train_baseline_template.py   MODULE B  baseline on template-disjoint splits
├── train_baseline_para.py       MODULE B  baseline on paraphrased splits (honest)
│
├── paraphrase.py                dataset  LLM paraphrasing, 3 providers
├── make_template_split.py       dataset  template-disjoint splits
├── make_para_split.py           dataset  splits from paraphrased data
│
├── case_files/                  generated case files (JSON + PDF)
├── models/                      label_map.json
└── dataset/
    ├── generated/               master copies, 500 per sub-category, NEVER train on
    ├── generators/              vocab / templates / config per sub-category
    ├── splits/                  random splits
    ├── splits_template/         template-disjoint splits
    ├── paraphrased/             created by paraphrase.py  (on your machine)
    └── splits_para/             created by make_para_split.py  (on your machine)
```

Note: `dataset/paraphrased/` and `dataset/splits_para/` are generated on your
machine and are not shipped in this archive. Do not overwrite them.

## Module status

| Module | What it does | Status |
|--------|--------------|--------|
| A  AI Assistant   | messy multilingual input -> standardised English narrative | built |
| B  Classifier     | narrative -> NCRP sub-category, 21 classes | built, macro-F1 0.9970 |
| C  OCR            | screenshots -> entities | NOT BUILT |
| D  Legal Mapping  | sub-category -> IT Act / BNS / POCSO | built, 21/21 |
| E  Case File      | assemble everything -> JSON + PDF | built |
| F  Dashboard      | investigator UI | NOT BUILT |

## Quick start

    pip install scikit-learn reportlab requests

    python modules/legal_mapping.py              Module D self-test
    python modules/ai_assistant.py --check       Module A guard self-test
    python modules/case_file.py                  Module E, builds 3 demo case files
    python pipeline.py --demo                    end to end (needs Ollama running)

    python train_baseline_template.py            classifier, template-disjoint
    python train_baseline_para.py                classifier, paraphrased (honest)

Module A needs Ollama with qwen2.5:7b:

    ollama pull qwen2.5:7b

## Results

Classifier, template-disjoint AND paraphrase-family-disjoint splits:

    macro-F1  0.9970      6 errors / 1960

All 6 errors fall on semantically adjacent pairs (phishing <-> BEC,
internet banking <-> phishing, profile hacking <-> email hacking), which
indicates residual confusion tracks real taxonomic overlap rather than
generation artifacts.

Accuracy by writing style:

    original   100.0%    generator wording
    plain      100.0%    natural rewrite
    detailed    96.9%    natural rewrite
    terse       96.8%    natural rewrite

Model selection finding: on the paraphrase task Llama 3.1 8B rejected 71% of
outputs on fact-preservation checks; Qwen 2.5 7B rejected 2.3% with an identical
prompt. Selection was made on measured fact fidelity, not parameter count.

## Open items

- Legal section numbers came from the source news articles for each sub-category.
  The descriptions and IPC equivalents need verification against indiacode.nic.in
  before they go in the report.
- Two taxonomy duplicates unresolved: BEC (Financial 02 vs Social 05) and
  Vishing (Financial 06 vs Social 01).
- Module A is untested on Devanagari script. The guard compares numerals between
  input and output and will need numeral normalisation for non-Latin digits.
- Gold set of hand-written complaints not yet collected.
