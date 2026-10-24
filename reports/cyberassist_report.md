# Cybercrime Complaint Analysis and Investigator Review System
## Updated Project Report

**Submitted in partial fulfillment of the requirements for the degree of Bachelor of Engineering in Computer Engineering**

**Department of Computer Engineering**
K. K. Wagh Institute of Engineering Education & Research, Nashik, Maharashtra
Savitribai Phule Pune University
Academic year: 2025-2026

**Project guide:** Prof. I. Priyadarshini
**Head of Department:** Dr. Snehal Kamalapur

| Student | Examination number |
|---|---|
| Pranit Chavan | T231301016 |
| Harshal Dahiphalkar | T231301021 |
| Yash Kanhe | T231301060 |
| Chaitanya Mali | T231301074 |

**Report status:** Updated implementation report based on the project repository reviewed on 24 October 2026.
**Project title in Phase I submission:** Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP.

> This report describes an academic prototype. It does not claim to submit complaints to a government portal, contact a bank or law-enforcement system, or make legal determinations. Generated case documents are drafts for human review.

# Certificate

This is to certify that the project report entitled **“Cybercrime Complaint Analysis and Investigator Review System”** is a record of project work carried out by Pranit Chavan (T231301016), Harshal Dahiphalkar (T231301021), Yash Kanhe (T231301060), and Chaitanya Mali (T231301074) under the guidance of Prof. I. Priyadarshini, in partial fulfillment of the requirements for the degree of Bachelor of Engineering in Computer Engineering at K. K. Wagh Institute of Engineering Education & Research, Nashik, during academic year 2025-2026.

This page is a report template for institutional review. It is not a signed or approved certificate. The guide, Head of Department, and institute must verify the project details and add signatures and dates before formal submission.

| Project Guide | Head of Department | Principal / Director |
|---|---|---|
| Prof. I. Priyadarshini  \nSignature: __________________  \nDate: __________________ | Dr. Snehal Kamalapur  \nSignature: __________________  \nDate: __________________ | Name: __________________  \nSignature: __________________  \nDate: __________________ |

# Abstract

People reporting online fraud often need to describe an incident, identify payment details, preserve evidence, and explain what happened to an investigator. This project provides a local web application that guides a complainant through a conversational or manual intake, accepts typed text, speech transcripts, and evidence files, and prepares a structured complaint draft. A separate investigator environment stores submitted case records in a local inbox for review.

The current implementation combines a FastAPI service with a standalone HTML, CSS, and JavaScript interface. The earlier Streamlit dashboard remains in the repository. Complaint text can be classified into a 21-label taxonomy using a saved TF-IDF and LinearSVC model. OCR uses Tesseract, with PDF/image handling and deterministic pattern extraction for fields such as amounts, transaction references, UPI IDs, dates, times, bank names, payment apps, and masked account details. Extracted evidence is shown alongside the complainant’s account; agreement, evidence-only values, missing fields, and conflicts are represented separately so that uncertain evidence is not silently treated as confirmed fact. A conversational assistant asks follow-up questions, while a manual form and editing controls provide an alternative. Speech capture/transcription is available through browser speech recognition and optional local Whisper processing, depending on the selected path and installed dependencies.

After confirmation, the application can create a structured case record and draft PDF. The investigator interface supports a local review queue, case detail review, evidence inspection, workflow updates, and JSON case import. Local SQLite databases persist intake sessions and indexing/workflow information; case JSON and evidence files are stored separately in local folders. Legal references and urgency indicators are suggestions for review, not decisions.

The project is a functional academic prototype, not an official reporting service or production case-management platform. The included classification data are generated and intentionally vocabulary-separated; the repository itself warns that excellent benchmark scores on these splits do not measure real-world accuracy. Human verification, privacy safeguards, access control, independent evaluation, and operational deployment remain essential future work.

**Keywords:** cybercrime intake, complaint drafting, text classification, OCR, evidence reconciliation, speech transcription, investigator review, human oversight.

# Acknowledgement

We thank our project guide, Prof. I. Priyadarshini, for guidance during the project, and Dr. Snehal Kamalapur, Head of the Department of Computer Engineering, for academic support. We also acknowledge the K. K. Wagh Institute of Engineering Education & Research and Savitribai Phule Pune University. The project builds on open-source software and research cited in the references. This acknowledgement should be reviewed and edited by the student team before submission.

# Contents

The generated table of contents below includes all numbered headings in the report. The chapter structure follows the provided 64-page sample; project-specific modules, results, and annexures are adapted to this repository.

# List of Figures

3.1 Complaint intake methodology
4.1 Iterative project plan
6.1 System architecture
6.2 Intake and case review workflow
6.3 Evidence reconciliation model

# List of Tables

1.1 Project user roles and outputs
3.1 Scope and project outcomes
5.1 Hardware requirements
5.2 Software and library requirements
6.1 Data persistence overview
7.1 Dataset distribution
7.2 Evaluation values reported by the repository
7.3 Software validation status

# Chapter 1. Introduction

## 1.1 Project Idea

