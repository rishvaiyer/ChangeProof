from __future__ import annotations

import json
from pathlib import Path

from changeproof.classifier import classify_schema_change
from changeproof.models import ChangeType

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "examples" / "input" / "rename_artist_id.json"


def test_classify_schema_change_detects_single_column_rename() -> None:
    payload = json.loads(FIXTURE_PATH.read_text())

    request = classify_schema_change(
        before_schema=payload["before_schema"],
        after_schema=payload["after_schema"],
        source_file=Path(payload["source_file"]),
        dataset_urn=payload["dataset_urn"],
    )

    assert request.change_type is ChangeType.COLUMN_RENAME
    assert request.dataset_urn == payload["dataset_urn"]
    assert request.old_column == "artist_id"
    assert request.new_column == "rights_holder_id"
    assert request.old_type == "varchar"
    assert request.new_type == "varchar"


def test_classify_schema_change_detects_single_column_removal() -> None:
    request = classify_schema_change(
        before_schema=[
            {"fieldPath": "artist_id", "nativeDataType": "varchar"},
            {"fieldPath": "track_id", "nativeDataType": "varchar"},
        ],
        after_schema=[
            {"fieldPath": "track_id", "nativeDataType": "varchar"},
        ],
        source_file=Path("models/staging/stg_streams.sql"),
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
    )

    assert request.change_type is ChangeType.COLUMN_REMOVAL
    assert request.old_column == "artist_id"
    assert request.new_column is None
    assert request.old_type == "varchar"
    assert request.new_type is None


def test_classify_schema_change_detects_single_type_change() -> None:
    request = classify_schema_change(
        before_schema=[
            {"fieldPath": "artist_id", "nativeDataType": "varchar"},
        ],
        after_schema=[
            {"fieldPath": "artist_id", "nativeDataType": "bigint"},
        ],
        source_file=Path("models/staging/stg_streams.sql"),
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
    )

    assert request.change_type is ChangeType.COLUMN_TYPE_CHANGE
    assert request.old_column == "artist_id"
    assert request.new_column == "artist_id"
    assert request.old_type == "varchar"
    assert request.new_type == "bigint"


def test_classify_schema_change_marks_multiple_changes_as_unsupported() -> None:
    request = classify_schema_change(
        before_schema=[
            {"fieldPath": "artist_id", "nativeDataType": "varchar"},
            {"fieldPath": "track_id", "nativeDataType": "varchar"},
        ],
        after_schema=[
            {"fieldPath": "rights_holder_id", "nativeDataType": "varchar"},
            {"fieldPath": "track_id", "nativeDataType": "bigint"},
        ],
        source_file=Path("models/staging/stg_streams.sql"),
        dataset_urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
    )

    assert request.change_type is ChangeType.UNSUPPORTED
    assert request.old_column is None
    assert request.new_column is None
    assert request.old_type is None
    assert request.new_type is None
