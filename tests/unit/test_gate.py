from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from changeproof.gate import BLOCKED, PASS, REVIEW, UNSUPPORTED, app, evaluate_change

FIXTURE = Path(__file__).resolve().parents[2] / "examples" / "input" / "rename_artist_id.json"
runner = CliRunner()


def write_fixture(tmp_path: Path, *, field: str, after_type: str) -> Path:
    fixture = tmp_path / f"{field}.json"
    source_table = "stg_listeners" if field == "listener_email" else "stg_streams"
    fixture.write_text(
        json.dumps(
            {
                "dataset_urn": (
                    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
                    f"sonicledger.models.staging.{source_table},PROD)"
                ),
                "source_file": f"models/staging/stg_{field}.sql",
                "before_schema": [{"fieldPath": field, "nativeDataType": "varchar"}],
                "after_schema": [{"fieldPath": field, "nativeDataType": after_type}],
            }
        ),
        encoding="utf-8",
    )
    return fixture


def test_known_rename_passes_and_writes_reviewable_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"

    result = runner.invoke(app, ["gate", str(FIXTURE), "--output-dir", str(output_dir)])

    assert result.exit_code == 0
    assert PASS in result.stdout
    markdown = (output_dir / "contextiskey-gate.md").read_text(encoding="utf-8")
    sarif = json.loads((output_dir / "contextiskey-gate.sarif").read_text(encoding="utf-8"))
    assert "bundled-synthetic-datahub-shaped-metadata" in markdown
    assert "SQL execution: `none`" in markdown
    assert sarif["runs"][0]["results"][0]["properties"]["syntheticOnly"] is True


def test_low_confidence_evidence_is_review_gated(tmp_path: Path) -> None:
    fixture = write_fixture(tmp_path, field="listener_email", after_type="text")
    output_dir = tmp_path / "review-output"

    evaluation = evaluate_change(fixture)
    cli_result = runner.invoke(
        app,
        ["gate", str(fixture), "--output-dir", str(output_dir)],
    )

    assert evaluation.status == REVIEW
    assert evaluation.passed is False
    assert evaluation.impact is not None
    assert evaluation.impact.confidence.value == "LOW"
    assert cli_result.exit_code == 2
    assert (output_dir / "contextiskey-gate.md").is_file()
    assert (output_dir / "contextiskey-gate.sarif").is_file()


def test_unknown_bundled_field_is_blocked(tmp_path: Path) -> None:
    fixture = write_fixture(tmp_path, field="unknown_customer_key", after_type="bigint")

    evaluation = evaluate_change(fixture)

    assert evaluation.status == BLOCKED
    assert evaluation.passed is False


def test_multiple_changes_are_blocked_as_unsupported(tmp_path: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["after_schema"][1]["nativeDataType"] = "bigint"
    fixture = tmp_path / "unsupported.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    evaluation = evaluate_change(fixture)

    assert evaluation.status == UNSUPPORTED
    assert evaluation.passed is False