Cybercrime complaints can contain several kinds of information in different forms: a person’s narrative, a payment notification, a bank message, a chat screenshot, a voice description, or a transaction identifier. A complainant may not know which details are useful, and investigators need to review the narrative and supporting evidence together. Repeatedly asking for details already visible in an uploaded receipt creates friction and may lead to inconsistent records.

This project addresses the information-collection and organization stage. It combines a guided intake with file-based evidence extraction and a separate investigator review experience. Its purpose is to help a person prepare a more complete, editable draft and to make the captured information easier to inspect. It is not a replacement for official channels or investigator judgment.

## 1.2 Motivation of the Project

The initial Phase I proposal focused on NLP-based complaint classification. Development expanded it into a guided intake and investigator-review workflow because classification alone does not solve the practical problems of collecting a complete account, reading transaction evidence, correcting recognition errors, and ensuring a submitted record can be found by a reviewer. This report documents the current repository rather than presenting proposed Phase I functionality as completed work.

The system currently has two interface paths. FastAPI serves a separate static frontend from `static/`; `dashboard.py` retains the Streamlit application. These frontends share domain modules and service functionality, but they are distinct user interfaces and may not expose precisely identical interactions. The investigator workflow is part of the newer web interface and should be validated independently from the Streamlit view.

The prototype aims to reduce repeated manual entry, use uploaded evidence to populate candidate facts, and preserve a clear handoff from complainant confirmation to investigator review. It is designed for local academic demonstration and does not automatically file reports with public authorities.

## 1.3 Objectives

- Provide an accessible intake path using conversation, a manual form, typed input, and speech-derived text.
- Collect key facts and ask targeted follow-up questions where information remains missing.
- Let a complainant upload evidence and review OCR-derived fields before using them in a draft.
- Identify a likely complaint category as decision support and display uncertainty and alternatives.
- Produce a structured, editable complaint draft and a downloadable document.
- Store submitted records in a local investigator review workflow, with evidence associated with its individual case.
- Keep the process understandable to non-technical users and preserve human review at important decision points.

## 1.4 Intended users

**Complainant:** describes an incident, uploads evidence, reviews extracted details, corrects the draft, and chooses to submit the local case record.

**Investigator or reviewer:** opens records received in the local inbox, checks the narrative and evidence, reviews extraction conflicts and model suggestions, and updates the case workflow.

The terms “complainant” and “investigator” refer to prototype roles and do not imply authenticated real-world identities or official jurisdictional authority.

| User role | Main actions | Output |
|---|---|---|
| Complainant | Describe the incident, upload evidence, correct extracted details, review and submit a draft | Structured complaint record and draft document |
| Investigator / reviewer | Find a local case, inspect narrative and evidence, review suggested fields, update workflow | Locally updated review status and case notes |

# Chapter 2. Literature Survey

## 2.1 Text classification

TF-IDF represents text using weighted terms and is a common baseline for document categorization. Linear support-vector classification provides an efficient linear decision boundary and supports multiclass classification through a one-versus-rest approach in scikit-learn. This combination is useful as a lightweight, inspectable baseline for categorizing complaint narratives. It does not by itself establish semantic understanding, calibrated probabilities, or operational suitability. The implementation uses the highest decision margin and a bounded transformation of the gap between top margins as a confidence-like score; this number is a heuristic and must not be interpreted as a calibrated probability.

Joulin et al. describe efficient text classification with bag-of-words and n-gram features as a practical baseline [1]. The current project uses a TF-IDF + LinearSVC implementation rather than fastText, but the reference supports the broader use of sparse lexical representations as baselines.

## 2.2 Optical character recognition

OCR converts image pixels into text that can be searched and processed. The project uses Tesseract through `pytesseract`, then applies deterministic patterns and known-name matching to extract candidate entities. This approach is auditable and avoids asking a generative model to invent exact transaction identifiers. OCR remains sensitive to image quality, fonts, cropping, contrast, transliteration, and character confusion. A recognized value must therefore retain provenance and be checked against the original attachment.

## 2.3 Speech recognition

Automatic speech recognition produces text from audio and can make intake more accessible. The repository supports browser speech recognition for live capture in supported browsers and optional local Whisper transcription for uploaded audio when its package and model dependencies are available. Radford et al. describe Whisper’s multilingual weakly supervised training and its robustness across several speech tasks [2]. Recognition errors are still possible, especially with noise, accents, code-switching, names, and numeric identifiers. The user must be able to inspect and correct transcripts before relying on them.

## 2.4 Conversational intake and human-centered automation

A conversational interface can guide a person through details that are easy to omit. For reliable data collection, questions should be tied to explicit information gaps, responses should update a visible draft, and previously answered fields should not be repeatedly requested. The current implementation combines LLM-backed behavior with deterministic state and fallback logic. Provider availability and response quality depend on configuration, and every generated question or narrative needs validation. This project therefore treats the assistant as a drafting aid, not an authoritative source.

## 2.5 Evidence reconciliation

An OCR result and a complainant statement are separate sources. If the two agree, the match can be surfaced for confirmation; if OCR supplies a value not mentioned in the narrative, it can fill a candidate field; if they disagree, the difference should remain visible for review. The repository’s reconciliation module implements these distinct outcomes and generates missing-information gaps. This is preferable to silently overwriting one source with another, but it does not establish authenticity of an image or prove that a transaction occurred.

