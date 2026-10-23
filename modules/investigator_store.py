"""Local file store for structured records intentionally received by investigators."""

import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INBOX_DIR = PROJECT_ROOT / "investigator_inbox"
MAX_CASE_FILE_BYTES = 10 * 1024 * 1024
MAX_EVIDENCE_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_EVIDENCE_BYTES = 100 * 1024 * 1024


def _safe_reference(reference):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", str(reference)).strip("-_")


def load_cases(inbox_dir=DEFAULT_INBOX_DIR):
    inbox = Path(inbox_dir)
    if not inbox.exists():
        return [], []

    cases, errors = [], []
    for path in sorted(inbox.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("record must be a JSON object")
            data["_path"] = str(path.resolve())
            cases.append(data)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append((path.name, str(exc)))
    return cases, errors


def import_case_file(file_bytes, inbox_dir=DEFAULT_INBOX_DIR):
    if not file_bytes:
        raise ValueError("Choose a structured case file first.")
    if len(file_bytes) > MAX_CASE_FILE_BYTES:
        raise ValueError("The structured case file must be 10 MB or smaller.")

    try:
        case = json.loads(file_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("The file is not valid UTF-8 JSON.") from exc

    if not isinstance(case, dict):
        raise ValueError("The case file must contain a JSON object.")
    reference = str(case.get("reference", "")).strip()
    safe_reference = _safe_reference(reference)
    if not safe_reference:
        raise ValueError("The case file must include a usable case reference.")
    if not any(isinstance(case.get(key), dict) for key in ("complaint", "incident", "classification")):
        raise ValueError("The file does not contain structured complaint, incident, or classification details.")

    inbox = Path(inbox_dir).resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / f"{safe_reference}.json"
    if target.exists():
        raise FileExistsError(f"Case reference {reference} is already in the investigator inbox.")

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    case["status"] = "RECEIVED - AWAITING REVIEW"
    case["_investigator_received_at"] = now
    case["_activity_log"] = [{
        "at": now,
        "actor": "System",
        "action": "Structured case file received",
        "details": "Imported into the local investigator inbox.",
    }]
    case["_path"] = str(target)
    save_case(case, inbox_dir=inbox)
    return case


def save_received_evidence(case, files, inbox_dir=DEFAULT_INBOX_DIR):
    if not files:
        return []
    if len(files) > 20:
        raise ValueError("Attach no more than 20 evidence files at a time.")
    total_bytes = sum(len(content) for _, content in files)
    if total_bytes > MAX_TOTAL_EVIDENCE_BYTES:
        raise ValueError("Combined evidence files must be 100 MB or smaller.")
    if any(len(content) > MAX_EVIDENCE_FILE_BYTES for _, content in files):
        raise ValueError("Each evidence file must be 25 MB or smaller.")

    inbox = Path(inbox_dir).resolve()
    case_path = Path(case.get("_path", "")).resolve()
    if case_path.parent != inbox or case_path.suffix.lower() != ".json":
        raise ValueError("Refusing to attach evidence outside the investigator inbox.")
    evidence_dir = inbox / f"{case_path.stem}_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for index, (original_name, content) in enumerate(files, start=1):
        name = Path(str(original_name)).name
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(name).stem).strip("_") or f"evidence_{index}"
        suffix = Path(name).suffix.lower()[:12]
        target = evidence_dir / f"{index:02d}_{stem}{suffix}"
        target.write_bytes(content)
        saved.append({"name": name, "path": str(target.relative_to(inbox))})

    case.setdefault("received_evidence_files", []).extend(saved)
    add_activity(case, "System", "Evidence files received", f"{len(saved)} file(s) attached to the local case record.")
    return saved


def resolve_evidence_path(case, relative_path, inbox_dir=DEFAULT_INBOX_DIR):
    inbox = Path(inbox_dir).resolve()
    path = (inbox / str(relative_path)).resolve()
    if path != inbox and inbox not in path.parents:
        raise ValueError("Evidence path is outside the investigator inbox.")
    return path if path.is_file() else None


def save_case(case, inbox_dir=DEFAULT_INBOX_DIR):
    raw_path = case.get("_path")
    if not raw_path:
        raise ValueError("The case has no inbox file path.")

    inbox = Path(inbox_dir).resolve()
    path = Path(raw_path).resolve()
    if path.parent != inbox or path.suffix.lower() != ".json":
        raise ValueError("Refusing to write a case outside the investigator inbox.")

    payload = {key: value for key, value in case.items() if key != "_path"}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    case["_path"] = str(path)
    return True


def add_activity(case, actor, action, details=""):
    log = case.setdefault("_activity_log", [])
    if not isinstance(log, list):
        log = case["_activity_log"] = []
    log.append({
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "actor": str(actor).strip(),
        "action": str(action).strip(),
        "details": str(details).strip(),
    })
