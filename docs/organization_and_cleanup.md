# Organization and cleanup review

Reviewed 20 November 2026. No files were deleted. All 32 moves were verified by SHA-256 before reference edits. Application entry points, runtime data, and report build layouts were preserved. The outer workspace folder remains unchanged.

## Usually safe to delete later

- `__pycache__/` and `*.pyc`: regenerated Python bytecode; close running processes first.
- `.pytest_cache/`: regenerated test history.
- Root `streamlit*.log`: diagnostic logs, if no longer needed; stop the corresponding server first.
- `tmp/pdfs/`: two cover previews and two extracted text files; check for annotations before removing.

## Review before deleting

- `scratch/`: experiments, regenerated evaluation data, and guide templates; may contain unique work.
- `reports/*.zip`: packaged exports; verify editable folders contain everything before removing an archive.
- `output/pdf/Final_Year_Project_Report.pdf` and generated report PDFs: rebuildable, but may be useful submission copies. Verify a fresh build first.
- `reports/reference_documents/`: reference materials, not application dependencies. The purpose of `unidentified_reference_report.pdf` (formerly `new (1).pdf`) has not been established.
- Alternative diagrams: exact duplicate groups are listed below.
- `images.zip`, `ocr_test_images/`, and `test_evidence_upi_receipt.png`: inspect privately; retain anything needed for testing or demonstrations.
- `.claude/` and `.freebuff/`: local configuration, optional only if those tools are no longer used.

## Keep

Keep application code, `static/`, `requirements.txt`, `tests/`, `.env`, `.streamlit/`, `models/`, mapping JSON in `modules/`, and `dataset/` for reproducible training. Keep report sources, bibliography, build scripts, and referenced figures. Keep `.git/`, `.githooks/`, `.gitignore`, `.gitattributes`, and `AGENTS.md`.

`complaints.db`, `case_index.db`, `case_files/`, `uploads/`, and `investigator_inbox/` are stored records or evidence, not junk. Deleting them would lose data. Historical report snapshots may mention former filenames.

## Exact duplicate assets

Verified by SHA-256. Report-local copies may be required by relative image references; update and rebuild the report before considering their removal.

- `docs/diagrams/algorithm_flowchart.png`; `reports/final_year_project_report/images/algorithm_flowchart.png`
- `docs/diagrams/architecture.png`; `docs/diagrams/architecture_alternate.png`; `docs/diagrams/system_architecture.png`; `docs/diagrams/system_architecture_diagram.png`; `reports/overleaf_report_starter/system_architecture.png`; `reports/overleaf_report_starter/system_architecture_diagram.png`; `reports/final_year_project_report/images/architecture.png`; `reports/final_year_project_report/images/architrcture.png`; `reports/final_year_project_report/images/fig_6_1_system_architecture.png`; `reports/final_year_project_report/images/system_architecture.png`; `reports/final_year_project_report/images/system_architecture_diagram.png`
- `docs/diagrams/architecture_portrait.png`; `reports/overleaf_report_starter/Architecture_Portrait.png`
- `docs/diagrams/database_schema.jpg`; `reports/final_year_project_report/images/database_schema.jpg`
- `docs/diagrams/system_architecture_landscape.png`; `reports/overleaf_report_starter/architecture.png`; `reports/overleaf_report_starter/architrcture.png`
- `docs/diagrams/system_architecture_square.png`; `docs/diagrams/system_architecture_square_bw.png`; `reports/final_year_project_report/images/fig_6_1_system_architecture_square.png`
- `docs/diagrams/usecase_diagram.jpg`; `reports/final_year_project_report/images/usecase_diagram.jpg`
- `reports/kkwagh_logo.png`; `reports/final_year_project_report/kkwagh_logo.png`; `reports/overleaf_project/kkwagh_logo.png`

## Moves and renames

| Previous path | New path |
| --- | --- |
| `README.md` | `docs/baseline_training.md` |
| `README2.md` | `docs/application_guide.md` |
| `modules/README1.md` | `modules/README.md` |
| `PARAPHRASE_GUIDE.md` | `docs/paraphrase_guide.md` |
| `PROJECT_OVERVIEW.md` | `docs/project_overview.md` |
| `RUN_RECORD.md` | `docs/evaluation_run_record.md` |
| `TESTING_SCENARIO_UPI_FRAUD.md` | `docs/testing_upi_fraud.md` |
| `docs/NCRP_SYSTEM_ARCHITECTURE_V2.md` | `docs/system_architecture_v2.md` |
| `Research Seminar Report PID 18.pdf` | `reports/reference_documents/research_seminar_report_pid_18.pdf` |
| `new (1).pdf` | `reports/reference_documents/unidentified_reference_report.pdf` |
| `architecture.mmd` | `docs/diagrams/architecture.mmd` |
| `export_architecture.html` | `docs/diagrams/export_architecture.html` |
| `train_baseline.py` | `scripts/training/train_baseline.py` |
| `train_baseline_template.py` | `scripts/training/train_baseline_template.py` |
| `train_baseline_para.py` | `scripts/training/train_baseline_para.py` |
| `paraphrase.py` | `scripts/data_preparation/paraphrase.py` |
| `make_para_split.py` | `scripts/data_preparation/make_para_split.py` |
| `make_template_split.py` | `scripts/data_preparation/make_template_split.py` |
| `algorithm_flowchart.png` | `docs/diagrams/algorithm_flowchart.png` |
| `architecture.png` | `docs/diagrams/architecture.png` |
| `Architecture_Portrait.png` | `docs/diagrams/architecture_portrait.png` |
| `architrcture.png` | `docs/diagrams/architecture_alternate.png` |
| `database_schema.jpg` | `docs/diagrams/database_schema.jpg` |
| `system_architecture.png` | `docs/diagrams/system_architecture.png` |
| `system_architecture_compact.png` | `docs/diagrams/system_architecture_compact.png` |
| `system_architecture_diagram.png` | `docs/diagrams/system_architecture_diagram.png` |
| `system_architecture_landscape.png` | `docs/diagrams/system_architecture_landscape.png` |
| `system_architecture_square.png` | `docs/diagrams/system_architecture_square.png` |
| `system_architecture_square_bw.png` | `docs/diagrams/system_architecture_square_bw.png` |
| `usecase_diagram.jpg` | `docs/diagrams/usecase_diagram.jpg` |
| `../extracted_page39_architecture.png` | `docs/diagrams/extracted/extracted_page39_architecture.png` |
| `../extracted_phase1_fig3_1.png` | `docs/diagrams/extracted/extracted_phase1_fig3_1.png` |
