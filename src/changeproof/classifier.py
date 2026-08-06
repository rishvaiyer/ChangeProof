from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import ChangeRequest, ChangeType


def classify_schema_change(
    *,
    before_schema: Sequence[Mapping[str, Any]],
    after_schema: Sequence[Mapping[str, Any]],
    source_file: Path,
    dataset_urn: str | None = None,
) -> ChangeRequest:
    before_fields = _index_schema(before_schema)
    after_fields = _index_schema(after_schema)

    removed = sorted(before_fields.keys() - after_fields.keys())
    added = sorted(after_fields.keys() - before_fields.keys())
    type_changes = sorted(
        field_name
        for field_name in before_fields.keys() & after_fields.keys()
        if before_fields[field_name] != after_fields[field_name]
    )

    if (
        len(removed) == 1
        and len(added) == 1
        and not type_changes
        and before_fields[removed[0]] == after_fields[added[0]]
    ):
        field_type = before_fields[removed[0]]
        return ChangeRequest(
            change_type=ChangeType.COLUMN_RENAME,
            dataset_urn=dataset_urn,
            old_column=removed[0],
            new_column=added[0],
            old_type=field_type,
            new_type=field_type,
            source_file=Path(source_file),
        )

    if len(removed) == 1 and not added and not type_changes:
        return ChangeRequest(
            change_type=ChangeType.COLUMN_REMOVAL,
            dataset_urn=dataset_urn,
            old_column=removed[0],
            old_type=before_fields[removed[0]],
            source_file=Path(source_file),
        )

    if len(type_changes) == 1 and not removed and not added:
        field_name = type_changes[0]
        return ChangeRequest(
            change_type=ChangeType.COLUMN_TYPE_CHANGE,
            dataset_urn=dataset_urn,
            old_column=field_name,
            new_column=field_name,
            old_type=before_fields[field_name],
            new_type=after_fields[field_name],
            source_file=Path(source_file),
        )

    return ChangeRequest(
        change_type=ChangeType.UNSUPPORTED,
        dataset_urn=dataset_urn,
        source_file=Path(source_file),
    )


def _index_schema(schema: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for field in schema:
        field_name = _read_field_name(field)
        field_type = _read_field_type(field)
        indexed[field_name] = field_type
    return indexed


def _read_field_name(field: Mapping[str, Any]) -> str:
    for key in ("fieldPath", "name", "column", "field"):
        value = field.get(key)
        if isinstance(value, str) and value:
            return value
    raise ValueError(f"Schema field is missing a supported name key: {field}")


def _read_field_type(field: Mapping[str, Any]) -> str:
    for key in ("nativeDataType", "type", "dataType"):
        value = field.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value:
            return value
        if isinstance(value, Mapping):
            nested_type = value.get("type")
            if isinstance(nested_type, str) and nested_type:
                return nested_type
            return json.dumps(value, sort_keys=True)
    raise ValueError(f"Schema field is missing a supported type key: {field}")
