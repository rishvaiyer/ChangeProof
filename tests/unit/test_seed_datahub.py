from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from datahub.emitter.mce_builder import make_schema_field_urn
from datahub.emitter.rest_emitter import EmitMode
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
verify_emitted_urns = seed_datahub.verify_emitted_urns


def test_validate_expected_downstream_lineage_accepts_complete_seeded_chain() -> None:
    observed = ["fct_royalties", "artist_payouts", "finance_royalty_dashboard"]

    validate_expected_downstream_lineage(observed)


def test_validate_expected_downstream_lineage_raises_for_missing_seeded_lineage() -> None:
    observed = ["fct_royalties"]

    with pytest.raises(RuntimeError, match="artist_payouts"):
        validate_expected_downstream_lineage(observed)


class _ReadbackGraph:
    def __init__(self, existing_urns, schema_by_urn) -> None:
        self.existing_urns = set(existing_urns)
        self.schema_by_urn = dict(schema_by_urn)

    def exists(self, urn: str) -> bool:
        return urn in self.existing_urns

    def get_aspect(self, urn: str, aspect_type):
        if aspect_type is SchemaMetadataClass:
            return self.schema_by_urn.get(urn)
        return None

    def get_urns_by_filter(self, **kwargs):
        raise AssertionError("search should not be used when dataset URNs are supplied")


def test_verify_emitted_urns_accepts_schema_field_readback_via_dataset_schema() -> None:
    dataset_urn = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"
    graph = _ReadbackGraph(
        existing_urns={dataset_urn},
        schema_by_urn={
            dataset_urn: SchemaMetadataClass(
                schemaName="stg_streams",
                platform="urn:li:dataPlatform:dbt",
                version=0,
                hash="",
                platformSchema=seed_datahub.SchemalessClass(),
                fields=[seed_datahub.schema_field(dataset_urn, FieldSpec("artist_id", "varchar", "Artist identifier."))],
            )
        },
    )

    verify_emitted_urns(
        graph,
        [
            dataset_urn,
            make_schema_field_urn(dataset_urn, "artist_id"),
        ],
    )


def test_fetch_downstream_lineage_uses_supplied_dataset_urns_without_search(monkeypatch: pytest.MonkeyPatch) -> None:
    source_urn = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"
    mid_urn = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.fct_royalties,PROD)"
    target_urn = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.artist_payouts,PROD)"

    graph = _ReadbackGraph(
        existing_urns={source_urn, mid_urn, target_urn},
        schema_by_urn={
            source_urn: SchemaMetadataClass(
                schemaName="stg_streams",
                platform="urn:li:dataPlatform:dbt",
                version=0,
                hash="",
                platformSchema=seed_datahub.SchemalessClass(),
                fields=[seed_datahub.schema_field(source_urn, FieldSpec("artist_id", "varchar", "Artist identifier."))],
            ),
            mid_urn: SchemaMetadataClass(
                schemaName="fct_royalties",
                platform="urn:li:dataPlatform:dbt",
                version=0,
                hash="",
                platformSchema=seed_datahub.SchemalessClass(),
                fields=[seed_datahub.schema_field(mid_urn, FieldSpec("artist_id", "varchar", "Artist identifier."))],
            ),
            target_urn: SchemaMetadataClass(
                schemaName="artist_payouts",
                platform="urn:li:dataPlatform:dbt",
                version=0,
                hash="",
                platformSchema=seed_datahub.SchemalessClass(),
                fields=[seed_datahub.schema_field(target_urn, FieldSpec("artist_id", "varchar", "Artist identifier."))],
            ),
        },
    )
    graph.lineage_by_urn = {
        source_urn: seed_datahub.UpstreamLineageClass(upstreams=[], fineGrainedLineages=[]),
        mid_urn: seed_datahub.UpstreamLineageClass(
            upstreams=[seed_datahub.UpstreamClass(dataset=source_urn, type="TRANSFORMED")],
            fineGrainedLineages=[
                seed_datahub.FineGrainedLineageClass(
                    upstreamType="FIELD_SET",
                    upstreams=[make_schema_field_urn(source_urn, "artist_id")],
                    downstreamType="FIELD",
                    downstreams=[make_schema_field_urn(mid_urn, "artist_id")],
                )
            ],
        ),
        target_urn: seed_datahub.UpstreamLineageClass(
            upstreams=[seed_datahub.UpstreamClass(dataset=mid_urn, type="TRANSFORMED")],
            fineGrainedLineages=[
                seed_datahub.FineGrainedLineageClass(
                    upstreamType="FIELD_SET",
                    upstreams=[make_schema_field_urn(source_urn, "artist_id")],
                    downstreamType="FIELD",
                    downstreams=[make_schema_field_urn(target_urn, "artist_id")],
                )
            ],
        ),
    }

    def fake_get_aspect(urn: str, aspect_type):
        if aspect_type is SchemaMetadataClass:
            return graph.schema_by_urn.get(urn)
        if aspect_type is seed_datahub.UpstreamLineageClass:
            return graph.lineage_by_urn.get(urn)
        return None

    graph.get_aspect = fake_get_aspect
    monkeypatch.setattr(seed_datahub, "build_graph", lambda gms_url, token: graph)

    downstream = seed_datahub.fetch_downstream_lineage(
        gms_url="http://unused:8080",
        token="",
        dataset_urn=source_urn,
        source_field="artist_id",
        dataset_urns=[source_urn, mid_urn, target_urn],
    )

    assert downstream == ["fct_royalties", "artist_payouts"]


class _SerializingGraph:
    def __init__(self) -> None:
        self.batch_calls = []

    def emit(self, proposal) -> None:
        raise AssertionError("emit() should not be used for dataset aspect writes")

    def emit_mcps(self, proposals, emit_mode=None, wait_timeout=None) -> None:
        for proposal in proposals:
            proposal.aspect.to_obj()
        self.batch_calls.append((list(proposals), emit_mode, wait_timeout))


def test_emit_datasets_batches_schema_metadata_for_seed_fixture() -> None:
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
    assert len(graph.batch_calls) == 1
    proposals, emit_mode, wait_timeout = graph.batch_calls[0]
    assert emit_mode == EmitMode.SYNC_PRIMARY
    assert wait_timeout is None
    schema_aspects = [
        proposal.aspect for proposal in proposals if isinstance(proposal.aspect, SchemaMetadataClass)
    ]
    assert len(schema_aspects) == 1
