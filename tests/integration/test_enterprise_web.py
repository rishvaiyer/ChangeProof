import json
import re

import pytest
from fastapi.testclient import TestClient

from changeproof.app import app, create_app

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
    ],
)
def test_enterprise_pages_share_navigation_and_context(path: str, heading: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert heading in response.text
    assert "AsterVale Living" in response.text
    assert "customer_id" in response.text
    assert 'aria-label="Primary navigation"' in response.text
    for href in ("/", "/impact", "/regions", "/fixes", "/rollout", "/datahub"):
        assert f'href="{href}"' in response.text


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
