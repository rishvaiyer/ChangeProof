from __future__ import annotations

from .models import Confidence, ImpactAssessment, LineageNode, MetadataEvidence

MAX_FRESH_METADATA_AGE_HOURS = 24.0


def assess_impact(evidence: MetadataEvidence) -> ImpactAssessment:
    impacted_assets = _sorted_assets(evidence.downstream)
    required_reviewers = _required_reviewers(evidence, impacted_assets)
    critical_assets = [node.name for node in impacted_assets if node.critical]

    metadata_is_fresh = evidence.metadata_age_hours <= MAX_FRESH_METADATA_AGE_HOURS
    has_usable_downstream_lineage = bool(impacted_assets)
    owner_coverage_complete = bool(evidence.owners) and all(
        node.owners for node in impacted_assets
    )
    missing_evidence = sorted(set(evidence.missing))

    reasons: list[str] = []
    if not metadata_is_fresh:
        reasons.append(
            "Observed metadata is stale at "
            f"{evidence.metadata_age_hours:.1f} hours; refresh lineage evidence before editing."
        )
    if not has_usable_downstream_lineage:
        reasons.append("No usable downstream lineage was observed for the changed field.")
    if impacted_assets and not evidence.column_lineage_available:
        reasons.append(
            "Only table-level downstream lineage was observed; "
            "column lineage is incomplete."
        )
    if impacted_assets and not owner_coverage_complete:
        reasons.append("Owner coverage is incomplete for the source or downstream assets.")
    if missing_evidence:
        reasons.append(f"Missing metadata evidence: {', '.join(missing_evidence)}.")

    if not reasons:
        reasons.extend(
            [
                "Fresh column lineage is available for the observed downstream assets.",
                "Owners are known for the source and downstream assets.",
            ]
        )

    confidence = _confidence(
        metadata_is_fresh=metadata_is_fresh,
        has_usable_downstream_lineage=has_usable_downstream_lineage,
        column_lineage_available=evidence.column_lineage_available,
        owner_coverage_complete=owner_coverage_complete,
        missing_evidence=missing_evidence,
    )

    return ImpactAssessment(
        confidence=confidence,
        reasons=reasons,
        impacted_assets=impacted_assets,
        required_reviewers=required_reviewers,
        critical_assets=critical_assets,
    )


def _confidence(
    *,
    metadata_is_fresh: bool,
    has_usable_downstream_lineage: bool,
    column_lineage_available: bool,
    owner_coverage_complete: bool,
    missing_evidence: list[str],
) -> Confidence:
    if not metadata_is_fresh or not has_usable_downstream_lineage:
        return Confidence.LOW
    if column_lineage_available and owner_coverage_complete and not missing_evidence:
        return Confidence.HIGH
    return Confidence.MEDIUM


def _required_reviewers(
    evidence: MetadataEvidence,
    impacted_assets: list[LineageNode],
) -> list[str]:
    return sorted(
        {
            *evidence.owners,
            *(owner for node in impacted_assets for owner in node.owners),
        }
    )


def _sorted_assets(nodes: list[LineageNode]) -> list[LineageNode]:
    return sorted(nodes, key=lambda node: (node.hop, node.name, node.urn))