## 2.6 Position of the project

The contribution is an integrated prototype workflow that connects intake, classification support, evidence extraction, review, and local case persistence. It is not a new OCR engine, language model, or validated cybercrime risk model. Its engineering value is in connecting these components with explicit review steps and a separate investigator experience.

# Chapter 3. Problem Definition and Scope

## 3.1 Problem statement

People reporting a cyber incident may provide incomplete or unstructured descriptions, while useful facts can be contained in screenshots or documents. Existing manual collection can require repeated questions and re-entry. The project seeks to organize these inputs into a reviewable draft and local case record, while making uncertainty and source differences visible.

## 3.2 Methodology

The project follows an input–analysis–review–handoff sequence. It collects a narrative and optional evidence, extracts candidate entities, identifies gaps or source conflicts, presents targeted questions, and lets the complainant review the draft. Once submitted, the local case record is made available to the investigator interface. Figure 3.1 summarizes this conceptual method; it describes the implemented workflow and is not a deployment diagram.

**Figure 3.1.** Complaint intake methodology.

```text
Narrative / manual entry / voice transcript + image or PDF evidence
                  -> extract and classify candidate information
                  -> compare sources and identify missing details
                  -> ask focused follow-up questions
                  -> complainant reviews and confirms draft
                  -> local case record -> investigator review
```

## 3.3 Project Outcomes

| Included in the current repository | Not established by the current repository |
|---|---|
| Local citizen intake through separate web frontend; legacy Streamlit app remains | Official filing to NCRP, a police portal, bank, or payment network |
| Typed conversation, manual form, and voice-to-text options | Verified identity, legally valid electronic signature, or actual victim verification |
| Image/PDF upload and OCR-based candidate field extraction | Forensic proof of authenticity, chain of custody, or guaranteed OCR accuracy |
| Category prediction, urgency cues, and suggested legal references | Legal advice, final legal classification, or automatic enforcement action |
| Editable draft and generated PDF / structured JSON | Production-grade multi-tenant deployment or secure internet-facing service |
| Local investigator review queue and workflow updates | Role-based authentication, authorization, audit controls, or official assignment |
| Optional configured Gemini/Ollama paths and deterministic fallbacks | Guaranteed LLM availability, correctness, privacy terms, or response consistency |

The principal outcome is an integrated academic prototype comprising two user-facing environments, a local API, a complaint classifier, evidence extraction and reconciliation, and local case review. The outcomes are implementation capabilities, not claims of field validation or production readiness.

## 3.4 Assumptions and Constraints

- Evidence is supplied by the user and may be incomplete, unclear, or unrelated.
- OCR, ASR, and LLM outputs are fallible; the interface should require human confirmation.
- Tesseract must be installed and discoverable for image OCR. PDF and image support requires the Python dependencies listed in `requirements.txt`.
- Local Whisper transcription requires its optional package, model assets, and compatible runtime. Browser speech recognition depends on browser support and permissions.
- Gemini use requires valid configuration and external network access; Ollama paths require a locally available service and model.
- Case and evidence storage is local filesystem/SQLite persistence. The repository does not provide production user authentication or a secure cloud storage design.
- The classifier’s available training/evaluation dataset is generated. Its lexical construction makes reported split performance unsuitable as a real-world accuracy estimate.

# Chapter 4. Project Plan

## 4.1 Team Organization

### 4.1.1 Team Structure

| Team member | Examination number | Responsibility record |
|---|---|---|
| Pranit Chavan | T231301016 | Team member; specific current module ownership to be confirmed by the team |
| Harshal Dahiphalkar | T231301021 | Team member; specific current module ownership to be confirmed by the team |
| Yash Kanhe | T231301060 | Team member; specific current module ownership to be confirmed by the team |
| Chaitanya Mali | T231301074 | Team member; specific current module ownership to be confirmed by the team |

No module ownership is assigned here because the source material does not establish a verified responsibility matrix. The team may replace the final column with approved contributions before submission.

## 4.2 Project Plan

The project evolved iteratively from the Phase I classification idea toward an end-to-end prototype. Work can be understood in these stages: (1) taxonomy and baseline model, (2) narrative/entity extraction and conversational state, (3) OCR and evidence reconciliation, (4) case-file generation and local persistence, (5) web and Streamlit interfaces, and (6) investigator workflow and integration refinement. Figure 4.1 shows these stages as an ordered plan. It is not a dated Gantt chart because verified sprint dates and effort records were not supplied.

**Figure 4.1.** Iterative project plan.

```text
Classifier baseline -> Intake and extraction -> Evidence/OCR reconciliation
          -> Case persistence -> Citizen and investigator interfaces -> Integration refinement
```

## 4.3 Project Deliverables

- FastAPI application and static frontend source.
- Retained Streamlit dashboard.
- Classification and taxonomy artifacts stored under `models/` and project modules.
- OCR, entity extraction, reconciliation, speech, conversational-intake, and case-building modules.
- Local investigator case store and review interface.
- Automated test files under `tests/` and supporting project documentation.
- This updated implementation report and its reproducible source.

# Chapter 5. Software Requirements Specification

## 5.1 Functional requirements

