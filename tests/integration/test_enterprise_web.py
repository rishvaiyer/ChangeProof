import json
import re
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from changeproof.app import app, create_app
from changeproof.triage import SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT

client = TestClient(app)


@pytest.mark.parametrize(
    ("path", "heading"),
    [
        ("/", "Change Command Center"),
        ("/impact", "Dependency Intelligence"),
        ("/regions", "Regional Exposure"),
        ("/fixes", "Fix Studio"),
        ("/rollout", "Release Control"),
        ("/datahub", "DataHub Actions"),
        ("/triage", "Triage Composer"),
    ],
)
def test_enterprise_pages_share_navigation_and_context(path: str, heading: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert heading in response.text
    assert "AsterVale Living" in response.text
    assert "customer_id" in response.text
    assert 'aria-label="Primary navigation"' in response.text
    for href in ("/", "/impact", "/regions", "/fixes", "/rollout", "/datahub", "/triage"):
        assert f'href="{href}"' in response.text


def test_triage_page_shows_sample_mapping_complex_sql_and_datahub_trail() -> None:
    response = client.get("/triage")

    assert response.status_code == 200
    assert "Triage Composer" in response.text
    assert "contextIsKey" in response.text
    assert "Built on ChangeProof" in response.text
    assert "How DataHub context helped" in response.text
    assert "finance.ar_transactions" in response.text
    assert "running_balance" in response.text
    assert "Bundled DataHub context" in response.text
    assert "Context graph coverage" in response.text
    assert "7</strong><small>bounded lookups" in response.text
    assert "Bundled DataHub-shaped context" in response.text
    assert "CONNECT TO ACTIVATE" in response.text
    assert "The file stays ephemeral" in response.text
    assert 'accept=".pdf,.docx,.txt,.md,.sql,.csv"' in response.text
    assert 'role="status"' in response.text


def _minimal_docx(text: str) -> bytes:
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>'''
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_triage_accepts_uploaded_txt_document_and_shows_receipt() -> None:
    response = client.post(
        "/triage",
        data={"question": "Investigate accounts receivable", "requirements_text": ""},
        files={"document": ("incident.txt", b"Compare invoice totals.", "text/plain")},
    )

    assert response.status_code == 200
    assert "Document received" in response.text
    assert "incident.txt" in response.text
    assert "23 characters" in response.text
    assert "finance.ar_transactions" in response.text


def test_triage_accepts_uploaded_docx_document() -> None:
    response = client.post(
        "/triage",
        data={"question": "Investigate settlements", "requirements_text": ""},
        files={"document": ("incident.docx", _minimal_docx("Check payment settlement timing."))},
    )

    assert response.status_code == 200
    assert "Document received" in response.text
    assert "incident.docx" in response.text
    assert "payments.settlements" in response.text


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [("incident.exe", b"nope", "Supported document formats"), ("incident.txt", b"", "empty")],
)
def test_triage_rejects_invalid_uploaded_documents(
    filename: str, content: bytes, message: str
) -> None:
    response = client.post(
        "/triage",
        data={"question": "Investigate", "requirements_text": ""},
        files={"document": (filename, content)},
    )

    assert response.status_code == 422
    assert message in response.text


def test_triage_accepts_requirements_and_flags_unknown_rules() -> None:
    response = client.post(
        "/triage",
        data={"question": "Investigate", "requirements_text": "Use lunar weather color."},
    )

    assert response.status_code == 200
    assert "UNMAPPED" in response.text


@pytest.mark.parametrize(
    ("format", "content_type"),
    [("sql", "text/plain"), ("txt", "text/plain"), ("pdf", "application/pdf")],
)
def test_triage_exports(format: str, content_type: str) -> None:
    response = client.post(
        f"/triage/export/{format}",
        data={"question": SAMPLE_INCIDENT_QUESTION, "requirements_text": SAMPLE_SRS_TEXT},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["content-disposition"] == (
        f'attachment; filename="contextIsKey-triage.{format}"'
    )
    if format == "pdf":
        assert b"contextIsKey" in response.content
        assert b"Built on ChangeProof" in response.content
    else:
        assert "contextIsKey" in response.text
        assert "Built on ChangeProof" in response.text


def test_triage_without_mappings_hides_evidence_controls() -> None:
    response = client.post(
        "/triage",
        data={"question": "Investigate", "requirements_text": "Use lunar weather color."},
    )

    assert response.status_code == 200
    assert "Reviewable investigation SQL" not in response.text
    assert 'formaction="/triage/export/sql"' not in response.text
    assert 'formaction="/triage/ai-review"' not in response.text


def test_triage_ai_review_discloses_it_receives_extracted_mappings(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-for-rendering")

    response = client.get("/triage")

    assert response.status_code == 200
    assert 'formaction="/triage/ai-review"' in response.text
    assert "Extracted rule mappings—not the original file—are sent to OpenAI." in response.text


def test_triage_rejects_unknown_export_format_before_generation(monkeypatch) -> None:
    def fail_if_generated(*args: str):
        raise AssertionError("invalid export must not build triage evidence")

    monkeypatch.setattr("changeproof.app.build_triage_result", fail_if_generated)

    response = client.post("/triage/export/csv", data={"question": "x", "requirements_text": "x"})

    assert response.status_code == 404


def test_impact_page_shows_datahub_and_hidden_sql_evidence() -> None:
    response = client.get("/impact")

    assert "DataHub lineage" in response.text
    assert "4 observed assets" in response.text
    assert "Hidden SQL consumers" in response.text
    assert "usp_reconcile_loyalty_customer" in response.text
    assert "usp_export_customer_segments" in response.text
    assert "MANUAL REVIEW" in response.text


def test_regions_page_shows_all_regions_and_unknown_metadata() -> None:
    response = client.get("/regions")

    for region in ("NORTHEAST", "SOUTH", "MIDWEST", "WEST", "UNKNOWN"):
        assert region in response.text
    assert "CA_PRIVACY_REVIEW" in response.text
    assert "REGION_METADATA_MISSING" in response.text


@pytest.mark.parametrize(
    "name",
    [
        "impact-report.json",
        "discovery-query.sql",
        "proposed-fixes.sql",
        "validation-queries.sql",
        "rollback.sql",
        "changeproof.sarif",
    ],
)
def test_artifacts_are_downloadable(name: str) -> None:
    response = client.get(f"/artifacts/{name}")

    assert response.status_code == 200
    assert f'attachment; filename="{name}"' == response.headers["content-disposition"]
    assert response.text


def test_artifact_downloads_are_allowlisted() -> None:
    response = client.get("/artifacts/secret.env")

    assert response.status_code == 404


@pytest.mark.parametrize("suffix, media_type", [("txt", "text/plain"), ("pdf", "application/pdf")])
@pytest.mark.parametrize(
    "artifact_name",
    [
        "impact-report.json",
        "discovery-query.sql",
        "proposed-fixes.sql",
        "validation-queries.sql",
        "rollback.sql",
        "changeproof.sarif",
    ],
)
def test_every_artifact_can_be_exported_as_text_or_pdf(
    artifact_name: str, suffix: str, media_type: str
) -> None:
    response = client.get(f"/exports/{artifact_name}.{suffix}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)
    assert response.headers["content-disposition"].endswith(
        f'filename="{artifact_name.removesuffix(artifact_name[artifact_name.rfind("."):])}.{suffix}"'
    )
    assert response.content


def test_all_results_bundle_can_be_exported_as_text_or_pdf() -> None:
    text_response = client.get("/exports/all-results.txt")
    pdf_response = client.get("/exports/all-results.pdf")

    assert text_response.status_code == 200
    assert "ChangeProof complete result bundle" in text_response.text
    assert "usp_reconcile_loyalty_customer" in text_response.text
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


def test_pages_expose_a_clear_export_center() -> None:
    response = client.get("/fixes")

    assert response.status_code == 200
    assert "Download all results" in response.text
    assert "TXT" in response.text
    assert "PDF" in response.text
    assert "/exports/proposed-fixes.sql.pdf" in response.text


def test_impact_report_download_is_valid_json() -> None:
    response = client.get("/artifacts/impact-report.json")

    assert json.loads(response.text)["company"] == "AsterVale Living"


def test_ai_review_is_explicit_and_explains_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    page = client.get("/fixes")
    match = re.search(r'name="analysis_token" value="([^"]+)"', page.text)
    assert match is not None
    response = client.post("/ai-review", data={"analysis_token": match.group(1)})

    assert page.status_code == 200
    assert 'action="/ai-review"' in page.text
    assert "AI_REVIEWED" not in page.text
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.text


def test_ai_key_status_never_exposes_the_secret(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-for-rendering")

    response = client.get("/fixes")

    assert response.status_code == 200
    assert "AI REVIEW READY" in response.text
    assert "sk-test-not-for-rendering" not in response.text


def test_ai_review_rejects_a_missing_analysis_token() -> None:
    response = client.post("/ai-review")

    assert response.status_code == 403


def test_navigation_preserves_a_validated_non_default_scenario() -> None:
    response = client.get(
        "/impact?column=artist_id&old_type=varchar&new_type=bigint"
    )

    assert response.status_code == 200
    assert "artist_payouts" in response.text
    assert "stg_streams.artist_id" in response.text
    assert "/regions?column=artist_id" in response.text


def test_invalid_artifact_name_does_not_invoke_provider() -> None:
    def failing_provider(**values: str):
        raise AssertionError("provider must not run for an invalid artifact name")

    response = TestClient(create_app(failing_provider)).get("/artifacts/secret.env")

    assert response.status_code == 404
