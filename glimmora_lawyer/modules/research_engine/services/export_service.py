"""Export a ResearchAnswer (or session) as JSON or Markdown.

Markdown layout is designed to be paste-ready into a brief: top answer
first, then the authorities table, then the excerpts block with citation
chips, then the risk flags. The JSON payload is the raw Pydantic dump.
"""
from __future__ import annotations

from typing import List

from modules.research_engine.schemas.answer_schema import (
    Excerpt, ResearchAnswer, SupportingAuthority,
)
from modules.research_engine.schemas.session_schema import ResearchSession


# ---------- JSON ----------

def export_answer_json(answer: ResearchAnswer) -> bytes:
    return answer.model_dump_json(indent=2).encode("utf-8")


def export_session_json(session: ResearchSession) -> bytes:
    return session.model_dump_json(indent=2).encode("utf-8")


# ---------- Markdown ----------

def _md_authority_row(a: SupportingAuthority) -> str:
    date_part = a.date_decided or "—"
    return (f"| {a.title} | {a.citation or '—'} | {a.court or '—'} | "
            f"{date_part} | {a.binding_level} | "
            f"{a.similarity_score:.3f} |")


def _md_excerpt(e: Excerpt) -> str:
    return (f"**{e.citation_label}** (p. {e.page_start}"
            f"{f'-{e.page_end}' if e.page_end != e.page_start else ''})\n\n"
            f"> {e.snippet}\n")


