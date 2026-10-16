# Module D — Legal Mapping Engine

Maps a predicted NCRP sub-category to the applicable legal provisions.

## Files

    legal_mapping.json   the mapping data, 21 sub-categories
    legal_mapping.py     the lookup engine

## Use it

    from modules.legal_mapping import map_sections, format_sections

    result = map_sections("AePS Fraud")
    result = map_sections("Cyber Bullying / Stalking / Sexting", complainant_age=16)
    print(format_sections(result))

From the command line:

    python modules/legal_mapping.py                                    self-test
    python modules/legal_mapping.py "AePS Fraud"                       one category
    python modules/legal_mapping.py "Cyber Bullying / Stalking / Sexting" 16

## Why a lookup and not a model

The sub-category to section mapping is fixed by statute, not learned from data.
A lookup is auditable — an officer can see exactly why a section was proposed —
and it cannot hallucinate a provision that does not exist. Using a model here
would add risk and remove explainability for no gain.

## The conditional rule

POCSO applies where the complainant is a minor. That is read from the
complainant_age FIELD of the structured form, never inferred from the narrative.
A model guessing age from prose would be unreliable in exactly the cases where
being wrong matters most.

Three outcomes are handled explicitly:

    age >= 18        rule not applicable
    age < 18         POCSO sections added, marked APPLIED with the reason
    age not supplied NOT EVALUATED, with an instruction to confirm the age

The third case matters: silence is not the same as "does not apply".

## Coverage

All 21 classifier labels are mapped. Verified — no unmapped labels, no unused
mappings. Every category has at least one IT Act or BNS section.

## Sources

Each mapping was taken from the Legal: line of that sub-category's scenarios.md,
which was in turn drawn from the source article set for that category. BNS 2023
replaced the IPC from 1 July 2024; IPC equivalents are retained because older
FIRs cite them.

## Output goes to

  Module E — the legal sections block of the case file
  Module F — displayed to the investigator alongside the classification

## Maintenance

If the classifier's label set changes, run the self-test. It reports any
category with no sections and lists coverage per category. The label match
against dataset/splits/ should be re-verified after any relabelling.


---

# Module E — Case File Generator

Assembles the output of every module into an investigator-ready case file.

## Files

    case_file.py     the generator
    ../case_files/   output directory (JSON + PDF per case)

## Use it

    from modules.case_file import build_case_file, write_pdf, write_json, format_text

    case = build_case_file(
        complainant={"name": "...", "age": 34, "phone": "...", "city": "..."},
        narrative="...",              # Module A
        sub_category="AePS Fraud",    # Module B
        confidence=0.94,              # Module B
        entities={"amount": "Rs. 40,000"},   # Module C
        attachments=["screenshot.png"],
    )
    write_json(case)
    write_pdf(case)
    print(format_text(case))

Demo, builds three cases end to end:

    python modules/case_file.py

## Graceful degradation

Every upstream module is optional. If Module A or C has not run, the case file is
still produced and those sections read "NOT AVAILABLE - Module A did not run".

This is deliberate. In the field OCR fails on poor screenshots and many complaints
arrive with no attachments at all. A pipeline that collapses when one component is
missing is useless. The demo includes a degraded case to show this.

## Confidence bands

    >= 0.90   HIGH     reliable, officer confirmation still required
    >= 0.70   MEDIUM   review the narrative before accepting
    <  0.70   LOW      manual classification recommended
    none      NOT SUPPLIED

The case file always records that the classification is machine-generated and
requires confirmation. The system assists an officer; it does not decide.

## Suggested first actions

Categories are grouped into financial, account, content and institutional. Each
group carries the actions an officer should take first — for financial cases that
means freezing beneficiary accounts within the golden hour, because after that
the money is gone.

If the POCSO rule could not be evaluated because age was missing, "Confirm the
complainant's age" is inserted as the FIRST action.

## Output

    JSON   machine readable, goes to the database and Module F
    PDF    what an investigating officer opens

Both are written to case_files/ named by reference number.


---

# Module A — AI Assistant (intake and narrative standardisation)

Turns a complaint as a real person writes it into the formal English register the
classifier was trained on.

## Why it exists

The classifier was trained on formal generated English. A real complainant writes
"paise gaye 40000 koi otp nahi aaya". Those share almost no vocabulary. Module A
closes that gap.

This is measurable. Running the same complaint through the pipeline:

    raw Hinglish, Module A unavailable  -> Card/SIM Swap Fraud   (WRONG)
    standardised narrative              -> AePS Fraud            (correct)

## Use it

    from modules.ai_assistant import standardise

    r = standardise("paise gaye 40000 koi otp nahi aaya",
                    entities={"transaction_date": "12 August 2026"})
    r["ok"]         guard passed
    r["narrative"]  the standardised text
    r["issues"]     what the guard found, if it failed

    python modules/ai_assistant.py --check     guard self-test, no model needed
    python modules/ai_assistant.py             demo over messy sample complaints
    python modules/ai_assistant.py --text "..."

Defaults to Ollama with qwen2.5:7b. --provider gemini or anthropic also work.

## The hallucination guard

An LLM asked to "write a proper complaint" will invent plausible detail. In a
police system that is not cosmetic — a fabricated detail becomes part of a case
file an officer acts on.

So every narrative is checked before it is returned. Rejected if it:

    introduces a number not present in the input
    drops an amount that WAS in the input
    introduces a year not in the input
    introduces a mechanism (OTP, QR, SIM swap, ransomware...) not in the input
    falls outside 200–1500 characters
    returns commentary instead of a narrative

On rejection the instruction is tightened and the model is asked again, twice.
If all attempts fail the pipeline continues on the raw text and records why.

Self-test: 5/5 guard behaviours correct.

## Design decisions

PROMPTED, not trained. The task is rewriting, which instruction models already do
well. Training here would add cost and remove the ability to change behaviour by
editing text.

Temperature 0.2. This is transcription, not creative writing.

---

# Pipeline

    python pipeline.py --demo
    python pipeline.py --text "paise gaye 40000 koi otp nahi aaya"

Runs raw complaint -> C -> A -> B -> D -> E and writes a case file.

Every stage degrades gracefully. With Ollama stopped, the demo still produces a
complete case file — it simply classifies on raw text, marks confidence LOW, and
records that Module A was unavailable.

## Confidence

A linear SVM has no probability. It has a MARGIN: how far the top class sits
ahead of the runner-up. That gap is the honest signal — wide means the decision
was clear, narrow means two categories were competing. Mapped to 0–1 for banding.

    "...unauthorised debit, no OTP, card retained"  -> AePS Fraud       65%
    "...registration fee, training fee, no job"     -> Online Job Fraud 100%
    "Money was taken from my account."              -> AePS Fraud       50%  LOW

The third is correctly uncertain. Vague input should not produce a confident
answer, and the LOW band routes it to manual classification.
