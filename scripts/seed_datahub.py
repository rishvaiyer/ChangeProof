from __future__ import annotations

import json
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datahub.emitter.mce_builder import (
    make_data_platform_urn,
    make_dataset_urn,
    make_schema_field_urn,
    make_tag_urn,
    make_user_urn,
)
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import EmitMode
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
from datahub.metadata.schema_classes import (
    CorpUserInfoClass,
    DatasetPropertiesClass,
    FineGrainedLineageClass,
    GlobalTagsClass,
    OwnerClass,
    OwnershipClass,
    OwnershipTypeClass,
    SchemaFieldClass,
    SchemaFieldDataTypeClass,
    SchemalessClass,
    SchemaMetadataClass,
    StringTypeClass,
    TagAssociationClass,
    TagPropertiesClass,
    UpstreamClass,
    UpstreamLineageClass,
)

from changeproof.config import Settings

ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT / "demo" / "sonicledger"
MANIFEST_PATH = PROJECT_DIR / "target" / "manifest.json"
PLATFORM = "dbt"
ENVIRONMENT = "PROD"
TAG_NAME = "ChangeProofCritical"
EXPECTED_DOWNSTREAM_LINEAGE = (
    "fct_royalties",
    "artist_payouts",
    "finance_royalty_dashboard",
)
DEMO_OWNERS = {
    "analytics": "analytics@sonicledger.demo",
    "finance": "finance@sonicledger.demo",
}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    native_type: str
    description: str


@dataclass(frozen=True)
class DatasetSpec:
    urn: str
    name: str
    description: str
    fields: tuple[FieldSpec, ...]
    owners: tuple[str, ...]
    upstreams: tuple[str, ...]
    critical: bool = False


FIELD_SPECS: dict[str, tuple[FieldSpec, ...]] = {
    "raw_dsp_streams": (
        FieldSpec("stream_id", "integer", "Unique stream event identifier."),
        FieldSpec(
            "artist_id",
            "varchar",
            "Stable artist identifier used across the SonicLedger lineage chain.",
        ),
        FieldSpec("track_id", "varchar", "Track identifier."),
        FieldSpec("territory_code", "varchar", "Market territory code."),
        FieldSpec("stream_count", "integer", "Paid stream count."),
        FieldSpec("rate_per_stream", "decimal(10,4)", "Royalty rate per stream."),
    ),
    "stg_streams": (
        FieldSpec("stream_id", "integer", "Unique stream event identifier."),
        FieldSpec(
            "artist_id",
            "varchar",
            "Stable artist identifier used across the SonicLedger lineage chain.",
        ),
        FieldSpec("track_id", "varchar", "Track identifier."),
        FieldSpec("territory_code", "varchar", "Market territory code."),
        FieldSpec("stream_count", "integer", "Paid stream count."),
        FieldSpec("rate_per_stream", "decimal(10,4)", "Royalty rate per stream."),
        FieldSpec("royalty_amount", "decimal(12,4)", "Per-event royalty value."),
    ),
    "fct_royalties": (
        FieldSpec("stream_id", "integer", "Unique stream event identifier."),
        FieldSpec(
            "artist_id",
            "varchar",
            "Stable artist identifier used across the SonicLedger lineage chain.",
        ),
        FieldSpec("track_id", "varchar", "Track identifier."),
        FieldSpec("territory_code", "varchar", "Market territory code."),
        FieldSpec("stream_count", "integer", "Paid stream count."),
        FieldSpec("rate_per_stream", "decimal(10,4)", "Royalty rate per stream."),
        FieldSpec("royalty_amount", "decimal(12,4)", "Per-event royalty value."),
    ),
    "artist_payouts": (
        FieldSpec(
            "artist_id",
            "varchar",
            "Stable artist identifier used across the SonicLedger lineage chain.",
        ),
        FieldSpec("total_streams", "integer", "Total streams per artist."),
        FieldSpec("total_royalty_amount", "decimal(12,4)", "Total royalty amount per artist."),
    ),
    "finance_royalty_dashboard": (
        FieldSpec(
            "artist_id",
            "varchar",
            "Stable artist identifier used across the SonicLedger lineage chain.",
        ),
        FieldSpec("total_streams", "integer", "Total streams per artist."),
        FieldSpec("total_royalty_amount", "decimal(12,4)", "Total royalty amount per artist."),
        FieldSpec("payout_band", "varchar", "Finance payout priority band."),
    ),
}