| ID | Requirement | Current implementation summary |
|---|---|---|
| FR-01 | Start a complaint intake session | Frontend creates a session identifier; FastAPI persists session and messages locally. |
| FR-02 | Accept incident information | Conversation, manual form, typed answer, and supported speech paths are present. |
| FR-03 | Ask follow-up questions | Conversational module tracks a complaint docket and information gaps; model-backed and fallback behavior are configured in code. |
| FR-04 | Upload supporting evidence | Upload endpoint accepts supported formats with size/type limits and stores local evidence. |
| FR-05 | Extract candidate facts from images/PDFs | OCR and deterministic entity patterns yield candidate values with per-value metadata. |
| FR-06 | Compare text and evidence | Reconciliation returns agreements, OCR-only facts, missing fields, and conflicts. |
| FR-07 | Classify complaint text | Saved TF-IDF/LinearSVC assets return a predicted label, alternatives, margins, and a heuristic confidence-like value. |
| FR-08 | Review and edit the draft | Citizen frontend includes manual editing/confirmation paths before case submission. |
| FR-09 | Create a case record | Submission writes structured JSON and generated documents, then makes the record available to the local investigator inbox. |
| FR-10 | Review and update a case | Investigator paths include queue listing, case detail, workflow updates, adjudication/syndication endpoints, and evidence review. |
| FR-11 | Import an existing case | JSON import endpoint validates structure and stores a received record; evidence can be associated with the imported case. |
| FR-12 | Track or retrieve a local case | Case lookup and tracking endpoints operate on local project storage. |

## 5.2 Nonfunctional requirements

- **Usability:** separate citizen and investigator contexts; plain-language labels; visible values and corrections.
- **Reliability:** missing OCR/LLM/ASR dependencies should produce an error or fallback rather than silently claiming successful extraction.
- **Traceability:** retain source distinctions and show when data are model- or OCR-derived.
- **Privacy:** minimize unnecessary collection and protect local case files. Current prototype does not meet production access-control requirements.
- **Maintainability:** service, UI, extraction, classification, persistence, and investigator logic are separated into modules.
- **Portability:** runs locally with Python and documented dependencies; some capabilities depend on external system packages or model/provider setup.
- **Performance:** local classification and regex extraction are designed as lightweight operations; actual end-to-end latency depends on hardware, OCR, audio model, and LLM provider and has not been benchmarked here.

## 5.3 Constraints

- Evidence may be incomplete, unclear, unrelated, or manipulated; OCR does not verify authenticity.
- OCR, ASR, classifier, and LLM outputs are fallible and require human review.
- Local storage and the absence of production-grade authentication restrict appropriate use to a controlled environment.
- Provider-backed functions depend on credentials, network access, or local model services and may be unavailable.
- The available classifier dataset is generated and cannot establish real-world accuracy.

## 5.4 Hardware Requirements

The repository does not specify a verified minimum hardware configuration or a tested deployment target. Table 5.1 therefore records only the hardware classes implied by implemented functions; exact capacity should be set after measuring the intended installation.

| Component | Requirement or note |
|---|---|
| Development / server computer | General-purpose computer able to run the supported Python environment and local web service; minimum CPU/RAM not benchmarked |
| Client device | Modern desktop or mobile device with a supported browser |
| Microphone | Optional; needed for browser speech capture |
| Storage | Local disk for application, SQLite data, uploaded evidence, and generated drafts; capacity depends on usage and retention |
| GPU | Not required by the TF-IDF/LinearSVC classifier; optional local speech models may have different runtime needs |

## 5.5 Software Requirements

Table 5.2 summarizes software dependencies and their purpose. Exact package pins are maintained in the repository requirements file and should be checked against the selected Python version at installation time.

| Software / library | Purpose | Status or external dependency |
|---|---|---|
| Python, FastAPI, Uvicorn | API and application runtime | Required |
| HTML, CSS, JavaScript | Standalone browser frontend | Served locally by the application |
| Streamlit | Retained dashboard interface | Required for Streamlit path |
| scikit-learn, NumPy, pandas | Text classification and data operations | Required by classifier path |
| Pillow, PyMuPDF, pytesseract, Tesseract | Image/PDF processing and OCR | Tesseract executable must be installed separately |
| ReportLab | Draft PDF generation | Required for PDF output path |
| Browser SpeechRecognition API | Live speech-to-text where supported | Browser support and microphone permission required |
| Whisper | Optional audio transcription | Optional package, model assets, and compatible runtime |
| Gemini API or Ollama | Optional conversational model provider | Requires valid provider configuration or local service |

## 5.6 Interfaces

# Chapter 6. Detailed Design

## 6.1 Architecture

The design has a browser UI layer, local API/service layer, domain processing modules, and local persistence. Optional external model providers are dependencies of selected conversation or narrative paths; they are not the source of truth for OCR identifiers. The model and evidence tools provide suggestions or extracted candidates, while the user and investigator review the final content.

