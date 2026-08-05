from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def _load_seed_datahub_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_datahub.py"
    spec = importlib.util.spec_from_file_location("seed_datahub_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seed_datahub = _load_seed_datahub_module()
DatasetSpec = seed_datahub.DatasetSpec
FieldSpec = seed_datahub.FieldSpec
SchemaMetadataClass = seed_datahub.SchemaMetadataClass
validate_expected_downstream_lineage = seed_datahub.validate_expected_downstream_lineage


def test_validate_expected_downstream_lineage_accepts_complete_seeded_chain() -> None:
    observed = ["fct_royalties", "artist_payouts", "finance_royalty_dashboard"]

    validate_expected_downstream_lineage(observed)


def test_validate_expected_downstream_lineage_raises_for_missing_seeded_lineage() -> None:
    observed = ["fct_royalties"]

    with pytest.raises(RuntimeError, match="artist_payouts"):
        validate_expected_downstream_lineage(observed)


class _SerializingGraph:
    def __init__(self) -> None:
        self.emitted = []

    def emit(self, proposal) -> None:
        proposal.aspect.to_obj()
        self.emitted.append(proposal)


def test_emit_datasets_serializes_schema_metadata_for_seed_fixture() -> None:
    spec = DatasetSpec(
        urn="urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)",
        name="sonicledger.models.staging.stg_streams",
        description="Synthetic staging dataset for DataHub seed verification.",
        fields=(
            FieldSpec("stream_id", "integer", "Unique stream event identifier."),
            FieldSpec(
                "artist_id",
                "varchar",
                "Stable artist identifier used across the SonicLedger lineage chain.",
            ),
        ),
        owners=("analytics@sonicledger.demo",),
        upstreams=(),
    )
    graph = _SerializingGraph()

    emitted_urns = seed_datahub.emit_datasets(graph, {"stg_streams": spec})

    assert spec.urn in emitted_urns
    schema_aspects = [
        proposal.aspect for proposal in graph.emitted if isinstance(proposal.aspect, SchemaMetadataClass)
    ]
    assert len(schema_aspects) == 1
