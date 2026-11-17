"""Render an accurate, report-ready architecture figure from project code paths."""

from pathlib import Path
from textwrap import fill as wrap_text
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


OUT = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)

COLORS = {
    "ink": "#153149", "muted": "#536B7B", "line": "#9CB2C1",
    "bg": "#F4F7FA", "white": "#FFFFFF", "blue": "#E7F1FA",
    "teal": "#E4F3F0", "gold": "#FBF2DD", "purple": "#F0EBF8",
    "gray": "#EBF0F4", "external": "#9A6B25", "accent": "#176B87",
}

fig, ax = plt.subplots(figsize=(16.5, 11.0), facecolor=COLORS["bg"])
ax.set_facecolor(COLORS["bg"])
ax.set_xlim(0, 16.5)
ax.set_ylim(0, 11)
ax.axis("off")

ax.text(0.55, 10.52, "INTELLIGENT CYBERCRIME COMPLAINT ANALYSIS", fontsize=19,
        fontweight="bold", color=COLORS["ink"], va="center")
ax.text(0.55, 10.13, "AND COMPLAINT CATEGORY CLASSIFICATION USING NLP",
        fontsize=15.2, fontweight="bold", color=COLORS["ink"], va="center")
ax.text(0.55, 9.73, "Full system architecture · browser clients, FastAPI services, NLP pipeline and local case stores",
        fontsize=9.5, color=COLORS["muted"], va="center")

lanes = [
    (0.40, 2.25, "ACTORS & CHANNELS", COLORS["gray"]),
    (2.78, 2.70, "WEB FRONTEND", COLORS["blue"]),
    (5.60, 2.70, "FASTAPI BACKEND", COLORS["teal"]),
    (8.42, 4.00, "ANALYSIS & CASE SERVICES", COLORS["gold"]),
    (12.52, 3.58, "LOCAL DATA & FILES", COLORS["purple"]),
]
for x, w, title, color in lanes:
    p = FancyBboxPatch((x, 0.64), w, 8.63, boxstyle="round,pad=0.02,rounding_size=0.12",
                       linewidth=0.8, edgecolor="#D6E0E7", facecolor=color, zorder=0)
    ax.add_patch(p)
    ax.text(x + 0.16, 9.00, title, fontsize=9.4, fontweight="bold", color=COLORS["ink"], va="center")

def card(key, x, y, w, h, title, body, fill=COLORS["white"], title_color=COLORS["ink"], fontsize=8.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.035,rounding_size=0.10",
                       linewidth=1.15, edgecolor="#A8BBC8", facecolor=fill, zorder=3)
    ax.add_patch(p)
    ax.text(x + 0.13, y + h - 0.19, title, fontsize=9.0, fontweight="bold",
            color=title_color, va="top", zorder=4)
    width = max(23, int(w * 14.8))
    body = "\n".join(wrap_text(part, width=width) if part else "" for part in body.split("\n"))
    ax.text(x + 0.13, y + h - 0.49, body, fontsize=fontsize, color=COLORS["muted"],
            va="top", linespacing=1.34, zorder=4)
    return (x, y, w, h)

def arrow(a, b, label=None, color=COLORS["accent"], rad=0.0, dashed=False, label_dy=0.12):
    x1, y1 = a; x2, y2 = b
    p = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
                        linewidth=1.35, color=color, connectionstyle=f"arc3,rad={rad}",
                        linestyle="--" if dashed else "-", zorder=2, shrinkA=1, shrinkB=2)
    ax.add_patch(p)
    if label:
        ax.text((x1+x2)/2, (y1+y2)/2+label_dy, label, fontsize=6.6, color=color,
                ha="center", va="center", zorder=5,
                bbox=dict(boxstyle="round,pad=0.12", facecolor=COLORS["bg"], edgecolor="none", alpha=.94))

# Cards use five horizontal flows: intake, evidence, voice, registration, investigator review.
cit = card("cit", .58, 7.42, 1.88, 1.04, "Citizen", "Describe incident · consent\nReview result · submit · track")
off = card("off", .58, 1.15, 1.88, 1.04, "Investigator", "Triage cases · inspect evidence\nUpdate workflow · export reports")

portal = card("portal", 2.98, 7.32, 2.30, 1.23, "Citizen web portal", "HTML5 · CSS3 · JavaScript\nGuided multilingual text / voice intake\nConsent gate · evidence · status", COLORS["white"])
evidence_ui = card("evidence_ui", 2.98, 5.63, 2.30, 1.15, "Evidence & review UI", "Upload / preview attachments\nReview extracted details and\nclassification before registration")
voice_ui = card("voice_ui", 2.98, 3.94, 2.30, 1.15, "Voice capture", "Browser speech / MediaRecorder\nAudio transcript returned to the\nsame narrative intake path")
submit_ui = card("submit_ui", 2.98, 2.26, 2.30, 1.15, "Confirm & track", "Consent required for local\ninvestigator workspace; show case\nreference and victim guidance")
off_ui = card("off_ui", 2.98, 1.04, 2.30, 1.15, "Investigator dashboard", "Search · filter · inspect case\nEvidence · status · legal suggestions\nPDF / JSON · document drafts")

