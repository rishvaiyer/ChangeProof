from dataclasses import dataclass
from pathlib import Path

from .classifier import classify_schema_change
from .impact import assess_impact
from .models import (
    AiReview,
    ArtifactBundle,
    ChangeRequest,
    ImpactAssessment,
    LineageNode,
    MetadataEvidence,
    RegionExposure,
    RemediationPlan,
    SqlDependency,
)
from .planner import plan_remediation

PLATFORM = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models"


def _urn(layer: str, name: str) -> str:
    return _urn_for("sonicledger.models", layer, name)


def _urn_for(platform_name: str, layer: str, name: str) -> str:
    return f"urn:li:dataset:(urn:li:dataPlatform:dbt,{platform_name}.{layer}.{name},PROD)"


SOURCE_URN = _urn("staging", "stg_streams")


class DemoInputError(ValueError):
    pass


@dataclass(frozen=True)
class DemoAnalysis:
    request: ChangeRequest
    evidence: MetadataEvidence
    impact: ImpactAssessment
    plan: RemediationPlan
    evidence_source: str
    company_name: str = "SonicLedger"
    platform_name: str = "sonicledger.models"
    sql_dependencies: tuple[SqlDependency, ...] = ()
    region_exposures: tuple[RegionExposure, ...] = ()
    artifacts: ArtifactBundle | None = None
    ai_review: AiReview | None = None

    @property
    def source_table(self) -> str:
        return self.evidence.source_urn.split(",")[1].split(".")[-1]

    @property
    def source_owner(self) -> str:
        return self.evidence.owners[0] if self.evidence.owners else "unowned"

    @property
    def source_label(self) -> str:
        return f"{self.source_table}.{self.evidence.source_field}"


@dataclass(frozen=True)
class DemoColumn:
    """One explorable column in the synthetic enterprise catalog."""

    column: str
    source_table: str
    source_layer: str
    source_file: str
    old_type: str
    new_type: str
    blurb: str
    owners: list[str]
    downstream: list[LineageNode]
    company_name: str = "SonicLedger"
    platform_name: str = "sonicledger.models"
    column_lineage_available: bool = True
    metadata_age_hours: float = 0.0
    missing: tuple[str, ...] = ()

    @property
    def source_urn(self) -> str:
        return _urn_for(self.platform_name, self.source_layer, self.source_table)


def _node(
    name: str,
    *,
    hop: int,
    layer: str = "marts",
    critical: bool = False,
    owners: list[str] | None = None,
    fields: list[str] | None = None,
    platform_name: str = "sonicledger.models",
) -> LineageNode:
    return LineageNode(
        urn=_urn_for(platform_name, layer, name),
        name=name,
        entity_type="dataset",
        hop=hop,
        fields=fields if fields is not None else [],
        owners=owners if owners is not None else ["finance@sonicledger.demo"],
        critical=critical,
    )


