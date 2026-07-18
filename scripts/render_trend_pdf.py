#!/usr/bin/env python3
"""Render a knowledge/daily_logs/*.md trend-scout log to a printable PDF.

Usage: python3 scripts/render_trend_pdf.py knowledge/daily_logs/2026-07-18.md
Output: knowledge/daily_logs/pdf/2026-07-18.pdf
"""
import re
import sys
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def inline_markup(text):
    return BOLD_RE.sub(r"<b>\1</b>", text)


def build_story(md_text, styles):
    story = []
    bullet_buffer = []

    def flush_bullets():
        if bullet_buffer:
            items = [ListItem(Paragraph(inline_markup(b), styles["Body"])) for b in bullet_buffer]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18))
            story.append(Spacer(1, 8))
            bullet_buffer.clear()

    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            flush_bullets()
            continue
        if line.startswith("# "):
            flush_bullets()
            story.append(Paragraph(inline_markup(line[2:]), styles["Title"]))
            story.append(Spacer(1, 12))
        elif line.startswith("## "):
            flush_bullets()
            story.append(Paragraph(inline_markup(line[3:]), styles["Heading2"]))
            story.append(Spacer(1, 8))
        elif line.startswith("- ") or line.startswith("  "):
            bullet_buffer.append(line.lstrip("- ").strip())
        else:
            flush_bullets()
            story.append(Paragraph(inline_markup(line), styles["Body"]))
            story.append(Spacer(1, 6))
    flush_bullets()
    return story


def render(md_path: Path, out_path: Path):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Body", parent=styles["Normal"], fontSize=10.5, leading=15))

    story = build_story(md_path.read_text(), styles)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        title=md_path.stem,
    )
    doc.build(story)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: render_trend_pdf.py <path/to/daily_log.md>")
        sys.exit(1)

    md_path = Path(sys.argv[1])
    out_path = md_path.parent / "pdf" / (md_path.stem + ".pdf")
    render(md_path, out_path)
    print(f"Wrote {out_path}")
