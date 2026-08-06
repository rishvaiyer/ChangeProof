from dataclasses import dataclass
from pathlib import Path

from .classifier import classify_schema_change
from .impact import assess_impact
from .models import (
    ChangeRequest,
    ImpactAssessment,
    LineageNode,
    MetadataEvidence,
    RemediationPlan,
)
from .planner import plan_remediation

SOURCE_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,"
    "sonicledger.models.staging.stg_streams,PROD)"
)


@dataclass(frozen=True)
class DemoAnalysis:
    request: ChangeRequest
    evidence: MetadataEvidence
    impact: ImpactAssessment
    plan: RemediationPlan


def analyze_demo_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis:
    column = column.strip()
    old_type = old_type.strip()
    new_type = new_type.strip()
    if column != "artist_id":
        raise ValueError("Supported demo column: artist_id")
    if not old_type or not new_type or old_type == new_type:
        raise ValueError("Old and new types must be different non-empty values.")

    request = classify_schema_change(
        before_schema=[{"fieldPath": column, "nativeDataType": old_type}],
        after_schema=[{"fieldPath": column, "nativeDataType": new_type}],
        source_file=Path("models/staging/stg_streams.sql"),
        dataset_urn=SOURCE_URN,
    )
    evidence = _demo_evidence()
    impact = assess_impact(evidence)
    return DemoAnalysis(
        request=request,
        evidence=evidence,
        impact=impact,
        plan=plan_remediation(request, impact),
    )


def _demo_evidence() -> MetadataEvidence:
    return MetadataEvidence(
        source_urn=SOURCE_URN,
        source_field="artist_id",
        column_lineage_available=True,
        downstream=[
            _dataset("fct_royalties", hop=1),
            _dataset("artist_payouts", hop=2, critical=True),
            _dataset("finance_royalty_dashboard", hop=3, critical=True),
        ],
        owners=["analytics@sonicledger.demo"],
        assertions_passing=True,
        metadata_age_hours=0.0,
        missing=[],
    )


def _dataset(name: str, *, hop: int, critical: bool = False) -> LineageNode:
    return LineageNode(
        urn=(
            "urn:li:dataset:(urn:li:dataPlatform:dbt,"
            f"sonicledger.models.marts.{name},PROD)"
        ),
        name=name,
        entity_type="dataset",
        hop=hop,
        fields=["artist_id"],
        owners=["finance@sonicledger.demo"],
        critical=critical,
    )
