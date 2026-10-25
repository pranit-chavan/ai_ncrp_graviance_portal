# S3 evaluation run record

Run date: 2026-10-26 (local workstation clock).
Project: `classifier_project`; source split `dataset/splits_para/`.

## Split diagnosis and repair

The current paraphrase master contains 12,364 unique rows. The previously saved split contained 12,362 unique rows. Exact ID comparison found only `CBS_0029_de` and `CBS_0029_te` missing, both in `1_02_cyber_bullying_stalking_sexting_para.jsonl`, with `template_id=S01_T4` and `paraphrase_of=CBS_0029`. They are now present in train. All previous IDs remain assigned to the same split. The generator logic grouped by template and wrote each template group; an isolated run of an unchanged copy of the script with only `DST` redirected to scratch produced all 12,364 rows. This indicates the saved split was stale/incomplete relative to the current master, not a demonstrated split-script defect. No split logic was changed.

Only `dataset/splits_para/train/1_02_cyber_bullying_stalking_sexting_train.jsonl` changed. The repository `.gitignore` intentionally excludes the complete `dataset/` tree, so the corrected split and source corpus remain local and are not included in the repository commit. The corrected split contains:

| Split | Rows | Unique IDs |
|---|---:|---:|
| Train | 8,487 | 8,487 |
| Validation | 1,917 | 1,917 |
| Test | 1,960 | 1,960 |
| Total | 12,364 | 12,364 |

## Split-checker results

The checker embedded in the copied `make_para_split.py` was run during scratch regeneration; an independent ID/group check was then run against the corrected saved split. Pairwise group overlap counts:

| Group key | Train–test | Train–validation | Validation–test |
|---|---:|---:|---:|
| `(sub_category, template_id)` | 0 | 0 | 0 |
| `(sub_category, paraphrase_of or id)` | 0 | 0 | 0 |

No duplicate IDs or cross-split IDs were found. All 21 labels occur in train and test.

## Evaluation results

Features were complaint text only. The TF-IDF vectorizer was fitted on train and reused for test: word unigrams and bigrams, `max_features=50000`, `sublinear_tf=True`, `min_df=2`; vocabulary size 35,342. Labels were encoded from the train labels. The same vector matrix was used to fit and evaluate the three implemented models. Full metrics, per-class precision/recall/F1/support for each executable model, and the LinearSVC confusion matrix are in `reports/s3_evaluation/s3_metrics.json`; the CSV export of per-class results is `reports/s3_evaluation/per_class_scores.csv`.

| Model | Accuracy | Macro-F1 |
|---|---:|---:|
| LinearSVC | 0.996938775510 | 0.997001080446 |
| Logistic Regression (L2) | 0.997959183673 | 0.998079420598 |
| Complement Naive Bayes | 0.997448979592 | 0.997525760146 |

LinearSVC misclassified records: 6 of 1,960. Every full misclassified test record with true and predicted label is saved locally in `reports/s3_evaluation/linear_svc_misclassified_records.json`. That row-level artifact remains untracked because it contains complaint text from the locally excluded dataset. Confusion matrix: `reports/s3_evaluation/linear_svc_confusion_matrix.csv` (also embedded in `s3_metrics.json`).

### Model availability

LinearSVC, Logistic Regression (L2), and Complement Naive Bayes were trainable from the checked-in benchmark implementation and were run. The benchmark script’s DistilBERT row is a hard-coded reference dictionary, not a model implementation or train/evaluation path. No DistilBERT training script, weights, tokenizer, or configured model dataset were found in the repository, so it was not reported as a measured model. The existing pre-trained `models/classifier.joblib` was not treated as a separate architecture or retrained result.

## Environment and reproducibility

- Python: `3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]`
- scikit-learn: `1.8.0`
- OS/platform: Windows 11, 64-bit Python/AMD64; exact runtime platform: `Windows-11-10.0.26300-SP0`
- Hardware: HP Victus by HP Gaming Laptop 15-fa1xxx; Intel Core i5-12450H (8 cores, 12 logical processors); 8,212,975,616 bytes installed RAM; NVIDIA GeForce RTX 2050 4,096 MiB, driver 592.82. GPU was not used.
- Seeds: split assignment uses `SEED=20260825` in `make_para_split.py`; LinearSVC `random_state=42`; Logistic Regression `random_state=42`; ComplementNB has no random seed parameter; TF-IDF vectorisation is deterministic.
- Exact installed environment: `pip freeze` output follows.

### Commands and actions