CATALOG: dict[str, DemoColumn] = {
    "customer_id": DemoColumn(
        column="customer_id",
        source_table="stg_orders",
        source_layer="staging",
        source_file="models/staging/stg_orders.sql",
        old_type="varchar",
        new_type="bigint",
        blurb="National order identity change across loyalty, returns, and finance.",
        owners=["commerce-data@astervale.demo"],
        company_name="AsterVale Living",
        platform_name="astervale.models",
        downstream=[
            _node(
                "fct_order_sales",
                hop=1,
                fields=["customer_id"],
                owners=["commerce-analytics@astervale.demo"],
                platform_name="astervale.models",
            ),
            _node(
                "loyalty_customer_value",
                hop=2,
                critical=True,
                fields=["customer_id"],
                owners=["loyalty-platform@astervale.demo"],
                platform_name="astervale.models",
            ),
            _node(
                "regional_returns",
                hop=2,
                fields=["customer_id"],
                owners=["store-operations@astervale.demo"],
                platform_name="astervale.models",
            ),
            _node(
                "executive_revenue_dashboard",
                hop=3,
                critical=True,
                fields=["customer_id"],
                owners=["finance-data@astervale.demo"],
                platform_name="astervale.models",
            ),
        ],
    ),
    # Full evidence: fresh column lineage, owners everywhere. Expect HIGH.
    "artist_id": DemoColumn(
        column="artist_id",
        source_table="stg_streams",
        source_layer="staging",
        source_file="models/staging/stg_streams.sql",
        old_type="varchar",
        new_type="bigint",
        blurb="Royalty pipeline. Two critical assets downstream.",
        owners=["analytics@sonicledger.demo"],
        downstream=[
            _node("fct_royalties", hop=1, fields=["artist_id"]),
            _node("artist_payouts", hop=2, critical=True, fields=["artist_id"]),
            _node(
                "finance_royalty_dashboard",
                hop=3,
                critical=True,
                fields=["artist_id"],
            ),
        ],
    ),
    # Clean but smaller radius, no critical assets. Expect HIGH.
    "track_id": DemoColumn(
        column="track_id",
        source_table="stg_streams",
        source_layer="staging",
        source_file="models/staging/stg_streams.sql",
        old_type="varchar",
        new_type="bigint",
        blurb="Catalog joins only. No critical assets exposed.",
        owners=["analytics@sonicledger.demo"],
        downstream=[
            _node("fct_royalties", hop=1, fields=["track_id"]),
            _node(
                "catalog_report",
                hop=2,
                owners=["catalog@sonicledger.demo"],
                fields=["track_id"],
            ),
        ],
    ),
    # Only table-level lineage was observed. Expect MEDIUM.
    "payout_amount": DemoColumn(
        column="payout_amount",
        source_table="fct_royalties",
        source_layer="marts",
        source_file="models/marts/fct_royalties.sql",
        old_type="decimal(10,2)",
        new_type="decimal(18,4)",
        blurb="Money column, but only table-level lineage was observed.",
        owners=["finance@sonicledger.demo"],
        downstream=[
            _node("artist_payouts", hop=1, critical=True),
            _node("finance_royalty_dashboard", hop=2, critical=True),
        ],
        column_lineage_available=False,
        missing=("column_lineage",),
    ),
    # Stale metadata. Expect LOW regardless of how good the graph looks.
    "stream_ts": DemoColumn(
        column="stream_ts",
        source_table="stg_streams",
        source_layer="staging",
        source_file="models/staging/stg_streams.sql",
        old_type="timestamp",
        new_type="timestamptz",
        blurb="Lineage evidence is three days stale.",
        owners=["analytics@sonicledger.demo"],
        downstream=[
            _node("fct_royalties", hop=1, fields=["stream_ts"]),
            _node(
                "daily_streams",
                hop=2,
                owners=["analytics@sonicledger.demo"],
                fields=["stream_ts"],
            ),
        ],
        metadata_age_hours=72.0,
    ),
    # Nothing observed downstream. Expect LOW, and say why.
    "listener_email": DemoColumn(
        column="listener_email",
        source_table="stg_listeners",
        source_layer="staging",
        source_file="models/staging/stg_listeners.sql",
        old_type="varchar",
        new_type="text",
        blurb="No downstream consumers observed. Absence is not proof.",
        owners=["growth@sonicledger.demo"],
        downstream=[],
    ),
}


def catalog_options() -> list[DemoColumn]:
    return list(CATALOG.values())


def analyze_demo_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis:
    entry = resolve_column(column)
    request = build_demo_request(column=column, old_type=old_type, new_type=new_type)
    return compose_analysis(
        request=request,
        evidence=_demo_evidence(column.strip()),
        evidence_source=(
            "Bundled SonicLedger demo metadata"
            if entry.company_name == "SonicLedger"
            else f"Bundled {entry.company_name} DataHub metadata"
        ),
        company_name=entry.company_name,
        platform_name=entry.platform_name,
    )


def resolve_column(column: str) -> DemoColumn:
    entry = CATALOG.get(column.strip())
    if entry is None:
        known = ", ".join(sorted(CATALOG))
        raise DemoInputError(f"Unknown column '{column.strip()}'. Try one of: {known}")
    return entry


def build_demo_request(*, column: str, old_type: str, new_type: str) -> ChangeRequest:
    entry = resolve_column(column)
    old_type = old_type.strip()
    new_type = new_type.strip()
    if not old_type or not new_type or old_type == new_type:
        raise DemoInputError("Old and new types must be different non-empty values.")
    if old_type != entry.old_type or new_type != entry.new_type:
        raise DemoInputError(
            f"Prepared transition for {entry.column} is "
            f"{entry.old_type} to {entry.new_type}."
        )

    return classify_schema_change(
        before_schema=[{"fieldPath": entry.column, "nativeDataType": old_type}],
        after_schema=[{"fieldPath": entry.column, "nativeDataType": new_type}],
        source_file=Path(entry.source_file),
        dataset_urn=entry.source_urn,
    )


def compose_analysis(
    *,
    request: ChangeRequest,
    evidence: MetadataEvidence,
    evidence_source: str,
    company_name: str = "SonicLedger",
    platform_name: str = "sonicledger.models",
) -> DemoAnalysis:
    impact = assess_impact(evidence)
    return DemoAnalysis(
        request=request,
        evidence=evidence,
        impact=impact,
        plan=plan_remediation(request, impact),
        evidence_source=evidence_source,
        company_name=company_name,
        platform_name=platform_name,
    )


def _demo_evidence(column: str) -> MetadataEvidence:
    entry = resolve_column(column)
    return MetadataEvidence(
        source_urn=entry.source_urn,
        source_field=entry.column,
        column_lineage_available=entry.column_lineage_available,
        downstream=list(entry.downstream),
        owners=list(entry.owners),
        assertions_passing=True,
        metadata_age_hours=entry.metadata_age_hours,
        missing=list(entry.missing),
    )
