# pdf_export.py
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import re


def save_text_as_pdf(text: str, out_path: Path) -> None:
    """Render plain/markdown-ish text (headings, bullets) into a paginated PDF."""
    styles = getSampleStyleSheet()

    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceAfter=6,
    )

    story = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # blank line -> small spacer
        if not line:
            story.append(Spacer(1, 6))
            i += 1
            continue

        # headings (#, ##, ###)
        if line.startswith("### "):
            story.append(Paragraph(line[4:].strip(), h2))
            i += 1
            continue
        if line.startswith("## "):
            story.append(Paragraph(line[3:].strip(), h2))
            i += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:].strip(), h1))
            i += 1
            continue

        # bullets: group consecutive "- " lines
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(ListItem(Paragraph(lines[i][2:].strip(), body), leftIndent=12))
                i += 1
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18))
            story.append(Spacer(1, 6))
            continue

        # normal paragraph: gather until blank line
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            para.append(lines[i].rstrip())
            i += 1
        story.append(Paragraph(" ".join(para), body))
        story.append(Spacer(1, 6))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=out_path.stem,
    )
    doc.build(story)

