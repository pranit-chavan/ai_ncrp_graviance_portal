"""Create a classic, Overleaf-ready LaTeX project from the report Markdown."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "cyberassist_report.md"
PROJECT = ROOT / "overleaf_project"
MAIN = PROJECT / "main.tex"
ROOT_TEX = ROOT / "cyberassist_report.tex"
ROOT_LOGO = ROOT / "kkwagh_logo.png"
LOGO_SOURCE = ROOT / "kkwagh_logo.png"
LOGO = PROJECT / "kkwagh_logo.png"
PACKAGE = ROOT / "cyberassist_overleaf_project.zip"

TABLE_CAPTIONS = {
    "Included in the current repository": "Implemented capabilities and boundaries",
    "ID": "Functional requirements",
    "Data": "Data persistence overview",
    "Area": "Repository-level evaluation findings",
    "Risk": "Risk and mitigation summary",
}


def escape_tex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "₹": "INR ",
        "—": "---", "–": "--", "’": "'", "“": "``", "”": "''",
        "→": "to", "←": "from", "≥": ">=", "≤": "<=", "×": "x",
    }
    return "".join(replacements.get(char, char) for char in value)


def inline(value: str) -> str:
    held: list[str] = []

    def keep(latex: str) -> str:
        held.append(latex)
        return f"@@LATEX{len(held) - 1}@@"

    value = value.replace("\\n", "\\\\")
    value = re.sub(r"`([^`]+)`", lambda m: keep(r"\texttt{" + escape_tex(m.group(1)) + "}"), value)
    value = re.sub(r"\*\*(.+?)\*\*", lambda m: keep(r"\textbf{" + escape_tex(m.group(1)) + "}"), value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", lambda m: keep(r"\emph{" + escape_tex(m.group(1)) + "}"), value)
    value = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", lambda m: keep(r"\href{" + m.group(2) + "}{" + escape_tex(m.group(1)) + "}"), value)
    value = escape_tex(value)
    for index, latex in enumerate(held):
        value = value.replace(f"@@LATEX{index}@@", latex)
    return value


def table_rows(lines: list[str], start: int):
    rows = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        row = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
        if not all(re.fullmatch(r"[-: ]+", cell or " ") for cell in row):
            rows.append(row)
        i += 1
    return rows, i


def latex_table(rows: list[list[str]]) -> str:
    cols = max(len(row) for row in rows)
    width = 0.95 / cols
    spec = "".join(r"|>{\RaggedRight\arraybackslash}p{" + f"{width:.3f}" + r"\textwidth}" for _ in range(cols)) + "|"
    output = [r"\begin{longtable}{" + spec + "}", r"\hline"]
    for number, row in enumerate(rows):
        row += [""] * (cols - len(row))
        cells = [inline(cell.replace(r"\\n", " ")) for cell in row]
        if number == 0:
            cells = [r"\textbf{" + cell + "}" for cell in cells]
        output.append(" & ".join(cells) + r" \\\hline")
    output.append(r"\end{longtable}")
    return "\n".join(output)


PREAMBLE = r"""\documentclass[12pt,a4paper,oneside]{report}
\usepackage[a4paper,left=25mm,right=25mm,top=23mm,bottom=22mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{mathptmx}
\usepackage{graphicx,array,longtable,tabularx,booktabs,ragged2e,caption,xurl,hyperref,enumitem,fancyhdr,titlesec,setspace}
\hypersetup{colorlinks=true,linkcolor=black,urlcolor=blue,citecolor=black}
\setlength{\parindent}{1cm}
\setlength{\parskip}{0pt}
\setstretch{1.08}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{2}
\setlist[enumerate]{leftmargin=1.1cm,itemsep=2pt,topsep=3pt}
\setlist[itemize]{leftmargin=1.1cm,itemsep=2pt,topsep=3pt}
\titleformat{\chapter}[hang]{\normalfont\Large\bfseries}{\thechapter}{0.7em}{}
\titlespacing*{\chapter}{0pt}{-6pt}{15pt}
\titleformat{\section}{\normalfont\large\bfseries}{\thesection}{0.7em}{}
\titleformat{\subsection}{\normalfont\normalsize\bfseries}{\thesubsection}{0.7em}{}
\newcolumntype{L}[1]{>{\RaggedRight\arraybackslash}p{#1}}
\fancypagestyle{front}{\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}}
\fancypagestyle{main}{\fancyhf{}\fancyfoot[L]{KKWIEER, Department of Computer Engineering, 2025}\fancyfoot[R]{Page \thepage}\renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0.4pt}}
\captionsetup{font=small,labelfont=bf,justification=raggedright,singlelinecheck=false}
\begin{document}
"""


def cover() -> str:
    names = [
        ("Pranit Chavan", "T231301016"),
        ("Harshal Dahiphalkar", "T231301021"),
        ("Yash Kanhe", "T231301060"),
        ("Chaitanya Mali", "T231301074"),
    ]
    member_rows = "\n".join(r"\textbf{" + escape_tex(name) + r"} & Exam No: " + exam + r" \\" for name, exam in names)
    return r"""\begin{titlepage}
\thispagestyle{empty}
\centering
\vspace*{8mm}
{\large A PROJECT REPORT ON\par}
\vspace{8mm}
{\Large\bfseries Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP\par}
\vspace{4mm}
{\large\bfseries Cybercrime Complaint Analysis and Investigator Review System\par}
\vspace{12mm}
Submitted towards the\par
Partial Fulfilment of the Requirements of\par
\vspace{8mm}
{\large\bfseries BACHELOR OF ENGINEERING\par}
{\large\bfseries IN\par}
{\large\bfseries Computer Engineering\par}
\vspace{6mm}
{\large By\par}
\vspace{2mm}
\begin{tabular}{p{0.45\textwidth}p{0.43\textwidth}}
""" + member_rows + r"""
\end{tabular}
\vspace{5mm}

{\large Under the guidance of\par}
\vspace{2mm}
{\large\bfseries Prof. I. Priyadarshini\par}
\vspace{5mm}
\includegraphics[width=2.5cm]{kkwagh_logo.png}\par
\vspace{3mm}
Department of Computer Engineering\par
K. K. Wagh Institute of Engineering Education \& Research\par
Hirabai Haridas Vidyanagari, Amrutdham, Panchavati, Nashik 422003\par
(An Autonomous Institute affiliated to Savitribai Phule Pune University)\par
\vspace{3mm}
Academic Year 2025--2026
\end{titlepage}
"""


def certificate() -> str:
    students = [
        ("Pranit Chavan", "T231301016"), ("Harshal Dahiphalkar", "T231301021"),
        ("Yash Kanhe", "T231301060"), ("Chaitanya Mali", "T231301074"),
    ]
    table = "\n".join(r"\textbf{" + escape_tex(name) + "} & Exam No: " + exam + r" \\" for name, exam in students)
    return r"""\clearpage
\thispagestyle{empty}
\begin{center}
{\Large\bfseries CERTIFICATE\par}
\vspace{8mm}
\textit{This is to certify that the project report entitled}\par
\vspace{2mm}
{\large\bfseries Intelligent Cybercrime Complaint Analysis and Category Classification System using NLP\par}
{\normalsize Cybercrime Complaint Analysis and Investigator Review System\par}
\textit{being submitted by}\par
\vspace{3mm}
\begin{tabular}{p{0.48\textwidth}p{0.38\textwidth}}
""" + table + r"""
\end{tabular}
\end{center}

\vspace{6mm}
is a record of project work carried out under the guidance of Prof. I. Priyadarshini in partial fulfilment of the requirements for the degree of Bachelor of Engineering in Computer Engineering during academic year 2025--2026.

This updated report documents work completed beyond the Phase I submission and is submitted for academic review. Final certificate wording and signatures must be verified and approved by the department.

\vspace{16mm}
\begin{tabularx}{\textwidth}{X X}
\textbf{Prof. I. Priyadarshini} & \hfill \textbf{Dr. Snehal Kamalapur} \\
Internal Guide & \hfill Head of Department, Computer Engineering \\
Signature: \rule{45mm}{0.4pt} & \hfill Signature: \rule{45mm}{0.4pt} \\
Date: \rule{35mm}{0.4pt} & \hfill Date: \rule{35mm}{0.4pt} \\
\end{tabularx}

\vspace{13mm}
\textbf{External Examiner}\par
Signature: \rule{45mm}{0.4pt}\hspace{15mm}Date: \rule{30mm}{0.4pt}\par
Place: Nashik
"""


def section_body(lines: list[str]) -> str:
    output: list[str] = []
    i = 0
    first_chapter = False
    table_index = 0
    list_env = None
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(escape_tex(lines[i]))
                i += 1
            output.append(r"\begin{quote}\ttfamily\footnotesize " + r"\\".join(code) + r"\end{quote}")
            i += 1
            continue
        if line.startswith("|"):
            if list_env:
                output.append(r"\end{" + list_env + "}")
                list_env = None
            rows, i = table_rows(lines, i)
            if rows:
                if first_chapter:
                    header = rows[0][0]
                    caption = TABLE_CAPTIONS.get(header)
                    if caption:
                        table_index += 1
                        output.append(r"\captionof{table}{" + escape_tex(caption) + "}")
                output.append(latex_table(rows))
                output.append(r"\vspace{2mm}")
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            if title.startswith("Chapter "):
                chapter_title = title.split(". ", 1)[1] if ". " in title else title
                output.append(r"\clearpage\chapter{" + escape_tex(chapter_title) + "}")
                first_chapter = True
            elif title.startswith("Appendix "):
                output.append(r"\clearpage\chapter*{" + escape_tex(title) + r"}\addcontentsline{toc}{chapter}{" + escape_tex(title) + "}")
            elif title == "References":
                output.append(r"\clearpage\chapter*{References}\addcontentsline{toc}{chapter}{References}")
            i += 1
            continue
        if line.startswith("## ") or line.startswith("### "):
            if list_env:
                output.append(r"\end{" + list_env + "}")
                list_env = None
            match = re.match(r"#{2,3}\s+(?:\d+(?:\.\d+)*\s+)?(.*)", line)
            title = escape_tex(match.group(1) if match else line.lstrip("# "))
            command = r"\section" if line.startswith("## ") else r"\subsection"
            output.append(command + "{" + title + "}")
            i += 1
            continue
        if line.startswith("- ") or re.match(r"\d+\. ", line):
            ordered = bool(re.match(r"\d+\. ", line))
            env = "enumerate" if ordered else "itemize"
            if list_env != env:
                if list_env:
                    output.append(r"\end{" + list_env + "}")
                output.append(r"\begin{" + env + "}")
                list_env = env
            item = re.sub(r"^(- |\d+\. )", "", line)
            output.append(r"\item " + inline(item))
            i += 1
            continue
        if list_env:
            output.append(r"\end{" + list_env + "}")
            list_env = None
        if line.startswith("> "):
            output.append(r"\begin{quote}\itshape " + inline(line[2:]) + r"\end{quote}")
            i += 1
            continue
        paragraph = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "> ", "- ", "```")) and not re.match(r"\d+\. ", lines[i]):
            paragraph.append(lines[i].strip())
            i += 1
        text = " ".join(paragraph)
        caption_match = re.match(r"\*\*Figure\s+\d+\.\*\*\s*(.*)", text)
        if caption_match:
            output.append(r"\captionof{figure}{" + inline(caption_match.group(1)) + "}")
        else:
            output.append(inline(text) + r"\par\medskip")
    if list_env:
        output.append(r"\end{" + list_env + "}")
    return "\n".join(output)


def build() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    output = [PREAMBLE, cover(), certificate(), r"\clearpage\pagenumbering{Roman}\pagestyle{front}",
              r"\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\thepage}\renewcommand{\headrulewidth}{0pt}}"]

    def content_after(title: str, until: str) -> list[str]:
        start = next(i for i, line in enumerate(lines) if line.strip() == f"# {title}") + 1
        end = next(i for i in range(start, len(lines)) if lines[i].strip() == f"# {until}")
        return lines[start:end]

    output += [r"\clearpage\chapter*{Abstract}\addcontentsline{toc}{chapter}{Abstract}", section_body(content_after("Abstract", "Acknowledgement"))]
    output += [r"\clearpage\chapter*{Acknowledgement}\addcontentsline{toc}{chapter}{Acknowledgement}", section_body(content_after("Acknowledgement", "Contents")),
               r"\vfill\begin{flushright}Pranit Chavan\\Harshal Dahiphalkar\\Yash Kanhe\\Chaitanya Mali\end{flushright}"]
    output += [r"\clearpage\tableofcontents", r"\clearpage\addcontentsline{toc}{chapter}{List of Figures}\listoffigures",
               r"\clearpage\addcontentsline{toc}{chapter}{List of Tables}\listoftables",
               r"\clearpage\pagenumbering{arabic}\pagestyle{main}",
               r"\fancypagestyle{plain}{\fancyhf{}\fancyfoot[L]{KKWIEER, Department of Computer Engineering, 2025}\fancyfoot[R]{Page \thepage}\renewcommand{\headrulewidth}{0pt}\renewcommand{\footrulewidth}{0.4pt}}"]
    start = next(i for i, line in enumerate(lines) if line.startswith("# Chapter 1."))
    end = len(lines)
    output.append(section_body(lines[start:end]))
    output.append(r"\end{document}")

    PROJECT.mkdir(parents=True, exist_ok=True)
    if not LOGO_SOURCE.exists():
        fallback_logo = Path(r"C:\Users\hp\Downloads\newlogo-removebg-preview.png")
        if not fallback_logo.exists():
            raise FileNotFoundError(f"Institute logo not found: {LOGO_SOURCE}")
        shutil.copyfile(fallback_logo, LOGO_SOURCE)
    if LOGO_SOURCE.resolve() != LOGO.resolve():
        shutil.copyfile(LOGO_SOURCE, LOGO)
    if LOGO_SOURCE.resolve() != ROOT_LOGO.resolve():
        shutil.copyfile(LOGO_SOURCE, ROOT_LOGO)
    MAIN.write_text("\n\n".join(output), encoding="utf-8")
    shutil.copyfile(MAIN, ROOT_TEX)
    with zipfile.ZipFile(PACKAGE, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(MAIN, "main.tex")
        archive.write(LOGO, "kkwagh_logo.png")
    print(f"Created {MAIN}")
    print(f"Created {PACKAGE}")


if __name__ == "__main__":
    build()
