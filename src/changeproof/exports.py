from html import escape
from io import BytesIO

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .demo import DemoAnalysis

ARTIFACT_FIELDS = {
    "impact-report.json": "impact_report_json",
    "discovery-query.sql": "discovery_query_sql",
    "proposed-fixes.sql": "proposed_fixes_sql",
    "validation-queries.sql": "validation_queries_sql",
    "rollback.sql": "rollback_sql",
    "changeproof.sarif": "sarif_json",
}

ARTIFACT_EXPORTS = [
    {
        "name": "Impact report",
        "artifact_name": "impact-report.json",
        "description": "Complete evidence",
    },
    {
        "name": "Discovery query",
        "artifact_name": "discovery-query.sql",
        "description": "SQL Server read-only scan",
    },
    {
        "name": "Proposed fixes",
        "artifact_name": "proposed-fixes.sql",
        "description": "Reviewable SQL drafts",
    },
    {
        "name": "Validation queries",
        "artifact_name": "validation-queries.sql",
        "description": "Conversion and null checks",
    },
    {
        "name": "Rollback runbook",
        "artifact_name": "rollback.sql",
        "description": "Owner-gated recovery steps",
    },
    {
        "name": "SARIF results",
        "artifact_name": "changeproof.sarif",
        "description": "CI-compatible findings",
    },
]


def artifact_text(analysis: DemoAnalysis, artifact_name: str) -> str:
    if analysis.artifacts is None or artifact_name not in ARTIFACT_FIELDS:
        raise KeyError(artifact_name)
    return getattr(analysis.artifacts, ARTIFACT_FIELDS[artifact_name])


def all_results_text(analysis: DemoAnalysis) -> str:
    sections = [
        "ChangeProof complete result bundle",
        f"Company: {analysis.company_name}",
        f"Evidence: {analysis.evidence_source}",
        "Change: "
        f"{analysis.request.old_column} {analysis.request.old_type} "
        f"-> {analysis.request.new_type}",
    ]
    for item in ARTIFACT_EXPORTS:
        sections.extend(
            [
                "",
                "=" * 78,
                item["name"].upper(),
                "=" * 78,
                artifact_text(analysis, item["artifact_name"]),
            ]
        )
    return "\n".join(sections).rstrip() + "\n"


def pdf_bytes(title: str, content: str) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        leftMargin=0.62 * inch,
        rightMargin=0.62 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.58 * inch,
        title=title,
        author="ChangeProof",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChangeProofTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor="#12233f",
        alignment=TA_LEFT,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "ChangeProofBody",
        parent=styles["BodyText"],
        fontName="Courier",
        fontSize=9,
        leading=12,
        textColor="#263b59",
        wordWrap="CJK",
        spaceAfter=1,
    )
    story = [Paragraph(escape(title), title_style), Spacer(1, 4)]
    for line in content.splitlines() or [""]:
        story.append(Paragraph(escape(line) or "&nbsp;", body_style))
    document.build(story)
    return output.getvalue()