1. `python scratch\make_para_split_repro.py` — temporary copy of the repository `make_para_split.py`, with only the destination constant changed to `scratch/s3_regenerated`; no split algorithm edits. Its built-in template/family checker completed with 0 overlaps.
2. Compare regenerated outputs with saved split outputs by ID and file bytes; copy only files that differed. This changed only the Cyber Bullying / Stalking / Sexting train JSONL and added the two missing records.
3. Independent split integrity check: loaded all JSONL files under `dataset/splits_para/{train,val,test}`, counted rows/unique IDs, and measured pairwise intersections for template and paraphrase-family group keys.
4. `python scripts\run_s3_evaluation.py` — fitted TF-IDF and trained LinearSVC, Logistic Regression, ComplementNB on the corrected train split; evaluated on corrected test split; wrote JSON, CSV, confusion matrix, and all LinearSVC errors.
5. `python -m pip freeze` — saved verbatim output to `reports/s3_evaluation/pip_freeze.txt` and embedded below.
6. Hardware queried with `Get-CimInstance Win32_ComputerSystem`, `Get-CimInstance Win32_Processor`, and `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader`.

```text
absl-py==2.5.1
aiohappyeyeballs==2.6.1
aiohttp==3.13.5
aiosignal==1.4.0
altair==6.0.0
annotated-doc==0.0.4
annotated-types==0.7.0
anyio==4.13.0
argcomplete==3.6.3
argon2-cffi==25.1.0
argon2-cffi-bindings==25.1.0
arrow==1.4.0
asttokens==3.0.1
astunparse==1.6.3
async-lru==2.3.0
attrs==26.1.0
babel==2.18.0
bcrypt==5.0.0
beautifulsoup4==4.14.3
bleach==6.3.0
blinker==1.9.0
branca==0.8.2
build==1.4.3
cachetools==7.0.6
cairocffi==1.7.1
CairoSVG==2.9.0
catboost==1.2.10
certifi==2026.2.25
cffi==2.0.0
charset-normalizer==3.4.7
chromadb==1.5.8
click==8.3.2
cloudpickle==3.1.2
colorama==0.4.6
comm==0.2.3
contourpy==1.3.3
cssselect2==0.9.0
cycler==0.12.1
dataclasses-json==0.6.7
debugpy==1.8.20
decorator==5.2.1
defusedxml==0.7.1
distro==1.9.0
dm-tree==0.1.10
docstring_parser==0.18.0
durationpy==0.10
einops==0.8.2
et_xmlfile==2.0.0
etils==1.14.0
executing==2.2.1
fastjsonschema==2.21.2
filelock==3.29.0
flatbuffers==25.12.19
folium==0.20.0
fonttools==4.63.0
fqdn==1.5.1
frozenlist==1.8.0
fsspec==2026.3.0
gast==0.7.0
gitdb==4.0.12
GitPython==3.1.46
google-pasta==0.2.0
googleapis-common-protos==1.74.0
graphviz==0.21
greenlet==3.4.0
groq==0.37.1
grpcio==1.80.0
h11==0.16.0
h5py==3.15.1
hf-xet==1.4.3
httpcore==1.0.9
httptools==0.7.1
httpx==0.28.1
httpx-sse==0.4.3
huggingface_hub==1.11.0
idna==3.11
immutabledict==4.3.1
importlib_metadata==8.7.1
importlib_resources==7.1.0
ipykernel==7.2.0
ipython==9.12.0
ipython_pygments_lexers==1.1.1
isoduration==20.11.0
jedi==0.19.2
Jinja2==3.1.6
joblib==1.5.3
json5==0.14.0
jsonpatch==1.33
jsonpointer==3.1.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
jupyter-events==0.12.0
jupyter-lsp==2.3.1
jupyter_client==8.8.0
jupyter_core==5.9.1
jupyter_server==2.17.0
jupyter_server_terminals==0.5.4
jupyterlab==4.5.6
jupyterlab_pygments==0.3.0
jupyterlab_server==2.28.0
keras-nightly==3.16.0.dev2026101404
kiwisolver==1.5.0
kubernetes==35.0.0
langchain==1.2.15
langchain-classic==1.0.4
langchain-community==0.4.1
langchain-core==1.4.8
langchain-groq==1.1.2
langchain-huggingface==1.2.2
langchain-protocol==0.0.18
langchain-text-splitters==1.1.2
langgraph==1.2.6
langgraph-checkpoint==4.1.1
langgraph-prebuilt==1.1.0
langgraph-sdk==0.4.2
langsmith==0.7.33
lark==1.3.1
libclang==18.1.1
llvmlite==0.47.0
lxml==6.0.4
markdown-it-py==4.0.0
MarkupSafe==3.0.3
marshmallow==3.26.2
matplotlib==3.10.9
matplotlib-inline==0.2.1
mdurl==0.1.2
mistune==3.2.0
ml_dtypes==0.6.0
mmh3==5.2.1
more-itertools==11.2.1
mpmath==1.3.0
multidict==6.7.1
mypy_extensions==1.1.0
namex==0.1.0
narwhals==2.20.0
nbclient==0.10.4
nbconvert==7.17.1
nbformat==5.10.4
nest-asyncio==1.6.0
networkx==3.6.1
notebook_shim==0.2.4
numba==0.65.0
numpy==2.4.4
oauthlib==3.3.1
onnxruntime==1.24.4
openai-whisper==20250625
openpyxl==3.1.5
opentelemetry-api==1.41.0
opentelemetry-exporter-otlp-proto-common==1.41.0
opentelemetry-exporter-otlp-proto-grpc==1.41.0
opentelemetry-proto==1.41.0
opentelemetry-sdk==1.41.0
opentelemetry-semantic-conventions==0.62b0
opt_einsum==3.4.0
optree==0.20.0
orjson==3.11.8
ormsgpack==1.12.2
overrides==7.7.0
packaging==26.1
pandas==3.0.2
pandocfilters==1.5.1
parso==0.8.6
pillow==12.2.0
pipx==1.14.1
platformdirs==4.9.6
plotly==6.7.0
prometheus_client==0.25.0
promise==2.3
prompt_toolkit==3.0.52
propcache==0.4.1
protobuf==6.33.6
psutil==7.2.2
pure_eval==0.2.3
pyarrow==23.0.1
pybase64==1.4.3
pycparser==3.0
pydantic==2.13.3
pydantic-settings==2.14.0
pydantic_core==2.46.3
pydeck==0.9.2
Pygments==2.20.0
pyparsing==3.3.2
pypdf==6.10.0
PyPika==0.51.1
pyproject_hooks==1.2.0
pytesseract==0.3.13
python-dateutil==2.9.0.post0
python-docx==1.2.0
python-dotenv==1.2.2
python-json-logger==4.1.0
pywinpty==3.0.3
PyYAML==6.0.3
pyzmq==27.1.0
referencing==0.37.0
regex==2026.4.4
reportlab==5.0.1
requests==2.33.1
requests-oauthlib==2.0.0
requests-toolbelt==1.0.0
rfc3339-validator==0.1.4
rfc3986-validator==0.1.1
rfc3987-syntax==1.1.0
rich==15.0.0
rpds-py==0.30.0
safetensors==0.7.0
scikit-learn==1.8.0
scipy==1.17.1
Send2Trash==2.1.0
sentence-transformers==5.4.1
setuptools==81.0.0
shap==0.51.0
shellingham==1.5.4
simple-parsing==0.1.9
six==1.17.0
slicer==0.0.8
smmap==5.0.3
sniffio==1.3.1
soupsieve==2.8.3
SQLAlchemy==2.0.49
stack-data==0.6.3
streamlit==1.56.0
sympy==1.14.0
tenacity==9.1.4
tensorflow-datasets==4.9.10
tensorflow-metadata==1.21.0
termcolor==3.3.0
terminado==0.18.1
threadpoolctl==3.6.0
tiktoken==0.14.0
tinycss2==1.4.0
tokenizers==0.22.2
toml==0.10.2
torch==2.11.0
tornado==6.5.5
tqdm==4.67.3
traitlets==5.14.3
transformers==5.5.4
typer==0.24.1
typing-inspect==0.9.0
typing-inspection==0.4.2
typing_extensions==4.15.0
tzdata==2026.1
uri-template==1.3.0
urllib3==2.6.3
userpath==1.9.2
uuid_utils==0.14.1
uvicorn==0.44.0
watchdog==6.0.0
watchfiles==1.1.1
wcwidth==0.6.0
webcolors==25.10.0
webencodings==0.5.1
websocket-client==1.9.0
websockets==15.0.1
wheel==0.48.0
wrapt==2.5.1
xgboost==3.2.0
xxhash==3.6.0
xyzservices==2026.3.0
yarl==1.23.0
yt-dlp==2026.7.4
zipp==3.23.1
zstandard==0.25.0
```

## Independent S3 confirmation rerun

On 2026-10-26 local time, `python scripts\run_s3_evaluation.py` was run again from the corrected S3 files without loading the prior model or predictions. The fresh run again used 8,487 train, 1,917 validation, and 1,960 test records and produced LinearSVC accuracy 0.996938775510204 and macro-F1 0.9970010804457539 (rounded in the paper to 0.9969 and 0.9970). It produced six misclassified records. The fresh `reports/s3_evaluation/linear_svc_predictions.json` contains 1,960 predictions with 1,960 unique test IDs; its filesystem modification time was 2026-10-25 19:47:33.164664 UTC (2026-10-26 01:17:33.164664 India time), and its embedded run timestamp is 2026-10-25 19:47:33.156546 UTC. The companion `linear_svc_predictions_metadata.json` records row count, unique-ID count, and SHA-256 `4927f2c512369834f26b0cb734bdd5a5ccfdd377b399711c3de2a5f256c4266b`. Per-class support sums to 1,960. This independently confirms that the repeated rounded macro-F1 was generated from the corrected split in a fresh run.
