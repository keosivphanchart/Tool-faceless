"""Assembles the analyzer's output dict into a formatted PDF report."""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.charts import health_distribution_chart, resource_usage_chart

SEVERITY_TEXT_COLOR = {
    "healthy": colors.HexColor("#2e9e5b"),
    "warning": colors.HexColor("#e0a72e"),
    "critical": colors.HexColor("#d64545"),
}


def _metric(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}%"


def build_pdf(report: dict, title: str = "Infrastructure Report") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    h1 = styles["Title"]
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], spaceBefore=14, spaceAfter=6)
    body = styles["BodyText"]

    summary = report["summary"]
    story = [
        Paragraph(title, h1),
        Paragraph(datetime.now(timezone.utc).strftime("Generated %Y-%m-%d %H:%M UTC"), body),
        Spacer(1, 12),
        Paragraph("Infrastructure Summary", h2),
        Table(
            [
                ["Total Servers", "Healthy", "Warning", "Critical"],
                [
                    str(summary["total_servers"]),
                    str(summary["healthy"]),
                    str(summary["warning"]),
                    str(summary["critical"]),
                ],
            ],
            colWidths=[1.6 * inch] * 4,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]
            ),
        ),
        Spacer(1, 16),
        Image(io.BytesIO(health_distribution_chart(summary)), width=3 * inch, height=3 * inch),
    ]

    if report["critical_issues"]:
        story.append(Paragraph("Critical Issues", h2))
        for issue in report["critical_issues"]:
            story.append(Paragraph(f"- {issue}", ParagraphStyle("crit", parent=body, textColor=SEVERITY_TEXT_COLOR["critical"])))

    if report["warning_issues"]:
        story.append(Paragraph("Warnings", h2))
        for issue in report["warning_issues"]:
            story.append(Paragraph(f"- {issue}", ParagraphStyle("warn", parent=body, textColor=SEVERITY_TEXT_COLOR["warning"])))

    if report["recommendations"]:
        story.append(Paragraph("Recommended Actions", h2))
        for rec in report["recommendations"]:
            story.append(Paragraph(f"- {rec}", body))

    if report["servers"]:
        story.append(Paragraph("Per-Server Detail", h2))
        rows = [["Server", "Status", "CPU", "RAM", "Disk", "Severity"]]
        for s in report["servers"]:
            rows.append([s["name"], s["status"], _metric(s["cpu"]), _metric(s["ram"]), _metric(s["disk"]), s["severity"]])
        table = Table(rows, colWidths=[1.4 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch, 0.9 * inch])
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ]
        for i, s in enumerate(report["servers"], start=1):
            table_style.append(("TEXTCOLOR", (5, i), (5, i), SEVERITY_TEXT_COLOR[s["severity"]]))
        table.setStyle(TableStyle(table_style))
        story.append(table)
        story.append(Spacer(1, 16))
        story.append(Image(io.BytesIO(resource_usage_chart(report["servers"])), width=6.5 * inch, height=4.3 * inch))

    doc.build(story)
    return buf.getvalue()
