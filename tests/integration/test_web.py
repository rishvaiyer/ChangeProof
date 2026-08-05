from fastapi.testclient import TestClient

from changeproof.app import app

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