DATASET_OWNERS = {
    "raw_dsp_streams": (DEMO_OWNERS["analytics"],),
    "stg_streams": (DEMO_OWNERS["analytics"],),
    "fct_royalties": (DEMO_OWNERS["finance"],),
    "artist_payouts": (DEMO_OWNERS["finance"],),
    "finance_royalty_dashboard": (DEMO_OWNERS["finance"],),
}

CRITICAL_DATASETS = {"artist_payouts"}


def build_graph(gms_url: str, token: str) -> DataHubGraph:
    return DataHubGraph(DatahubClientConfig(server=gms_url, token=token or None))


def ensure_manifest() -> None:
    if MANIFEST_PATH.exists():
        return
    result = subprocess.run(
        [
            "uv",
            "run",
            "dbt",
            "parse",
            "--project-dir",
            str(PROJECT_DIR),
            "--profiles-dir",
            str(PROJECT_DIR),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)


def load_manifest() -> dict[str, Any]:
    ensure_manifest()
    return json.loads(MANIFEST_PATH.read_text())


def dataset_name_for_node(node: dict[str, Any]) -> str:
    project_name = node["package_name"]
    resource_type = node["resource_type"]
    name = node["name"]
    if resource_type == "seed":
        return f"{project_name}.seeds.{name}"

    path_parts = Path(node["path"]).parts
    if path_parts and path_parts[0] == "staging":
        return f"{project_name}.models.staging.{name}"
    if path_parts and path_parts[0] == "marts":
        return f"{project_name}.models.marts.{name}"
    return f"{project_name}.models.{name}"


def build_dataset_specs(manifest: dict[str, Any]) -> dict[str, DatasetSpec]:
    nodes = {**manifest.get("nodes", {}), **manifest.get("sources", {})}
    name_to_urn: dict[str, str] = {}
    for node in nodes.values():
        if node.get("resource_type") not in {"model", "seed"}:
            continue
        dataset_name = dataset_name_for_node(node)
        name_to_urn[node["name"]] = make_dataset_urn(PLATFORM, dataset_name, ENVIRONMENT)

    specs: dict[str, DatasetSpec] = {}
    for node in nodes.values():
        if node.get("resource_type") not in {"model", "seed"}:
            continue
        model_name = node["name"]
        dataset_name = dataset_name_for_node(node)
        urn = name_to_urn[model_name]
        fields = FIELD_SPECS[model_name]
        upstreams = tuple(
            name_to_urn[upstream_name]
            for upstream_name in [
                dependency.split(".")[-1]
                for dependency in node.get("depends_on", {}).get("nodes", [])
            ]
            if upstream_name in name_to_urn
        )
        description = node.get("description") or f"SonicLedger dataset {dataset_name}."
        specs[model_name] = DatasetSpec(
            urn=urn,
            name=dataset_name,
            description=description,
            fields=fields,
            owners=DATASET_OWNERS[model_name],
            upstreams=upstreams,
            critical=model_name in CRITICAL_DATASETS,
        )
    return specs


def build_aspect_proposal(entity_urn: str, aspect: Any) -> MetadataChangeProposalWrapper:
    return MetadataChangeProposalWrapper(
        entityUrn=entity_urn,
        aspect=aspect,
    )


def emit_proposals(graph: DataHubGraph, proposals: list[MetadataChangeProposalWrapper]) -> None:
    if not proposals:
        return
    graph.emit_mcps(proposals, emit_mode=EmitMode.SYNC_PRIMARY)


def schema_field(dataset_urn: str, spec: FieldSpec) -> SchemaFieldClass:
    return SchemaFieldClass(
        fieldPath=spec.name,
        type=SchemaFieldDataTypeClass(type=StringTypeClass()),
        nativeDataType=spec.native_type,
        nullable=False,
        recursive=False,
        description=spec.description,
    )


def build_reference_entity_proposals() -> tuple[list[MetadataChangeProposalWrapper], list[str]]:
    proposals: list[MetadataChangeProposalWrapper] = []
    emitted: list[str] = []

    tag_urn = make_tag_urn(TAG_NAME)
    proposals.append(
        build_aspect_proposal(
            tag_urn,
            TagPropertiesClass(
                name=TAG_NAME,
                description=(
                    "Marks downstream SonicLedger assets that ChangeProof treats as critical."
                ),
            ),
        )
    )
    emitted.append(tag_urn)

    for owner_email in DEMO_OWNERS.values():
        owner_urn = make_user_urn(owner_email)
        proposals.append(
            build_aspect_proposal(
                owner_urn,
                CorpUserInfoClass(
                    active=True,
                    displayName=owner_email,
                    email=owner_email,
                    fullName=owner_email,
                    title="Demo owner",
                ),
            )
        )
        emitted.append(owner_urn)

    return proposals, emitted


def emit_reference_entities(graph: DataHubGraph) -> list[str]:
    proposals, emitted = build_reference_entity_proposals()
    emit_proposals(graph, proposals)
    return emitted


def build_dataset_proposals(
    specs: dict[str, DatasetSpec],
) -> tuple[list[MetadataChangeProposalWrapper], list[str]]:
    proposals: list[MetadataChangeProposalWrapper] = []
    emitted_urns: list[str] = []
    tag_urn = make_tag_urn(TAG_NAME)
    platform_urn = make_data_platform_urn(PLATFORM)

    for model_name, spec in specs.items():
        proposals.append(
            build_aspect_proposal(spec.urn, DatasetPropertiesClass(description=spec.description))
        )
        proposals.append(
            build_aspect_proposal(
                spec.urn,
                SchemaMetadataClass(
                    schemaName=model_name,
                    platform=platform_urn,
                    version=0,
                    hash="",
                    platformSchema=SchemalessClass(),
                    fields=[schema_field(spec.urn, field_spec) for field_spec in spec.fields],
                ),
            )
        )
        proposals.append(
            build_aspect_proposal(
                spec.urn,
                OwnershipClass(
                    owners=[
                        OwnerClass(
                            owner=make_user_urn(owner_email), type=OwnershipTypeClass.DATAOWNER
                        )
                        for owner_email in spec.owners
                    ]
                ),
            )
        )
        if spec.critical:
            proposals.append(
                build_aspect_proposal(
                    spec.urn,
                    GlobalTagsClass(tags=[TagAssociationClass(tag=tag_urn)]),
                )
            )

        fine_grained: list[FineGrainedLineageClass] = []
        for upstream_urn in spec.upstreams:
            if any(field.name == "artist_id" for field in spec.fields):
                fine_grained.append(
                    FineGrainedLineageClass(
                        upstreamType="FIELD_SET",
                        upstreams=[make_schema_field_urn(upstream_urn, "artist_id")],
                        downstreamType="FIELD",
                        downstreams=[make_schema_field_urn(spec.urn, "artist_id")],
                    )
                )

        proposals.append(
            build_aspect_proposal(
                spec.urn,
                UpstreamLineageClass(
                    upstreams=[
                        UpstreamClass(dataset=upstream_urn, type="TRANSFORMED")
                        for upstream_urn in spec.upstreams
                    ],
                    fineGrainedLineages=fine_grained,
                ),
            )
        )

        emitted_urns.append(spec.urn)
        emitted_urns.extend(make_schema_field_urn(spec.urn, field.name) for field in spec.fields)

    return proposals, emitted_urns


def emit_datasets(graph: DataHubGraph, specs: dict[str, DatasetSpec]) -> list[str]:
    proposals, emitted_urns = build_dataset_proposals(specs)
    emit_proposals(graph, proposals)
    return emitted_urns


def schema_field_present(graph: DataHubGraph, schema_field_urn: str) -> bool:
    prefix = "urn:li:schemaField:("
    if not schema_field_urn.startswith(prefix) or not schema_field_urn.endswith(")"):
        return False

    dataset_urn, field_path = schema_field_urn[len(prefix) : -1].rsplit(",", 1)
    schema = graph.get_aspect(dataset_urn, SchemaMetadataClass)
    return schema is not None and any(field.fieldPath == field_path for field in schema.fields)


def verify_emitted_urns(graph: DataHubGraph, urns: list[str]) -> None:
    missing = [
        urn
        for urn in urns
        if not (
            schema_field_present(graph, urn)
            if urn.startswith("urn:li:schemaField:")
            else graph.exists(urn)
        )
    ]
    if missing:
        missing_text = "\n".join(missing)
        raise RuntimeError(f"Failed to read back emitted URNs:\n{missing_text}")


def urn_to_name(dataset_urn: str) -> str:
    identifier = dataset_urn.split(",")[1]
    return identifier.split(".")[-1]


def validate_expected_downstream_lineage(observed: list[str]) -> None:
    missing = [
        dataset_name for dataset_name in EXPECTED_DOWNSTREAM_LINEAGE if dataset_name not in observed
    ]
    if missing:
        missing_text = ", ".join(missing)
        observed_text = ", ".join(observed) if observed else "<none>"
        raise RuntimeError(
            "Seeded DataHub lineage readback is incomplete. "
            f"Missing expected downstream lineage: {missing_text}. "
            f"Observed: {observed_text}"
        )


def fetch_downstream_lineage(
    gms_url: str,
    token: str,
    dataset_urn: str,
    source_field: str,
    dataset_urns: list[str] | None = None,
) -> list[str]:
    graph = build_graph(gms_url=gms_url, token=token)
    source_field_urn = make_schema_field_urn(dataset_urn, source_field)

    if dataset_urns is None:
        dataset_urns = list(
            graph.get_urns_by_filter(
                entity_types=["dataset"],
                platform=PLATFORM,
                env=ENVIRONMENT,
                query="sonicledger",
            )
        )
    upstream_by_dataset = {urn: graph.get_aspect(urn, UpstreamLineageClass) for urn in dataset_urns}
    schema_by_dataset = {urn: graph.get_aspect(urn, SchemaMetadataClass) for urn in dataset_urns}

    seen = {dataset_urn}
    queue: deque[str] = deque([dataset_urn])
    downstream: list[str] = []

    while queue:
        current = queue.popleft()
        for candidate_urn, lineage in upstream_by_dataset.items():
            if candidate_urn in seen or lineage is None:
                continue
            candidate_upstreams = {upstream.dataset for upstream in lineage.upstreams}
            if current not in candidate_upstreams:
                continue

            schema = schema_by_dataset.get(candidate_urn)
            has_field = schema is not None and any(
                field.fieldPath == source_field for field in schema.fields
            )
            has_field_lineage = any(
                source_field_urn in fine.upstreams
                or any(
                    downstream_field.endswith(f",{source_field})")
                    for downstream_field in fine.downstreams
                )
                for fine in lineage.fineGrainedLineages or []
            )

            if has_field and has_field_lineage:
                downstream.append(urn_to_name(candidate_urn))
                seen.add(candidate_urn)
                queue.append(candidate_urn)

    return downstream


def main() -> int:
    settings = Settings.from_env()
    graph = build_graph(settings.datahub_gms_url, settings.datahub_gms_token)
    manifest = load_manifest()
    specs = build_dataset_specs(manifest)

    emitted_urns = emit_reference_entities(graph)
    emitted_urns.extend(emit_datasets(graph, specs))
    verify_emitted_urns(graph, emitted_urns)

    downstream = fetch_downstream_lineage(
        gms_url=settings.datahub_gms_url,
        token=settings.datahub_gms_token,
        dataset_urn=specs["stg_streams"].urn,
        source_field="artist_id",
        dataset_urns=[spec.urn for spec in specs.values()],
    )
    validate_expected_downstream_lineage(downstream)
    print("Seeded DataHub demo metadata for:", ", ".join(sorted(specs)))
    print("Observed downstream lineage for artist_id:", ", ".join(downstream))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
