# UI screenshots for the project report

Screenshots were captured from the local application at `http://127.0.0.1:8501/`. The complaint narrative shown is fictional. The officer overview displays aggregate counts only; case rows and personal details are not included.

| File | Suggested report caption | Suggested section |
|---|---|---|
| `01-home-dashboard.jpg` | Citizen portal home page and reporting workflow | User interface / Home screen |
| `02-consent-before-reporting.jpg` | Privacy and data-use consent shown before complaint intake | Consent and privacy |
| `03-guided-complaint-intake.jpg` | Guided voice and multilingual complaint intake | Complaint registration |
| `04-officer-dashboard-overview.jpg` | Officer dashboard with queue and workload statistics | Officer dashboard |
| `05-manual-intake-fictional-example.jpg` | Manual complaint form with fictional incident details | Complaint registration |
| `06-review-before-classification.jpg` | Complaint narrative and extracted fields presented for user review | NLP analysis and user review |
| `07-manual-intake-upi-sample.jpg` | Fictional UPI complaint details entered in the manual form | Complaint registration |
| `08-review-complaint-details.jpg` | Review step before the classifier runs | User confirmation |
| `09-classification-results.jpg` | Suggested category, estimated match, and next steps | NLP classification results |
| `10-status-tracking.jpg` | Local complaint reference lookup screen | Status tracking |
| `11-officer-case-triage.jpg` | Officer queue, saved-record statistics, and a queue filtered to the fictional Example Complainant record | Investigator dashboard / case triage |
| `12-investigator-case-detail.jpg` | Fictional case details, summary, reported transaction, and possible legal references for officer verification | Investigator case review |
| `13-case-evidence-links-reconciliation.jpg` | Evidence and cross-check state plus possible related records; this sample has no attached evidence | Evidence review / repeat-pattern leads |
| `14-case-review-workflow-actions.jpg` | Review decision, category correction, assignment/status workflow, request-draft actions, and complaint PDF link | Case management / report actions |
| `15-officer-priority-status-queue.jpg` | Filtered queue view focused on urgency, status, assignment, and evidence-check indicators | Investigator dashboard / prioritization |

Suggested report sequence: 01 home, 02 consent, 03 guided intake, 05 or 07 manual intake, 06 or 08 user review, 09 classification results, 10 status tracking, 04 officer overview, then 11–14 investigator review. The narrative and `Example Complainant` records shown in the screenshots are fictional demonstration data. The investigator screenshots are filtered to those example records; do not use unfiltered queue rows in a report.

## Coverage and limitations to reflect in the report

- Screenshots 03 and 06–09 show the guided intake, detail review, classifier suggestion, and category guidance. Screenshot 03 is the assistant's initial state; the conversational follow-up path did not complete reliably during this capture session. Do not use it as proof that every gap question was answered successfully.
- Screenshot 11 shows triage statistics and a filtered queue. The displayed totals come from the local sample queue and are illustrative, not government or police statistics.
- Screenshot 13 shows a case with no attached evidence and no recorded conflict. It does not demonstrate successful OCR, amount-mismatch reconciliation, or an evidence preview. The local run reported that OCR was unavailable on this computer.
- Screenshot 12 includes a warning for an NPCI guideline entry whose section is undefined. Treat the BNS and IT Act entries as suggestions requiring officer verification; correct or remove the undefined NPCI entry before presenting it as a legal reference.
- Screenshot 14 demonstrates the available local workflow controls and complaint PDF link. The visible actions prepare bank and phone-record request drafts; they are not evidence of BNSS/BSA statutory notice generation. The HTML officer dashboard has no login/access control and is not connected to police systems.
- A saved-record confirmation screen, successful local Whisper transcription, successful OCR extraction, populated evidence mismatch review, and BNSS/BSA notice output were not captured in this session. The report should only claim these where a verified implementation screen or backend result is available.
## Report section with figure references

`report-section-with-figures.tex` is the supplied LaTeX passage with figures inserted under the home page and each described intake/investigator screen. Its image paths are relative to the repository root, so compile the report from that root or adjust the paths for your report project. The same updated passage was written back to the provided `Pasted text.txt` attachment.

The passage uses the existing verified screenshots. It includes notes where a capture does not demonstrate a completed flow: successful voice transcription, a follow-up answer, evidence preview/progress, saved-submission confirmation, OCR mismatch, a confirmed repeat-offender link, or BNSS/BSA notice generation.