```text
Complainant browser
  |-- Static HTML/CSS/JS intake and manual form
  |-- Browser speech capture (where supported)
  |-- Evidence upload -----------------------------+
  |                                                 |
  v                                                 v
FastAPI service --> conversation / gap logic     OCR / PDF text
  |               --> TF-IDF + LinearSVC         regex entity extraction
  |               --> optional Gemini/Ollama       |
  |               --> optional local Whisper       v
  |                                            reconciliation
  |                                                 |
  +--> SQLite session/draft store                  v
  +--> case JSON / PDF files <-------------- confirmed draft
                        |
                        v
                 local investigator inbox
                        |
            separate investigator review UI
```

**Figure 1.** Current conceptual architecture derived from repository code. The Streamlit dashboard remains as a second interface path.

## 6.2 Overview of Project Modules

### 6.2.1 Data Collection and Intake Module

1. A complainant starts a session and gives an incident description through text, voice-derived text, or the manual form.
2. The intake logic extracts known details and evaluates what important information is missing.
3. The assistant asks a follow-up question based on the current gap state. The draft and conversation are persisted in SQLite during the session.
4. If a relevant item is requested or available, the complainant uploads an image or PDF. The file is stored locally, and the OCR path returns extracted text and candidate fields.
5. The interface presents candidate OCR data for review. Reconciliation compares the fields to the complainant’s description and marks agreement, OCR-only data, gaps, or conflicts.
6. The complainant corrects the transcript, extracted values, and narrative, then confirms the draft.
7. The application classifies the confirmed narrative as decision support and generates a structured case record and draft document.
8. The local investigator environment loads the submitted case, reviews the narrative and evidence, and updates its workflow status.

**Figure 2.** Complaint intake and review workflow.

### 6.2.2 Image Evidence Processing and OCR Module

OCR is performed through Tesseract for supported images; PDF pages are made available to the extraction path through PyMuPDF. Regular expressions and known-name lists identify candidate amount, UTR/RRN/transaction reference, phone number, date, time, UPI ID, email, masked ID, bank, payment app, or platform. Candidates carry a value and a heuristic confidence field. This confidence indicates extraction plausibility, not a calibrated probability that the OCR is correct.

The reconciliation module deliberately keeps typed and OCR sources separate. It reports:

- **Agreement:** the same relevant value appears in the typed account and evidence.
- **OCR-only:** evidence contains a candidate value not stated in the narrative.
- **Conflict:** the two sources differ, so the mismatch remains reviewable.
- **Gap:** neither source currently supplies the requested information.

The application must not treat a candidate OCR value as verified transaction truth. The complainant or investigator should inspect the original file, especially for long numeric identifiers and low-quality images.

**Figure 3.** Evidence reconciliation model.

```text
Typed narrative -----+---- same value? ----> agreement to review
                     |
                     +---- different value -> visible conflict
OCR candidate -------+---- only in image --> OCR-only candidate
                     +---- neither source -> information gap
```

### 6.2.3 Complaint Classification Module

The classifier loads `classifier.joblib`, `vectorizer.joblib`, and `label_encoder.joblib` from `models/`. It transforms complaint narrative using the saved vectorizer and obtains LinearSVC decision scores. The system ranks labels and returns the top alternatives. A bounded function of the top-versus-runner-up margin is displayed as confidence-like information. It is not a calibrated probability and must be interpreted with the stated caveat. The category taxonomy includes 21 labels in the saved model artifacts.

The sentiment/urgency component identifies potential urgency cues, including an emergency or “golden hour” state. It is a prioritization aid and cannot determine whether a transfer can be reversed or guarantee a financial recovery. The legal mapping module provides suggested references for review, not a legal opinion or final section selection.

### 6.2.4 Conversational Intake and Speech Module

The conversational intake stores user/assistant messages and draft fields in SQLite. A configured Gemini or Ollama provider can support follow-up conversation or narrative standardization. Code includes deterministic fallback behavior when a provider is unavailable or output fails validation. A model response can still be incomplete or unsuitable; validation and visible draft correction remain necessary.

The interface supports browser speech recognition where available. An optional backend path transcribes uploaded audio with Whisper when installed and configured. Recognized words and especially amounts, names, dates, and transaction IDs should be corrected before submission. The application provides text entry so the user can correct voice transcription or proceed without audio.

### 6.2.5 Persistence and Data Model Module

| Data | Storage location | Purpose / caution |
|---|---|---|
| Intake sessions, messages, draft fields | Local SQLite (`complaints.db`) | Supports session history and evolving draft; includes complainant-supplied content. |
| Case index / workflow data | Local SQLite (`case_index.db`) and case records | Supports local queue/search/status and should be protected as operational case data. |
| Structured submitted case | JSON files under `investigator_inbox/` | Includes case content and references to evidence; local runtime data, excluded from source control. |
| Uploaded evidence | Local `uploads/` and case-specific evidence storage | May contain sensitive personal and financial data; runtime storage only. |
| Generated draft reports | Local case file output / document endpoints | Draft output should be reviewed before use and is not an official filing. |
| Model artifacts | `models/` | Serialized classifier, vectorizer, label encoder, and benchmark metadata. |

The repository’s `.gitignore` excludes local databases, case folders, uploads, evidence, logs, and datasets. This is important because these locations may contain sensitive information. Developers should continue to verify staged paths before committing.

### 6.2.6 Case Output and Investigator Handoff Module

