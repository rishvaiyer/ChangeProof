from fastapi.testclient import TestClient

from changeproof.app import app, create_app, provider_from_env
from changeproof.demo import analyze_demo_change
from changeproof.live import analyze_live_change

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "changeproof"}


def test_dashboard_labels_demo_evidence() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "ChangeProof" in response.text
    assert "Bundled SonicLedger demo metadata" in response.text
    assert 'href="/static/styles.css"' in response.text


def test_analyze_renders_downstream_impact_and_safe_fix() -> None:
    response = client.post(
        "/analyze",
        data={"column": "artist_id", "old_type": "varchar", "new_type": "bigint"},
    )

    assert response.status_code == 200
    assert "artist_payouts" in response.text
    assert "parallel_typed_field" in response.text
    assert "Proposed safe rollout" in response.text


def test_analyze_returns_validation_message() -> None:
    response = client.post(
        "/analyze",
        data={"column": "unknown", "old_type": "varchar", "new_type": "bigint"},
    )

    assert response.status_code == 422
    assert "Supported demo column" in response.text


def test_dashboard_displays_injected_live_evidence_label() -> None:
    def live_provider(**values: str):
        result = analyze_demo_change(**values)
        return result.__class__(
            request=result.request,
            evidence=result.evidence,
            impact=result.impact,
            plan=result.plan,
            evidence_source="Live DataHub MCP evidence",
        )

    response = TestClient(create_app(live_provider)).get("/")

    assert response.status_code == 200
    assert "Live DataHub MCP evidence" in response.text
    assert "Bundled SonicLedger demo metadata" not in response.text


def test_live_provider_failure_returns_503_without_demo_fallback() -> None:
    def unavailable_provider(**values: str):
        raise RuntimeError("DataHub MCP unavailable")

    response = TestClient(create_app(unavailable_provider)).get("/")

    assert response.status_code == 503
    assert "DataHub MCP unavailable" in response.text
    assert "Bundled SonicLedger demo metadata" not in response.text


def test_provider_from_env_defaults_to_bundled(monkeypatch) -> None:
    monkeypatch.delenv("CHANGE_PROOF_EVIDENCE_MODE", raising=False)

    assert provider_from_env() is analyze_demo_change


def test_provider_from_env_selects_datahub(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE_PROOF_EVIDENCE_MODE", "datahub")

    assert provider_from_env() is analyze_live_change


def test_provider_from_env_rejects_unknown_mode(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE_PROOF_EVIDENCE_MODE", "mystery")

    try:
        provider_from_env()
    except RuntimeError as exc:
        assert "Unknown CHANGE_PROOF_EVIDENCE_MODE" in str(exc)
    else:
        raise AssertionError("Expected an unknown evidence mode to fail")
