# Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP

Local complaint intake, classification, evidence review, and investigator workflows.

## Start

Run from this directory (`classifier_project/`):

```powershell
pip install -r requirements.txt
python -m uvicorn server:app --host 127.0.0.1 --port 8501
```

Streamlit interface: `streamlit run dashboard.py --server.port 8502`.
Local configuration stays in `.env` and `.streamlit/`.

## Layout

| Location | Purpose |
| --- | --- |
| `server.py`, `dashboard.py`, `pipeline.py` | Application entry points |
| `modules/` | Services and mapping data |
| `static/` | Browser interface and assets |
| `scripts/training/` | Baseline model training |
| `scripts/data_preparation/` | Dataset splitting and paraphrasing |
| `scripts/` | Model export, benchmarking, evaluation |
| `tests/` | Automated tests |
| `docs/` | Project guides and run records |
| `docs/diagrams/` | Standalone figures, Mermaid source, export page |
| `models/` | Trained artifacts and labels required for inference |
| `dataset/` | Local datasets and generators |
| `reports/` | Report sources, figures, evaluation results, Overleaf projects |
| `reports/reference_documents/` | Reference PDFs |
| `output/pdf/` | Generated final report |
| `case_files/`, `uploads/`, `investigator_inbox/` | Local records and evidence |
| `scratch/`, `tmp/` | Experiments and temporary previews |

Databases stay at the root because the application uses those paths. Report projects retain their image copies for portable builds.

## Guides

- [Application guide](docs/application_guide.md)
- [Project overview](docs/project_overview.md)
- [Baseline training](docs/baseline_training.md)
- [Paraphrasing](docs/paraphrase_guide.md)
- [Architecture](docs/system_architecture_v2.md)
- [Evaluation run record](docs/evaluation_run_record.md)
- [UPI fraud testing](docs/testing_upi_fraud.md)
- [Module documentation](modules/README.md)
- [Offline setup and model notes](docs/offline_setup.md)
- [Organization inventory and cleanup candidates](docs/organization_and_cleanup.md)

## Development

Run scripts from the project root; dataset and model paths remain relative to it.

```powershell
python scripts/training/train_baseline.py
python scripts/training/train_baseline_template.py
python scripts/training/train_baseline_para.py
python scripts/data_preparation/paraphrase.py --help
python -m unittest discover -s tests
```

Training and preparation commands write model metadata or datasets. Use them only when intending to regenerate those artifacts.