The investigator interface is designed as a separate operational view. It loads locally received cases, presents a queue and filters, opens a case detail view, and exposes complaint summary, complainant-provided fields, suspected identifiers, attached evidence, OCR/reconciliation results, suggested classification or legal information, and workflow actions. Imported case JSON is validated before it is saved. Workflow changes are written back into local case/index storage.

The investigator UI is only as complete as the case payload and local storage. Empty or incomplete records can exist, and imported records require validation. The current repository does not establish authenticated investigator identities, role-based permissions, secure remote access, an immutable audit log, or central backup. The application should be run only in an appropriately controlled environment until those controls are implemented.

## 6.3 User Interface

### 6.3.1 Citizen Intake Page

The standalone citizen interface presents guided conversation, a manual correction path, speech controls, and evidence upload when supporting documents can answer a question. Uploaded evidence can be reviewed alongside extracted candidate values. These interface elements allow a person to complete or correct details before submission. The older Streamlit interface remains in the repository as a separate path.

### 6.3.2 Investigator Dashboard

The investigator environment provides a distinct queue and case review experience. It is intended to show locally submitted records and make the review workflow independent from citizen intake. It should not be interpreted as a secured multi-user deployment because authentication and role-based authorization are not established by the repository.

### 6.3.3 Case Detail and History

The case detail view associates the complaint narrative, complainant details, evidence files, OCR/reconciliation output, classification suggestions, and workflow status with the selected case. Session history and case persistence use local storage described in Section 6.2.5. A reviewer must check original evidence where extracted values are material.

## 6.4 UML Diagrams

The following diagrams are conceptual views of current application boundaries. They are not generated from a formal UML model and should be updated if service routes or persistence behavior change.

**Figure 6.1.** System architecture and actors.

```text
Complainant -> Citizen UI -> FastAPI / domain modules -> Local session and case storage
                         -> OCR / classifier / optional speech and LLM services
Investigator -> Investigator UI -> Case API -> Local case records and evidence
```

**Figure 6.2.** Complaint intake and case review workflow.

```text
Start intake -> collect narrative -> extract gaps -> ask follow-up / accept evidence
    -> reconcile and edit -> confirm draft -> submit local case -> investigator review
```

**Figure 6.3.** Evidence reconciliation model.

```text
Typed narrative -----+---- same value? ----> agreement to review
                     +---- different value -> visible conflict
OCR candidate -------+---- only in image --> OCR-only candidate
                     +---- neither source -> information gap
```

## 6.5 Tools and Technology Used

### 6.5.1 Hardware Requirements

The project requires a general-purpose development or server computer and a browser client. No measured minimum CPU or memory configuration is available. The classifier does not require a GPU; an optional local speech model may need additional memory and processing capacity. See Table 5.1 for the hardware requirement summary.

### 6.5.2 Software and Libraries

The application uses Python, FastAPI, and a static browser frontend, while retaining Streamlit as a second interface. scikit-learn supplies the saved text-classification pipeline. Pillow, PyMuPDF, pytesseract, and the external Tesseract executable support evidence handling and OCR. ReportLab generates draft PDFs. Browser speech support, optional Whisper transcription, Gemini, and Ollama depend on the selected path and environment. See Table 5.2 for dependency roles.

## 6.6 Algorithm

1. Receive typed, manually entered, or speech-transcribed incident information and assign it to an intake session.
2. Parse the narrative and current draft fields to identify known facts and remaining information gaps.
3. If evidence is supplied, extract visible text and candidate entities using OCR and deterministic patterns.
4. Compare narrative and evidence candidates, preserving matches, OCR-only candidates, missing values, and conflicts as distinct outcomes.
5. Ask a follow-up tied to an unresolved information gap; update the draft from the complainant’s answer or confirmed evidence.
6. Classify the confirmed narrative and prepare a structured draft with source information and suggested review cues.
7. On submission, persist a case record and associate its evidence and generated draft outputs.
8. Present the case in the local investigator queue for human inspection and workflow updates.

The exact implementation is distributed across the API and domain modules. A model or OCR result must not override a confirmed user correction without making the discrepancy visible.

# Chapter 7. Results and Discussion

## 7.1 Experimental Setup

### 7.1.1 Dataset

The repository README describes a synthetic classification dataset with 10,500 generated examples across 21 categories. It documents a random split of 7,350 training, 1,575 validation, and 1,575 test examples, and a template-disjoint split of 7,149 training, 1,680 validation, and 1,671 test examples. These are generated records, not a sample of real complainant data. No human-reviewed real-world dataset or external deployment cohort is established in the repository.

| Split scheme | Training | Validation | Test | Dataset qualification |
|---|---:|---:|---:|---|
| Random split | 7,350 | 1,575 | 1,575 | Generated examples; vocabulary construction limits interpretation |
| Template-disjoint split | 7,149 | 1,680 | 1,671 | Generated examples; 801 templates kept within a single split |

### 7.1.2 Performance Parameters

The repository README reports macro-F1 of 1.0000 for both split schemes. Table 7.2 records this as repository-reported benchmark output, not an independently rerun experiment. Since category vocabularies are separable by construction, the figures do not establish real-world performance. The model uses TF-IDF and LinearSVC; macro precision, macro recall, per-class error analysis, calibration, and external validation should be reported only when measured and preserved with reproducible evaluation artifacts.