api_intake = card("api_intake", 5.80, 7.32, 2.30, 1.23, "Intake & conversation APIs", "POST /api/chat\nPOST /agent/session/{id}/message\nPOST /api/intake/analyze · /api/confirm")
api_evidence = card("api_evidence", 5.80, 5.63, 2.30, 1.15, "Evidence APIs", "POST /api/upload_evidence\nGET /api/evidence/{filename}\nPOST /api/evidence/reconcile")
api_voice = card("api_voice", 5.80, 3.94, 2.30, 1.15, "Transcription APIs", "POST /api/transcribe\nPOST /api/transcribe_audio\nHealth & app state endpoints")
api_submit = card("api_submit", 5.80, 2.26, 2.30, 1.15, "Case registration APIs", "POST /api/cases/submit\nPOST /api/cases/track\nPOST /api/generate_pdf")
api_off = card("api_off", 5.80, 1.04, 2.30, 1.15, "Investigation APIs", "GET /api/cases · case detail\nWorkflow · adjudication · correlation\nTemplates · PDF · benchmark")

agent = card("agent", 8.62, 7.58, 3.58, 1.10, "Conversational intake & gap resolution", "Question-by-question slot filling · deterministic gap checks · grounded reply validation\nOptional Gemini API / Ollama provider; deterministic fallback on failure", COLORS["white"], fontsize=7.5)
evidence = card("evidence", 8.62, 5.83, 3.58, 1.10, "Evidence processing (when supported / available)", "Image OCR: Tesseract · PDF text: PyMuPDF · entity extraction\nCompare narrative with extracted evidence; surface agreements / conflicts / gaps", COLORS["white"], fontsize=7.4)
nlp = card("nlp", 8.62, 4.08, 3.58, 1.10, "NLP classification & triage", "TF-IDF features → LinearSVC (21 crime labels) → margin-derived confidence\nKeyword urgency / Golden Hour signals · routing · preliminary category", COLORS["white"], fontsize=7.35)
guidance = card("guidance", 8.62, 2.33, 3.58, 1.10, "Decision support & case assembly", "Auto-fill · victim guidance · deterministic BNS / IT Act suggestions\nStructured case JSON · ReportLab PDF; officer must verify suggestions", COLORS["white"], fontsize=7.4)
offsvc = card("offsvc", 8.62, 0.92, 3.58, 1.17, "Investigation services", "Workflow / status store · officer adjudication · SQLite pattern matching\nRelated-case leads · statutory notice drafts · structured JSON / PDF access", COLORS["white"], fontsize=7.3)

stores = card("db", 12.73, 7.65, 3.15, 0.91, "complaints.db (SQLite)", "Intake sessions · messages · complaint drafts", COLORS["white"], fontsize=7.4)
uploads = card("uploads", 12.73, 6.12, 3.15, 0.91, "uploads/", "Uploaded evidence originals; may be OCR-processed", COLORS["white"], fontsize=7.4)
casefiles = card("casefiles", 12.73, 4.59, 3.15, 0.91, "case_files/", "Registered complaint JSON and generated PDF", COLORS["white"], fontsize=7.4)
inbox = card("inbox", 12.73, 3.06, 3.15, 0.91, "investigator_inbox/", "Local officer workspace case records + copied evidence", COLORS["white"], fontsize=7.4)
index = card("index", 12.73, 1.53, 3.15, 0.91, "SQLite case index(es)", "Cross-case matching over stored case identifiers / entities", COLORS["white"], fontsize=7.4)

# Primary user and data flows.
arrow((2.47, 7.95), (2.97, 7.95))
arrow((5.29, 7.95), (5.79, 7.95), "HTTP / JSON")
arrow((8.11, 7.95), (8.61, 7.95))
arrow((12.21, 8.12), (12.72, 8.12), "session state")

arrow((5.29, 6.19), (5.79, 6.19), "file upload")
arrow((8.11, 6.19), (8.61, 6.19))
arrow((12.21, 6.32), (12.72, 6.55), "originals", rad=.02)

arrow((5.29, 4.50), (5.79, 4.50), "audio")
arrow((8.11, 4.50), (8.61, 4.50))

arrow((2.47, 1.67), (2.97, 1.67))
arrow((5.29, 1.62), (5.79, 1.62), "case queries / updates")
arrow((8.11, 1.62), (8.61, 1.62))
arrow((12.21, 1.50), (12.72, 3.50), rad=-.05)
arrow((12.21, 1.36), (12.72, 1.95), rad=-.04)

arrow((5.29, 2.82), (5.79, 2.82), "confirmed payload")
arrow((8.11, 2.82), (8.61, 2.82))
arrow((12.21, 2.79), (12.72, 5.05), rad=-.04)
arrow((12.21, 2.62), (12.72, 3.52), rad=-.02)
arrow((12.21, 1.16), (12.72, 1.88), rad=.01)

# The service descriptions document process order and data relationships;
# arrows are reserved for request paths and persisted outputs to stay readable.

# Runtime / trust boundary and data handling notes.
ax.text(0.58, 0.10,
        "Runtime: Uvicorn serves the HTML/CSS/JavaScript app and JSON APIs. SQLite and evidence/case files are local to this prototype.\n"
        "No authentication or external police-system integration is represented here. OCR and optional LLM calls depend on installed/configured providers.\n"
        "Classification and statutory suggestions are decision support for review by an authorized officer.",
        fontsize=6.7, color=COLORS["muted"], va="bottom", linespacing=1.25)

fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
for suffix, kwargs in {
    "svg": {"format": "svg"},
    "pdf": {"format": "pdf", "metadata": {"Title": "Full System Architecture — Intelligent Cybercrime Complaint Analysis and Complaint Category Classification using NLP"}},
    "png": {"format": "png", "dpi": 260},
}.items():
    fig.savefig(OUT / f"full_architecture.{suffix}", facecolor=fig.get_facecolor(), **kwargs)
plt.close(fig)
print("Rendered reports/full_architecture.svg, .pdf and .png")
