"""Build the editable LaTeX source and review PDF from cyberassist_report.md."""

from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "cyberassist_report.md"
PDF_OUT = ROOT / "cyberassist_report.pdf"
TEX_OUT = ROOT / "cyberassist_report.tex"

NAVY = colors.HexColor("#132B45")
BLUE = colors.HexColor("#2457A7")
TEAL = colors.HexColor("#137C8B")
PALE = colors.HexColor("#EEF3F8")
INK = colors.HexColor("#202B36")
MUTED = colors.HexColor("#5B6978")


def inline_markup(text: str) -> str:
    text = text.replace("@@BR@@", "\x00")
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<link href='\2' color='#2457A7'>\1</link>", text)
    return text.replace("  \\\n", "<br/>").replace("\\n", "<br/>").replace("\x00", "<br/>")


def clean_table_line(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def tex_escape(text: str) -> str:
    swaps = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        "₹": "INR ", "—": "---", "–": "--", "’": "'", "“": "``", "”": "''",
    }
    return "".join(swaps.get(ch, ch) for ch in text)


def tex_inline(text: str) -> str:
    text = tex_escape(text)
    text = re.sub(r"`([^`]+)`", r"\\texttt{\1}", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\\emph{\1}", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\\href{\2}{\1}", text)
    return text.replace("  \\\n", r"\\ ").replace("\\n", r"\\ ")