| Evaluation scheme | Repository-reported macro-F1 | Interpretation |
|---|---:|---|
| Random synthetic split | 1.0000 | Generated benchmark only; not real-world accuracy |
| Template-disjoint synthetic split | 1.0000 | Generated benchmark only; not real-world accuracy |

### 7.1.3 Efficiency Issues

No reproducible end-to-end latency, throughput, memory, or OCR throughput benchmark is supplied. Text classification and rule-based entity extraction are intended to be lightweight, but actual response time depends on hardware, image/PDF size, OCR installation, optional speech model, and external LLM provider. Efficiency claims should be added only after measuring a documented environment and representative fictional test inputs.

### 7.1.4 Implemented Behavior Observed in the Repository

| Area | Repository evidence | Interpretation |
|---|---|---|
| Separate frontend | `server.py` serves `static/index.html`; `static/app.js` and `static/style.css` implement the interface | A standalone web UI exists in addition to Streamlit. |
| Intake and persistence | `/api/chat`, `/agent/session/{session_id}/message`, `modules/database.py` | Session messages and draft fields are stored locally. |
| Evidence upload/OCR | `/api/upload_evidence`, `modules/ocr_extract.py`, `modules/reconcile.py` | File upload, candidate extraction, and source comparison are implemented. External Tesseract setup is required. |
| Voice | Browser capture code and transcription endpoints/modules | Voice is available through browser support and/or optional backend transcription; availability depends on environment. |
| Classification | `modules/classifier_service.py` and saved artifacts under `models/` | TF-IDF/LinearSVC predicts a category and returns alternatives plus a heuristic margin score. |
| Case submission/review | `/api/cases/submit`, `modules/investigator_store.py`, case routes | Local records can be placed in the investigator inbox and reviewed. |
| Data safety | `.gitignore` excludes local evidence, database, logs, and case folders | Runtime records are intended to stay out of source control. |

These are code-level findings and do not certify every UI path, installation, test, or deployment scenario. This report does not claim that a full end-to-end test suite passed. The project’s test files should be run on the target machine with all required packages and local services available, and results should be recorded before submission.

The displayed margin-derived confidence is not calibrated. A future evaluation should measure calibration and category-wise precision/recall on representative, consented, de-identified data, with a pre-registered evaluation protocol and clear human oversight.

## 7.2 Software Testing

The repository contains test files, but a full test-suite execution result is not available as evidence for this report. The test status below is therefore intentionally not marked as passed. Before academic submission, execute the existing tests in the target environment and record versions, output, and failures.

### 7.2.1 Test Cases and Test Results

| Test area | Expected check | Result in this report |
|---|---|---|
| API and session flow | Start session, send messages, persist draft state | Not run for this report |
| OCR and evidence upload | Accept supported file, extract candidate fields, preserve source | Not run for this report |
| Conversation gap handling | Ask relevant questions and avoid repeating answered fields | Not run for this report |
| Case submission | Create a case associated with its own evidence | Not run for this report |
| Investigator queue | Show submitted case and persist review status changes | Not run for this report |
| JSON import and validation | Reject invalid payloads and associate valid cases correctly | Not run for this report |
| Failure paths | Handle absent OCR, ASR, Gemini, or Ollama dependencies clearly | Not run for this report |

## 7.3 Summary

The code-level review indicates that the repository has developed beyond a standalone classifier into an integrated complaint-intake and investigator-review prototype. It connects narrative collection, speech-to-text options, OCR candidate extraction, source reconciliation, category suggestions, editable draft preparation, and local case storage. These observations describe repository capabilities and do not certify that every deployment or UI flow works correctly.

### 7.3.1 Result Analysis and Discussion

#### Strengths

- The workflow combines narrative, manual entry, OCR candidates, and investigator review instead of treating classification as the whole product.
- OCR identifiers are extracted with deterministic patterns and can be traced to evidence text.
- The reconciliation design retains conflicts and separates evidence-only fields from the complainant’s own description.
- Draft editing and manual intake provide a correction path when voice or LLM output is wrong.
- Local case persistence allows a submitted complaint to appear in an investigator queue without relying on a static demo list.
- The repository documents the limitations of its synthetic classification benchmark rather than presenting that score as real-world accuracy.

#### Limitations and Risks

| Risk | Why it matters | Practical next step |
|---|---|---|
| Generated dataset bias | Artificial vocabulary and templates can inflate benchmark scores | Build a reviewed, consented, de-identified evaluation set; report per-class metrics and error analysis. |
| OCR / ASR errors | A wrong digit in an amount or reference can materially mislead review | Show source excerpts, let users correct every field, and retain original evidence for human inspection. |
| LLM variability | Questions or summaries may be repetitive, incomplete, or unsupported | Keep questions state-driven; validate extracted facts; regression-test multi-turn scenarios. |
| Uncalibrated classifier score | UI may make heuristic margins look like a probability | Rename/explain the score and calibrate it only with representative labeled data. |
| Local storage exposure | Case files and evidence may contain personal/financial data | Add authentication, role controls, encryption, retention/deletion policy, access logs, and secure backups before deployment. |
| No official integration | Local case creation does not notify authorities or banks | Clearly tell users where official filing must occur; pursue only approved integrations. |
| Suggested law and urgency | Could be misread as legal or recovery advice | Keep as non-binding prompts with review labels and official-source verification. |
| Two frontends | Streamlit and standalone UI can diverge in behavior | Maintain a feature parity checklist and automate the same core workflows across interfaces. |

