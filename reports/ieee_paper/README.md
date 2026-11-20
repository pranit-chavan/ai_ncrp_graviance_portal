# IEEE Conference Paper

This folder contains an IEEE conference-style LaTeX draft describing the current repository as an academic prototype.

## Build

Compile `main.tex` with an IEEEtran-capable LaTeX distribution from this folder. A typical sequence is:

```text
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

## Before submission

- Replace the author email placeholder with approved contact details.
- Confirm author order, institute naming, and the target conference's page limit and template rules.
- Verify all references and adjust access dates if needed.
- The classifier metrics are reported from `reports/s3_evaluation/s3_metrics.json`; they describe a generated test set and are not real-world accuracy estimates.
- The generated-corpus caveat is intentionally stated in the abstract, methods, results, and conclusion.