def build_tex(lines: list[str]) -> None:
    out = [
        r"\documentclass[12pt,a4paper,oneside]{report}",
        r"\usepackage[margin=25mm,headheight=15pt]{geometry}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{lmodern,microtype,booktabs,longtable,array,xcolor,hyperref,fancyhdr,enumitem}",
        r"\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}",
        r"\definecolor{reportnavy}{HTML}{132B45}",
        r"\pagestyle{fancy}\fancyhf{}\fancyhead[L]{Cybercrime Complaint Analysis and Investigator Review System}\fancyfoot[C]{\thepage}",
        r"\setlist[itemize]{leftmargin=1.7em,itemsep=2pt,topsep=3pt}",
        r"\setlength{\parskip}{5pt}\setlength{\parindent}{0pt}",
        r"\begin{document}",
    ]
    i = 0
    first_heading = True
    tex_titlepage = False
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i].replace("_", r"\_").replace("%", r"\%"))
                i += 1
            out += [r"\begin{quote}\ttfamily\small", *[tex_escape(x) for x in code], r"\end{quote}"]
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = clean_table_line(lines[i])
                if not all(re.fullmatch(r"[-: ]+", c or " ") for c in row):
                    rows.append(row)
                i += 1
            if rows:
                cols = max(map(len, rows))
                width = r"p{0.94\textwidth}" if cols == 1 else "".join([r"p{%.3f\textwidth}" % (0.94 / cols)] * cols)
                env = "tabular" if tex_titlepage else "longtable"
                out.append(r"\begin{" + env + "}{" + width + "}")
                if not tex_titlepage:
                    out.append(r"\toprule")
                for ri, row in enumerate(rows):
                    row += [""] * (cols - len(row))
                    cells = [tex_inline(x.replace(r"\\n", " ")) for x in row]
                    if ri == 0:
                        cells = [r"\textbf{" + x + "}" for x in cells]
                    out.append(" & ".join(cells) + r" \\")
                    if ri == 0 and not tex_titlepage:
                        out.append(r"\midrule")
                if not tex_titlepage:
                    out.append(r"\bottomrule")
                out.append(r"\end{" + env + "}")
            continue
        if line.startswith("# "):
            title = line[2:].strip()
            if first_heading:
                out += [r"\begin{titlepage}\centering\vspace*{25mm}",
                        r"{\Huge\bfseries\color{reportnavy} " + tex_inline(title) + r"\par}",
                        r"\vspace{12mm}"]
                tex_titlepage = True
                first_heading = False
                i += 1
                continue
            if tex_titlepage:
                out.append(r"\end{titlepage}")
                tex_titlepage = False
            if title in {"Certificate", "Abstract", "Acknowledgement", "Contents", "List of Figures", "List of Tables"}:
                out.append(r"\clearpage\chapter*{" + tex_inline(title) + "}")
                if title == "Contents": out.append(r"\tableofcontents")
                elif title == "List of Figures": out.append(r"\listoffigures")
                elif title == "List of Tables": out.append(r"\listoftables")
            elif title.startswith("Chapter "):
                out.append(r"\clearpage\chapter{" + tex_inline(title.split(". ", 1)[1] if ". " in title else title) + "}")
            elif title.startswith("Appendix "):
                out.append(r"\clearpage\chapter{" + tex_inline(title) + "}")
            else:
                out.append(r"\clearpage\chapter*{" + tex_inline(title) + r"}\addcontentsline{toc}{chapter}{" + tex_inline(title) + "}")
            i += 1
            continue
        if line.startswith("## "):
            if tex_titlepage:
                out.append(r"{\Large\bfseries " + tex_inline(line[3:].strip()) + r"\par}\vspace{7mm}")
            else:
                out.append(r"\section{" + tex_inline(line[3:].strip()) + "}")
            i += 1
            continue
        if line.startswith("### "):
            out.append(r"\subsection{" + tex_inline(line[4:].strip()) + "}")
            i += 1
            continue
        if line.startswith("> "):
            out.append(r"\begin{quote}\itshape " + tex_inline(line[2:].strip()) + r"\end{quote}")
            i += 1
            continue
        if line.startswith("- ") or re.match(r"\d+\. ", line):
            ordered = bool(re.match(r"\d+\. ", line))
            env = "enumerate" if ordered else "itemize"
            out.append(r"\begin{" + env + "}")
            while i < len(lines) and (lines[i].startswith("- ") or re.match(r"\d+\. ", lines[i])):
                item = re.sub(r"^(- |\d+\. )", "", lines[i].strip())
                out.append(r"\item " + tex_inline(item))
                i += 1
            out.append(r"\end{" + env + "}")
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "> ", "- ", "```")) and not re.match(r"\d+\. ", lines[i]):
            para.append(lines[i].strip())
            i += 1
        text = " ".join(para)
        out.append(tex_inline(text) + "\n")
    if tex_titlepage:
        out.append(r"\end{titlepage}")
    out.append(r"\end{document}")
    TEX_OUT.write_text("\n".join(out), encoding="utf-8")


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: Path, styles):
        super().__init__(str(filename), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm,
                         topMargin=22 * mm, bottomMargin=19 * mm, title="Cybercrime Complaint Analysis and Investigator Review System")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=self.draw_page))
        self.styles = styles

    def draw_page(self, canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setStrokeColor(colors.HexColor("#D8E0E9"))
            canvas.line(22 * mm, A4[1] - 15 * mm, A4[0] - 22 * mm, A4[1] - 15 * mm)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(22 * mm, A4[1] - 11.5 * mm, "CYBERASSIST  |  UPDATED PROJECT REPORT")
            canvas.drawRightString(A4[0] - 22 * mm, 10 * mm, str(doc.page))
        canvas.restoreState()

def styles():
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle("CoverTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=31, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10),
        "Subtitle": ParagraphStyle("CoverSub", parent=base["Heading2"], fontName="Helvetica", fontSize=14, leading=19, textColor=TEAL, alignment=TA_CENTER, spaceAfter=10),
        "Chapter": ParagraphStyle("Chapter", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=24, textColor=NAVY, spaceBefore=3, spaceAfter=12, keepWithNext=True),
        "Section": ParagraphStyle("Section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=9, spaceAfter=5, keepWithNext=True),
        "Subsection": ParagraphStyle("Subsection", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.8, leading=14, textColor=TEAL, spaceBefore=7, spaceAfter=4, keepWithNext=True),
        "Body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6),
        "Small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=8.4, leading=11.5, textColor=INK, spaceAfter=4),
        "Bullet": ParagraphStyle("Bullet", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=12.3, leftIndent=13, firstLineIndent=-8, textColor=INK, spaceAfter=3),
        "Quote": ParagraphStyle("Quote", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=9, leading=13, leftIndent=10, rightIndent=10, borderColor=TEAL, borderWidth=2, borderPadding=7, backColor=PALE, textColor=NAVY, spaceBefore=8, spaceAfter=10),
        "Code": ParagraphStyle("Code", parent=base["Code"], fontName="Courier", fontSize=7.4, leading=10, backColor=PALE, borderColor=colors.HexColor("#D8E0E9"), borderWidth=.4, borderPadding=8, spaceBefore=4, spaceAfter=8),
        "TOC": ParagraphStyle("TOC", parent=base["BodyText"], fontName="Helvetica", fontSize=9, leading=13, leftIndent=12, firstLineIndent=-12, textColor=INK),
        "TOC1": ParagraphStyle("TOC1", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=15, leftIndent=0, textColor=NAVY),
    }


def add_table(rows: list[list[str]], width: float, sty):
    max_cols = max(len(row) for row in rows)
    data = []
    header_style = ParagraphStyle("TableHeader", parent=sty["Small"], textColor=colors.white, fontName="Helvetica-Bold")
    for row_index, row in enumerate(rows):
        row = row + [""] * (max_cols - len(row))
        row_style = header_style if row_index == 0 else sty["Small"]
        data.append([Paragraph(inline_markup(cell.replace(r"\\n", " ")), row_style) for cell in row])
    col_widths = [width / max_cols] * max_cols
    if max_cols == 2:
        col_widths = [width * .25, width * .75] if len(rows) < 5 else [width * .2, width * .8]
    if max_cols == 3:
        col_widths = [width * .3, width * .3, width * .4]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D3DCE6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_pdf(lines: list[str]):
    sty = styles()
    doc = ReportDoc(PDF_OUT, sty)
    story = []
    i = 0
    first_heading = True
    code_mode = False
    code_lines = []
    front_title_mode = True
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            if not code_mode:
                code_mode = True
                code_lines = []
            else:
                code_mode = False
                escaped = "<br/>".join(x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;") for x in code_lines)
                story.append(Paragraph(escaped, sty["Code"]))
            i += 1
            continue
        if code_mode:
            code_lines.append(line)
            i += 1
            continue
        if not line.strip():
            i += 1
            continue
        if line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = clean_table_line(lines[i])
                if not all(re.fullmatch(r"[-: ]+", c or " ") for c in row):
                    rows.append(row)
                i += 1
            if rows:
                story.append(add_table(rows, doc.width, sty))
                story.append(Spacer(1, 5))
            continue
        if line.startswith("# "):
            heading = line[2:].strip()
            if first_heading:
                story += [Spacer(1, 35 * mm), Paragraph(inline_markup(heading), sty["Title"]), Spacer(1, 3 * mm)]
                first_heading = False
            else:
                if heading in {"Certificate", "Abstract", "Acknowledgement", "Contents", "List of Figures", "List of Tables", "References"} or heading.startswith("Chapter ") or heading.startswith("Appendix "):
                    story.append(PageBreak())
                if heading == "Contents":
                    story.append(Paragraph("Contents", sty["Chapter"]))
                elif heading in {"List of Figures", "List of Tables"}:
                    story.append(Paragraph(inline_markup(heading), sty["Chapter"]))
                elif heading.startswith("Chapter "):
                    title = heading.split(". ", 1)[1] if ". " in heading else heading
                    story.append(Paragraph(inline_markup(title), sty["Chapter"]))
                elif heading.startswith("Appendix "):
                    story.append(Paragraph(inline_markup(heading), sty["Chapter"]))
                else:
                    story.append(Paragraph(inline_markup(heading), sty["Chapter"]))
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(inline_markup(line[3:].strip()), sty["Section"]))
            i += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(inline_markup(line[4:].strip()), sty["Subsection"]))
            i += 1
            continue
        if line.startswith("> "):
            story.append(Paragraph(inline_markup(line[2:].strip()), sty["Quote"]))
            i += 1
            continue
        if line.startswith("- ") or re.match(r"\d+\. ", line):
            while i < len(lines) and (lines[i].startswith("- ") or re.match(r"\d+\. ", lines[i])):
                bullet = re.sub(r"^(- |\d+\. )", "", lines[i].strip())
                marker = "&#8226;" if lines[i].startswith("- ") else re.match(r"(\d+)\.", lines[i]).group(1) + "."
                story.append(Paragraph(f"{marker}&nbsp;&nbsp;{inline_markup(bullet)}", sty["Bullet"]))
                i += 1
            story.append(Spacer(1, 3))
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|", "> ", "- ", "```")) and not re.match(r"\d+\. ", lines[i]):
            separator = "@@BR@@" if lines[i - 1].endswith("  ") else " "
            para.append(separator + lines[i].strip())
            i += 1
        story.append(Paragraph(inline_markup(" ".join(para)), sty["Body"]))
    doc.build(story)


def main():
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    build_tex(lines)
    build_pdf(lines)
    print(f"Created {PDF_OUT}")
    print(f"Created {TEX_OUT}")


if __name__ == "__main__":
    main()