## 7.4 Validation Still Required

Before a formal demonstration or deployment, validate: clean installation; OCR with representative fictional images; voice capture and correction in supported browsers; repeated multi-turn Q&A without duplicate questions; upload prompt timing; text/OCR conflict display; case submission and investigator queue persistence; import validation; workflow updates; draft generation; failure behavior for missing Tesseract, Whisper, Gemini, and Ollama; and safeguards preventing runtime case data from entering Git. Record software versions, device/browser, test data source, expected result, actual result, and any defects. Test with fictional records only.

# Chapter 8. Conclusion and Future Work

## 8.1 Conclusions

The current project has expanded from a complaint classifier into a local cybercrime intake and investigator-review prototype. It connects conversational/manual reporting, voice-derived text, OCR-based candidate extraction, evidence reconciliation, category suggestions, draft generation, and local case storage. The separate investigator interface provides a path to review submitted records and update their workflow. The implementation’s most important design principle is that OCR, ASR, and model output remain reviewable suggestions rather than verified facts.

The project is suitable for continued academic development and controlled demonstration. It is not an official complaint-filing service or production-ready case-management system. The synthetic classification benchmark does not establish real-world accuracy, and local storage does not supply production security controls. Those limits must remain explicit in demonstrations and documentation.

## 8.2 Future Work

1. Improve the dataset using a legally and ethically approved, consented, de-identified process; establish a human-reviewed gold set and evaluate out of distribution.
2. Calibrate or remove margin-derived confidence and provide per-class error analysis.
3. Add source highlighting, confidence/provenance displays, and explicit confirmation for each OCR/ASR field.
4. Expand conversation regression tests to verify one meaningful question at a time, real-time field updates, no repeated answered questions, and OCR-aware gap suppression.
5. Add secure authentication, authorization, encryption at rest, configurable retention/deletion, immutable audit events, backup and recovery, and deployment threat modeling.
6. Align Streamlit and standalone frontend capabilities with a shared workflow checklist and cross-interface acceptance tests.
7. Improve accessibility, multilingual/code-switching support, keyboard navigation, and low-bandwidth behavior.
8. Validate statutory references against current official sources and keep them explicitly non-binding until qualified review.
9. Define an approved deployment and official-filing integration only with institutional and government authorization.

## 8.3 Applications

Potential applications include academic demonstrations of complaint-intake workflows, controlled usability studies with fictional scenarios, and internal prototyping of evidence-to-case organization. The current implementation is not established as an official reporting channel, live police case-management tool, bank investigation system, or production service for real victim data.

# Annexure A. References

[1] A. Joulin, E. Grave, P. Bojanowski, and T. Mikolov, “Bag of Tricks for Efficient Text Classification,” *Proceedings of the 15th Conference of the European Chapter of the Association for Computational Linguistics*, 2017; arXiv:1607.01759. https://arxiv.org/abs/1607.01759

[2] A. Radford et al., “Robust Speech Recognition via Large-Scale Weak Supervision,” *Proceedings of the 40th International Conference on Machine Learning*, PMLR 202, 2023; arXiv:2212.04356. https://arxiv.org/abs/2212.04356

[3] scikit-learn developers, “LinearSVC,” scikit-learn API documentation. https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html

[4] R. Smith, “An Overview of the Tesseract OCR Engine,” *Ninth International Conference on Document Analysis and Recognition (ICDAR 2007)*, vol. 2, pp. 629-633, 2007. https://tesseract-ocr.github.io/docs/tesseracticdar2007.pdf

[5] OpenAI, “Whisper: Robust Speech Recognition via Large-Scale Weak Supervision,” project repository and model usage documentation. https://github.com/openai/whisper

[6] K. K. Wagh Institute of Engineering Education & Research, Department of Computer Engineering, “Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP,” Phase I research seminar report, PID 18, 23 April 2026. Used for team, guide, department, and institutional metadata; technical design in this updated report is based on the current repository.

[7] “new report.pdf,” user-provided sample report for a different project. Used only as a reference for report organization and front-matter/chapter conventions; its project content has not been reused.

[8] Project repository reviewed for this report: `server.py`, `dashboard.py`, `static/`, `modules/`, `models/`, `tests/`, `README.md`, `README2.md`, and `.gitignore`, snapshot reviewed 24 October 2026.

# Annexure B. Plagiarism Report

Attach the institute-approved plagiarism or similarity report here if required. No verified report was supplied with the project materials, so no similarity score or clearance is claimed.

# Annexure C. Paper Published (if any)

Attach the published paper, acceptance letter, or citation here if applicable. No publication evidence was supplied for this report.

# Annexure D. Sponsorship Detail (if any)

Add verified sponsor name, support type, amount or in-kind contribution, and approval details here if applicable. No sponsorship details were supplied.
