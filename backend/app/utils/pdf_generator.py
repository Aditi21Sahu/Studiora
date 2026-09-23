import os
import io
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_notes_pdf(note_dict: dict) -> io.BytesIO:
    """
    Generate an elegant PDF document from structured study notes using ReportLab.
    Returns a BytesIO stream ready for HTTP StreamingResponse or FileResponse.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Brand Colors: Primary Purple #5B2BE0, Text #29234A, Background #FAF9FF, Border #E5E0F5
    primary_color = colors.HexColor("#5B2BE0")
    secondary_text = colors.HexColor("#716B89")
    dark_text = colors.HexColor("#29234A")
    light_purple_bg = colors.HexColor("#EEE9FF")
    border_color = colors.HexColor("#E5E0F5")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=primary_color,
        spaceAfter=6
    )

    brand_badge_style = ParagraphStyle(
        'BrandBadge',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=primary_color,
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_text,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletPoint',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=dark_text,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    term_style = ParagraphStyle(
        'TermDef',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=dark_text,
        spaceAfter=4
    )

    story = []

    # Studiora Header
    story.append(Paragraph("STUDIORA &bull; AI STUDY NOTES", brand_badge_style))
    story.append(Paragraph(note_dict.get("title", "Study Notes"), title_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=4, spaceAfter=14))

    # Executive Summary Box
    summary_text = note_dict.get("summary", "")
    if summary_text:
        story.append(Paragraph("Executive Summary", h2_style))
        story.append(Paragraph(summary_text, body_style))
        story.append(Spacer(1, 10))

    # Key Takeaways
    key_points = note_dict.get("key_points", [])
    if isinstance(key_points, str):
        try:
            key_points = json.loads(key_points)
        except Exception:
            key_points = [key_points]

    if key_points:
        story.append(Paragraph("Key Takeaways", h2_style))
        for point in key_points:
            story.append(Paragraph(f"&bull; {point}", bullet_style))
        story.append(Spacer(1, 10))

    # Detailed Sections
    sections = note_dict.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except Exception:
            sections = []

    if sections:
        story.append(Paragraph("Detailed Study Sections", h2_style))
        for sec in sections:
            sec_title = sec.get("title", "Section")
            sec_content = sec.get("content", "")
            bullets = sec.get("bullet_points", [])
            examples = sec.get("examples", [])

            sub_heading_style = ParagraphStyle(
                'SubH3',
                parent=styles['Heading3'],
                fontName='Helvetica-Bold',
                fontSize=11,
                leading=14,
                textColor=dark_text,
                spaceBefore=8,
                spaceAfter=4
            )
            story.append(Paragraph(sec_title, sub_heading_style))
            if sec_content:
                story.append(Paragraph(sec_content, body_style))
            for b in bullets:
                story.append(Paragraph(f"&ndash; {b}", bullet_style))
            for ex in examples:
                ex_style = ParagraphStyle('Example', parent=body_style, textColor=colors.HexColor("#4320B8"), leftIndent=12)
                story.append(Paragraph(f"<i>Example:</i> {ex}", ex_style))
            story.append(Spacer(1, 6))

    # Important Terms
    terms = note_dict.get("important_terms", [])
    if isinstance(terms, str):
        try:
            terms = json.loads(terms)
        except Exception:
            terms = []

    if terms:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Important Vocabulary & Definitions", h2_style))
        for t in terms:
            term_name = t.get("term", "")
            term_def = t.get("definition", "")
            story.append(Paragraph(f"<b>{term_name}</b>: {term_def}", term_style))
        story.append(Spacer(1, 8))

    # Revision Points
    revision = note_dict.get("revision_points", [])
    if isinstance(revision, str):
        try:
            revision = json.loads(revision)
        except Exception:
            revision = []

    if revision:
        story.append(Paragraph("Rapid Revision Checklist", h2_style))
        for r in revision:
            story.append(Paragraph(f"&#9633; {r}", bullet_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_notes_txt(note_dict: dict) -> str:
    """Generate clean, human-readable plain text notes."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"STUDIORA - AI STUDY NOTES")
    lines.append(f"Title: {note_dict.get('title', 'Study Notes')}")
    lines.append("=" * 60)
    lines.append("")

    summary = note_dict.get("summary", "")
    if summary:
        lines.append("EXECUTIVE SUMMARY:")
        lines.append(summary)
        lines.append("")

    key_points = note_dict.get("key_points", [])
    if isinstance(key_points, str):
        try:
            key_points = json.loads(key_points)
        except Exception:
            key_points = [key_points]
    if key_points:
        lines.append("KEY TAKEAWAYS:")
        for kp in key_points:
            lines.append(f"  * {kp}")
        lines.append("")

    sections = note_dict.get("sections", [])
    if isinstance(sections, str):
        try:
            sections = json.loads(sections)
        except Exception:
            sections = []
    if sections:
        lines.append("STUDY SECTIONS:")
        for sec in sections:
            lines.append(f"\n--- {sec.get('title', 'Section')} ---")
            if sec.get("content"):
                lines.append(sec.get("content"))
            for b in sec.get("bullet_points", []):
                lines.append(f"  - {b}")
            for ex in sec.get("examples", []):
                lines.append(f"  Example: {ex}")
        lines.append("")

    terms = note_dict.get("important_terms", [])
    if isinstance(terms, str):
        try:
            terms = json.loads(terms)
        except Exception:
            terms = []
    if terms:
        lines.append("IMPORTANT VOCABULARY & CONCEPTS:")
        for t in terms:
            lines.append(f"  * {t.get('term')}: {t.get('definition')}")
        lines.append("")

    revision = note_dict.get("revision_points", [])
    if isinstance(revision, str):
        try:
            revision = json.loads(revision)
        except Exception:
            revision = []
    if revision:
        lines.append("RAPID REVISION POINTS:")
        for r in revision:
            lines.append(f"  [ ] {r}")
        lines.append("")

    return "\n".join(lines)