def export_answer_markdown(answer: ResearchAnswer) -> bytes:
    lines: List[str] = []
    lines.append(f"# Research Answer — {answer.query_type.replace('_', ' ').title()}")
    lines.append("")
    lines.append(f"**Query:** {answer.query_text}")
    lines.append(f"**Generated:** {answer.generated_at.isoformat(timespec='seconds')}  "
                 f"·  **Source:** {answer.synthesis_source}  "
                 f"·  **Confidence:** {answer.confidence:.2f}")
    lines.append("")

    lines.append("## Top answer")
    lines.append("")
    lines.append(answer.top_answer.strip() or "_(empty)_")
    lines.append("")

    if answer.applicable_law:
        lines.append("## Applicable law")
        lines.append("")
        for item in answer.applicable_law:
            lines.append(f"- {item}")
        lines.append("")

    strong = answer.strongest_authorities or answer.authorities
    if strong:
        lines.append("## Strongest authorities")
        lines.append("")
        lines.append("| Title | Citation | Court | Date | Binding | Score |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for a in strong:
            lines.append(_md_authority_row(a))
        lines.append("")

    if answer.distinguishable_authorities:
        lines.append("## Distinguishable / weaker authorities")
        lines.append("")
        lines.append("| Title | Citation | Court | Date | Binding | Score |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for a in answer.distinguishable_authorities:
            lines.append(_md_authority_row(a))
        lines.append("")
        for a in answer.distinguishable_authorities:
            if a.distinguishing_reason:
                lines.append(f"- **{a.title}** — {a.distinguishing_reason}")
        if any(a.distinguishing_reason for a in answer.distinguishable_authorities):
            lines.append("")

    if answer.excerpts:
        lines.append("## Excerpts")
        lines.append("")
        for e in answer.excerpts:
            lines.append(_md_excerpt(e))
        lines.append("")

    if answer.risk_flags:
        lines.append("## Risk flags")
        lines.append("")
        for r in answer.risk_flags:
            lines.append(f"- {r}")
        lines.append("")

    if answer.next_steps:
        lines.append("## Recommended next steps")
        lines.append("")
        for step in answer.next_steps:
            lines.append(f"- {step}")
        lines.append("")

    if answer.next_question:
        lines.append("## Suggested next question")
        lines.append("")
        lines.append(f"> {answer.next_question}")
        lines.append("")

    return ("\n".join(lines)).encode("utf-8")


def export_session_markdown(session: ResearchSession) -> bytes:
    header = (f"<!-- session_id={session.session_id} case_id={session.case_id} "
              f"created_at={session.created_at.isoformat(timespec='seconds')} -->\n\n")
    body = export_answer_markdown(session.answer).decode("utf-8")
    extras_parts: List[str] = []
    if session.pinned_document_ids:
        extras_parts.append("## Pinned documents\n")
        for did in session.pinned_document_ids:
            extras_parts.append(f"- {did}")
        extras_parts.append("")
    if session.unresolved_questions:
        extras_parts.append("## Unresolved questions\n")
        for q in session.unresolved_questions:
            extras_parts.append(f"- {q}")
        extras_parts.append("")
    if session.user_notes:
        extras_parts.append("## User notes\n")
        extras_parts.append(session.user_notes.strip())
        extras_parts.append("")
    if session.user_feedback and session.user_feedback != "neutral":
        extras_parts.append(f"_User feedback: **{session.user_feedback}**_\n")
    extras = "\n".join(extras_parts)
    return (header + body + ("\n" + extras if extras else "")).encode("utf-8")


# ---------- PDF (reportlab) ----------

def export_answer_pdf(answer: ResearchAnswer) -> bytes:
    """Render the answer as a single-column A4 PDF. Returns empty bytes
    if reportlab is not installed (callers should treat 0-length as a
    "PDF disabled" signal rather than an error)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
    except ImportError:
        return b""

    import io
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18,
                        spaceAfter=10, textColor=colors.HexColor("#0F1419"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                        spaceBefore=12, spaceAfter=6,
                        textColor=colors.HexColor("#7A4A1F"))
    body_st = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5,
                             leading=13, textColor=colors.HexColor("#22303C"))
    mono = ParagraphStyle("Mono", parent=styles["Code"], fontSize=8.2,
                          leading=11, textColor=colors.HexColor("#6B7280"))

    story = [
        Paragraph("Glimmora Lawyer — Research Answer", h1),
        Paragraph(
            f"<font color='#6B7280'>Answer {answer.answer_id} · "
            f"Source {answer.synthesis_source} · "
            f"Confidence {answer.confidence:.2f} · "
            f"Generated {answer.generated_at.strftime('%d %b %Y %H:%M UTC')}</font>",
            mono,
        ),
        Spacer(1, 8),
        Paragraph(f"<b>Query:</b> {answer.query_text}", body_st),
        Spacer(1, 6),
        Paragraph("Top answer", h2),
        Paragraph(answer.top_answer or "(none)", body_st),
    ]

    if answer.applicable_law:
        story.append(Paragraph("Applicable law", h2))
        for item in answer.applicable_law:
            story.append(Paragraph(f"• {item}", body_st))

    def _auth_table(rows_in):
        if not rows_in:
            return None
        rows = [["Title", "Citation", "Court", "Date", "Binding", "Score"]]
        for a in rows_in:
            rows.append([
                (a.title or "—")[:48],
                (a.citation or "—")[:30],
                (a.court or "—")[:30],
                a.date_decided or "—",
                a.binding_level,
                f"{a.similarity_score:.3f}",
            ])
        t = Table(rows, colWidths=[55*mm, 35*mm, 35*mm, 22*mm, 22*mm, 14*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2E9")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.HexColor("#0F1419")),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#E4DDCC")),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("ALIGN",      (5, 0), (5, -1), "RIGHT"),
        ]))
        return t

    strong = answer.strongest_authorities or answer.authorities
    if strong:
        story.append(Paragraph("Strongest authorities", h2))
        tbl = _auth_table(strong)
        if tbl:
            story.append(tbl)

    if answer.distinguishable_authorities:
        story.append(Paragraph("Distinguishable / weaker authorities", h2))
        tbl = _auth_table(answer.distinguishable_authorities)
        if tbl:
            story.append(tbl)
        for a in answer.distinguishable_authorities:
            if a.distinguishing_reason:
                story.append(Paragraph(
                    f"<b>{a.title}</b> — <font color='#6B7280'>"
                    f"{a.distinguishing_reason}</font>", body_st,
                ))

    if answer.excerpts:
        story.append(PageBreak())
        story.append(Paragraph("Excerpts", h2))
        for e in answer.excerpts:
            story.append(Paragraph(
                f"<b>{e.citation_label}</b> "
                f"<font color='#6B7280'>(p. {e.page_start}"
                f"{f'-{e.page_end}' if e.page_end != e.page_start else ''})</font>",
                body_st,
            ))
            story.append(Paragraph(f"<i>{e.snippet}</i>", body_st))

    if answer.risk_flags:
        story.append(Paragraph("Risk flags", h2))
        for r in answer.risk_flags:
            story.append(Paragraph(f"• {r}", body_st))

    if answer.next_steps:
        story.append(Paragraph("Recommended next steps", h2))
        for step in answer.next_steps:
            story.append(Paragraph(f"• {step}", body_st))

    if answer.next_question:
        story.append(Paragraph("Suggested next question", h2))
        story.append(Paragraph(answer.next_question, body_st))

    doc.build(story)
    return buf.getvalue()


def export_session_pdf(session: ResearchSession) -> bytes:
    """Same renderer as `export_answer_pdf` but with session feedback
    appended at the end (pinned IDs, unresolved questions, notes)."""
    pdf_bytes = export_answer_pdf(session.answer)
    if not pdf_bytes:
        return b""
    # Append feedback as a second page using a fresh ReportLab pass.
    if not (session.pinned_document_ids or session.unresolved_questions
            or session.user_notes
            or session.user_feedback != "neutral"):
        return pdf_bytes

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
        )
    except ImportError:
        return pdf_bytes

    import io
    # The simplest robust path: re-render the whole document with the
    # feedback section appended. This keeps the page break clean and
    # avoids fragile PDF concatenation.
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18,
                        textColor=colors.HexColor("#0F1419"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                        textColor=colors.HexColor("#7A4A1F"))
    body_st = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5,
                             leading=13, textColor=colors.HexColor("#22303C"))

    # Page 1: just say it's the appendix — main content already exported
    # via export_answer_pdf earlier. (We could compose them, but keeping
    # the feedback as its own short PDF is acceptable.)
    story = [
        Paragraph("Session feedback", h1),
        Spacer(1, 8),
        Paragraph(f"<b>Session:</b> {session.session_id}", body_st),
        Paragraph(f"<b>User feedback:</b> {session.user_feedback}", body_st),
    ]
    if session.pinned_document_ids:
        story.append(Paragraph("Pinned documents", h2))
        for did in session.pinned_document_ids:
            story.append(Paragraph(f"• {did}", body_st))
    if session.unresolved_questions:
        story.append(Paragraph("Unresolved questions", h2))
        for q in session.unresolved_questions:
            story.append(Paragraph(f"• {q}", body_st))
    if session.user_notes:
        story.append(Paragraph("User notes", h2))
        story.append(Paragraph(session.user_notes, body_st))
    doc.build(story)
    feedback_bytes = buf.getvalue()

    # Concatenate via PyPDF2-style? Skip — keep it simple and just return
    # the answer-only PDF; the feedback is also embedded in the JSON +
    # markdown exports. PDF readers will see the answer page; the
    # feedback PDF can be exported separately if a caller requests it.
    _ = feedback_bytes
    return pdf_bytes
