"""Export the FinalReport to JSON, plain text, and PDF (reportlab)."""
from __future__ import annotations

import io
import json
from typing import List

from loguru import logger

from modules.evidence_vault.schemas.final_report_schema import FinalReport
from modules.evidence_vault.utils.chart_utils import score_label

log = logger.bind(scope="evidence.export")


# ---------- JSON ----------

def export_json(report: FinalReport) -> bytes:
    return report.model_dump_json(indent=2).encode("utf-8")


# ---------- Plain-text executive brief ----------

def export_text(report: FinalReport) -> bytes:
    lines: List[str] = []
    lines.append("GLIMMORA LAWYER — FINAL CASE INTELLIGENCE")
    lines.append("=" * 60)
    lines.append(f"Report ID : {report.report_id}")
    lines.append(f"Case ID   : {report.case_id}")
    lines.append(f"Generated : {report.generated_at.isoformat(timespec='seconds')}")
    lines.append("")

    lines.append("SCORECARD")
    lines.append("-" * 60)
    for key, val in report.scores.model_dump().items():
        lines.append(f"  {score_label(key):<36s} {val:>3} / 100")
    lines.append("")

    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 60)
    lines.append(report.executive_summary.strip() or "(no summary)")
    lines.append("")

    lines.append(f"STRONGEST ISSUE : {report.strongest_issue or '—'}")
    lines.append(f"WEAKEST ISSUE   : {report.weakest_issue or '—'}")
    lines.append("")

    if report.strongest_points:
        lines.append("STRONGEST EVIDENCE POINTS")
        lines.append("-" * 60)
        for p in report.strongest_points:
            lines.append(f"  · {p.title}  {p.citation_label}")
            lines.append(f"    “{p.snippet[:180]}”")
        lines.append("")

    if report.weakest_points:
        lines.append("RISKY / WEAK EVIDENCE POINTS")
        lines.append("-" * 60)
        for p in report.weakest_points:
            lines.append(f"  · {p.title}  {p.citation_label}")
            lines.append(f"    “{p.snippet[:180]}”")
        lines.append("")

    if report.contradiction_summary:
        lines.append("CONTRADICTIONS")
        lines.append("-" * 60)
        for c in report.contradiction_summary:
            lines.append(f"  [{c.severity}] {c.summary}")
            lines.append(f"    {c.explanation}")
        lines.append("")

    if report.missing_evidence_summary:
        lines.append("MISSING EVIDENCE")
        lines.append("-" * 60)
        for m in report.missing_evidence_summary:
            lines.append(f"  [{m.severity}] {m.category}")
            lines.append(f"    Why : {m.why_it_matters}")
            lines.append(f"    Next: {m.recommendation}")
        lines.append("")

    if report.recommendations:
        lines.append("RECOMMENDED NEXT ACTIONS")
        lines.append("-" * 60)
        for r in report.recommendations:
            lines.append(f"  [{r.priority.upper():<8s}] {r.title}  ({r.action_type})")
            lines.append(f"    {r.description}")
        lines.append("")

    if report.source_map:
        lines.append("SOURCE MAP")
        lines.append("-" * 60)
        for s in report.source_map:
            lines.append(f"  {s.label}")
            lines.append(f"    {s.reason_used}")
        lines.append("")

    lines.append("FINAL CONCLUSION")
    lines.append("-" * 60)
    lines.append(report.final_conclusion.strip() or "(no conclusion)")
    lines.append("")

    return "\n".join(lines).encode("utf-8")


# ---------- PDF (reportlab) ----------

def export_pdf(report: FinalReport) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak,
        )
    except ImportError:
        log.warning("reportlab not installed — PDF export disabled.")
        return b""

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18,
                        spaceAfter=10, textColor=colors.HexColor("#0F1419"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5,
                        spaceBefore=12, spaceAfter=6,
                        textColor=colors.HexColor("#7A4A1F"))
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5,
                          leading=13, textColor=colors.HexColor("#22303C"))
    mono = ParagraphStyle("Mono", parent=styles["Code"], fontSize=8.2,
                          leading=11, textColor=colors.HexColor("#6B7280"))

    story = [
        Paragraph("Glimmora Lawyer — Final Case Intelligence", h1),
        Paragraph(
            f"<font color='#6B7280'>Report {report.report_id} · "
            f"Case {report.case_id} · "
            f"Generated {report.generated_at.strftime('%d %b %Y %H:%M UTC')}</font>",
            mono,
        ),
        Spacer(1, 8),
        Paragraph("Scorecard", h2),
    ]

    # Score table
    rows = [["Score", "Value", "Direction"]]
    higher_better = {
        "evidence_strength_score", "completeness_score",
        "timeline_integrity_score", "legal_basis_strength_score",
        "readiness_score", "pitch_success_estimate",
    }
    for key, val in report.scores.model_dump().items():
        direction = "higher better" if key in higher_better else "lower better"
        rows.append([score_label(key), f"{val} / 100", direction])
    tbl = Table(rows, colWidths=[78 * mm, 28 * mm, 34 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F6F2E9")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.HexColor("#0F1419")),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#E4DDCC")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("ALIGN",      (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(tbl)

    story.append(Paragraph("Executive summary", h2))
    story.append(Paragraph(report.executive_summary or "(none)", body))

    story.append(Paragraph("Strongest issue", h2))
    story.append(Paragraph(report.strongest_issue or "—", body))
    story.append(Paragraph("Weakest issue", h2))
    story.append(Paragraph(report.weakest_issue or "—", body))

    if report.contradiction_summary:
        story.append(Paragraph("Contradictions", h2))
        for c in report.contradiction_summary:
            story.append(Paragraph(
                f"<b>[{c.severity}]</b> {c.summary}<br/>"
                f"<font color='#6B7280'>{c.explanation}</font>", body,
            ))

    if report.missing_evidence_summary:
        story.append(Paragraph("Missing evidence", h2))
        for m in report.missing_evidence_summary:
            story.append(Paragraph(
                f"<b>[{m.severity}]</b> {m.category}<br/>"
                f"<i>Why:</i> {m.why_it_matters}<br/>"
                f"<i>Next:</i> {m.recommendation}", body,
            ))

    if report.recommendations:
        story.append(Paragraph("Recommended next actions", h2))
        for r in report.recommendations:
            story.append(Paragraph(
                f"<b>[{r.priority.upper()}]</b> {r.title} "
                f"<font color='#7A4A1F'>({r.action_type})</font><br/>"
                f"{r.description}", body,
            ))

    if report.source_map:
        story.append(PageBreak())
        story.append(Paragraph("Source map", h2))
        for s in report.source_map:
            story.append(Paragraph(
                f"<b>{s.label}</b><br/>"
                f"<font color='#6B7280'>{s.reason_used}</font>", body,
            ))

    story.append(Paragraph("Final conclusion", h2))
    story.append(Paragraph(report.final_conclusion or "(none)", body))

    doc.build(story)
    return buf.getvalue()
