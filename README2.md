# Cybercrime Complaint Classification System

An NCRP-modelled prototype that prepares a local cybercrime complaint record from
victim-provided text, voice, and evidence. It classifies the complaint, suggests
legal mappings, and generates a review PDF; it does not submit complaints to NCRP.

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
| A  Intake Assistant | voice/text intake with bounded, one-question follow-ups in the Streamlit flow | built |
| B  Classifier     | narrative -> NCRP sub-category, 21 classes | built, macro-F1 0.9970 |
| C  OCR            | evidence images -> text and entities, victim review, conflict confirmation | built; Tesseract required |
| D  Legal Mapping  | sub-category -> IT Act / BNS / POCSO | lookup built; legal verification remains open |
| E  Case File      | assemble reviewed details -> local JSON + preliminary PDF | built |
| F  Dashboard      | Streamlit citizen intake and investigator views | built; prioritize victim flow |
| Routing           | location -> law enforcement jurisdiction | lookup table not built |

The reported classifier benchmark is from generated evaluation data; it is not
evidence of real-world complaint accuracy.

## Quick start

    pip install -r requirements.txt
    python -m uvicorn server:app --host 127.0.0.1 --port 8501

Open http://localhost:8501 for the citizen-facing HTML/CSS/JavaScript app. The
FastAPI service provides the complaint intake, transcription, classification,
evidence review, PDF, and investigator-workspace endpoints.

The earlier Streamlit dashboard remains available for internal demonstrations:

    streamlit run dashboard.py --server.port 8502

Install Tesseract separately for image OCR. The generated case reference and
PDF are local records, not official NCRP acknowledgements. Legal mappings are
preliminary until verified against current official sources.

For component demos and training:

    python modules/legal_mapping.py              Module D self-test
    python modules/ai_assistant.py --check       Module A guard self-test
    python modules/case_file.py                  Module E, builds 3 demo case files
    python pipeline.py --demo                    end to end (needs Ollama running)

    python train_baseline_template.py            classifier, template-disjoint
    python train_baseline_para.py                classifier, paraphrased (honest)

Module A uses Gemma 4 12B through Ollama by default. Install/run it locally:

    ollama pull gemma4:12b

Conversational intake and complaint narrative standardisation use the Gemini Developer API by default (`gemini-3.5-flash-lite`). Set `GEMINI_API_KEY` and optionally `GEMINI_MODEL`. `INTAKE_LLM_PROVIDER=ollama` selects Ollama for intake; `LLM_PROVIDER=ollama` selects it for narrative standardisation. Keep API keys out of source control. If the configured model/API is unavailable or its response fails validation, intake uses the bounded deterministic fallback. Use fictional complaints for free-tier testing; review the provider's data-use terms before sending real victim information.

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
