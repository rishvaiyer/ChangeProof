from __future__ import annotations

from .models import (
    ChangeRequest,
    ChangeType,
    Confidence,
    ImpactAssessment,
    LineageNode,
    RemediationAction,
    RemediationPlan,
)


def plan_remediation(request: ChangeRequest, impact: ImpactAssessment) -> RemediationPlan:
    if request.change_type is ChangeType.COLUMN_RENAME:
        return _rename_plan(request, impact)
    if request.change_type is ChangeType.COLUMN_REMOVAL:
        return _removal_plan(request, impact)
    if request.change_type is ChangeType.COLUMN_TYPE_CHANGE:
        return _type_change_plan(request, impact)
    return _unsupported_plan(request, impact)


def _rename_plan(request: ChangeRequest, impact: ImpactAssessment) -> RemediationPlan:
    automatic = impact.confidence is Confidence.HIGH
    downstream_assets = _sorted_assets(impact.impacted_assets)
    actions = _rename_actions(request, downstream_assets)

    summary = (
        f"Add `{request.new_column}` while keeping `{request.old_column}` "
        "as a compatibility alias, "
        "then migrate observed downstream assets in hop order."
    )
    unresolved_risks = _common_risks(request, impact)
    if not automatic:
        summary = (
            f"Review the `{request.old_column}` to `{request.new_column}` "
            "rename manually before rollout "
            "because the observed lineage evidence is incomplete."
        )
        unresolved_risks.insert(
            0,
            "Observed impact confidence is "
            f"{impact.confidence.value}; automatic rename rollout is unsafe.",
        )

    return RemediationPlan(
        strategy="compatibility_alias",
        summary=summary,
        actions=actions,
        rollout_steps=[
            (
                f"Add `{request.new_column}` in `{request.source_file}` and keep "
                f"`{request.old_column}` as a compatibility alias."
            ),
            (
                f"Validate parity between `{request.old_column}` and "
                f"`{request.new_column}` before downstream edits."
            ),
            _ordered_rollout_step(
                downstream_assets,
                request.old_column or "",
                request.new_column or "",
            ),
            (
                "Re-run consistency tests while the alias remains available "
                f"for `{request.old_column}`."
            ),
            (
                "Remove the alias only after downstream owners confirm "
                f"migration to `{request.new_column}`."
            ),
        ],
        rollback_steps=[
            (
                f"Revert `{request.source_file}` to the previous model with "
                f"`{request.old_column}` as the canonical field."
            ),
            f"Point any migrated downstream assets back to `{request.old_column}`.",
            "Re-run compile and validation checks to confirm the prior contract is restored.",
        ],
        unresolved_risks=unresolved_risks,
        requires_approval=not automatic,
        supported_automatically=automatic,
    )


def _removal_plan(request: ChangeRequest, impact: ImpactAssessment) -> RemediationPlan:
    downstream_assets = _sorted_assets(impact.impacted_assets)
    return RemediationPlan(
        strategy="deprecation_window",
        summary=(
            f"Plan a deprecation window for removing `{request.old_column}`, "
            "preserve a compatibility view or "
            "alias during migration, and collect owner approval before deleting the field."
        ),
        actions=_removal_actions(request, downstream_assets),
        rollout_steps=[
            (
                f"Announce the proposed removal of `{request.old_column}` and "
                "the deprecation window to required reviewers."
            ),
            (
                f"Add a compatibility view or alias for `{request.old_column}` "
                "so downstream audits can happen safely."
            ),
            (
                "Audit each observed downstream asset for remaining "
                f"`{request.old_column}` usage and agree on owners' cutover dates."
            ),
            (
                f"Remove `{request.old_column}` only after owner approval and "
                "successful validation checks for every updated asset."
            ),
        ],
        rollback_steps=[
            f"Restore `{request.old_column}` in `{request.source_file}`.",
            "Keep the compatibility layer in place until downstream queries are stable again.",
            "Re-run compile and regression checks on the restored field contract.",
        ],
        unresolved_risks=_common_risks(request, impact),
        requires_approval=True,
        supported_automatically=False,
    )


def _type_change_plan(request: ChangeRequest, impact: ImpactAssessment) -> RemediationPlan:
    downstream_assets = _sorted_assets(impact.impacted_assets)
    return RemediationPlan(
        strategy="parallel_typed_field",
        summary=(
            f"Introduce a parallel typed field for `{request.old_column}`, "
            f"validate the safe cast from `{request.old_type}` to "
            f"`{request.new_type}`, and migrate downstream consumers in stages."
        ),
        actions=_type_change_actions(request, downstream_assets),
        rollout_steps=[
            (
                f"Add a parallel typed field for `{request.old_column}` "
                f"alongside the current `{request.old_type}` contract."
            ),
            (
                "Backfill the parallel field with a safe cast from "
                f"`{request.old_type}` to `{request.new_type}` and record "
                "validation results."
            ),
            (
                "Migrate observed downstream assets to the new typed field "
                "in hop order after owner review."
            ),
            (
                "Promote the new typed field only after compile, test, "
                f"and backfill validation succeed for `{request.new_type}`."
            ),
        ],
        rollback_steps=[
            (
                f"Keep or restore the original `{request.old_type}` field "
                f"for `{request.old_column}` as the active contract."
            ),
            (
                "Revert downstream consumers to the original field until "
                "cast and backfill issues are resolved."
            ),
            "Re-run compile and regression checks against the original type contract.",
        ],
        unresolved_risks=_common_risks(request, impact),
        requires_approval=True,
        supported_automatically=False,
    )


def _unsupported_plan(request: ChangeRequest, impact: ImpactAssessment) -> RemediationPlan:
    downstream_assets = _sorted_assets(impact.impacted_assets)
    return RemediationPlan(
        strategy="manual_review_required",
        summary=(
            "Observed metadata is not sufficient to generate a deterministic "
            "automatic remediation plan; "
            "manual review is required before any source or downstream edits."
        ),
        actions=_unsupported_actions(request, downstream_assets, impact),
        rollout_steps=[
            "Review the schema diff manually and confirm which source contract changed.",
            (
                "Expand metadata evidence for downstream consumers before "
                "drafting source or consumer edits."
            ),
            "Choose a rollout only after reviewers agree on the manual remediation sequence.",
        ],
        rollback_steps=[
            (
                "Stop the rollout and restore the last known-good source model "
                "if manual review uncovers unsafe changes."
            ),
            "Revert any partial downstream edits that relied on unverified assumptions.",
            "Re-run compile and regression checks once the previous contract is restored.",
        ],
        unresolved_risks=_common_risks(request, impact),
        requires_approval=True,
        supported_automatically=False,
    )


def _rename_actions(
    request: ChangeRequest,
    assets: list[LineageNode],
) -> list[RemediationAction]:
    if not assets:
        return [
            _source_action(
                request,
                "Review the rename before downstream updates can be proposed.",
            )
        ]
    return [
        RemediationAction(
            asset_urn=asset.urn,
            asset_name=asset.name,
            action=(
                f"Update `{asset.name}` to consume `{request.new_column}` "
                f"instead of `{request.old_column}` "
                "while the compatibility alias remains available."
            ),
            reason=_asset_reason(asset, request.old_column or ""),
            owner=_owner_for_asset(asset),
            validation_checks=[
                (
                    f"Compile `{asset.name}` after replacing "
                    f"`{request.old_column}` with `{request.new_column}`."
                ),
                (
                    "Run data consistency checks confirming "
                    f"`{request.old_column}` and `{request.new_column}` "
                    f"return identical values for `{asset.name}` before "
                    "alias removal."
                ),
            ],
        )
        for asset in assets
    ]


def _removal_actions(
    request: ChangeRequest,
    assets: list[LineageNode],
) -> list[RemediationAction]:
    if not assets:
        return [
            _source_action(
                request,
                f"Document the removal of `{request.old_column}` and gather "
                "manual lineage evidence first.",
            )
        ]
    return [
        RemediationAction(
            asset_urn=asset.urn,
            asset_name=asset.name,
            action=(
                f"Audit `{asset.name}` for remaining "
                f"`{request.old_column}` references and plan a replacement "
                "before the deprecation window closes."
            ),
            reason=_asset_reason(asset, request.old_column or ""),
            owner=_owner_for_asset(asset),
            validation_checks=[
                (
                    "Search compiled SQL or generated artifacts for "
                    f"`{request.old_column}` references in `{asset.name}`."
                ),
                (
                    f"Run targeted compile and regression checks for "
                    f"`{asset.name}` after applying the compatibility view "
                    "or alias."
                ),
            ],
        )
        for asset in assets
    ]


def _type_change_actions(
    request: ChangeRequest,
    assets: list[LineageNode],
) -> list[RemediationAction]:
    if not assets:
        return [
            _source_action(
                request,
                f"Validate a safe cast for `{request.old_column}` before "
                "downstream migrations are proposed.",
            )
        ]
    return [
        RemediationAction(
            asset_urn=asset.urn,
            asset_name=asset.name,
            action=(
                f"Update `{asset.name}` to read the parallel typed field for "
                f"`{request.old_column}` after a safe cast from "
                f"`{request.old_type}` to `{request.new_type}` and backfill "
                "validation."
            ),
            reason=_asset_reason(asset, request.old_column or ""),
            owner=_owner_for_asset(asset),
            validation_checks=[
                (
                    "Verify the safe cast from "
                    f"`{request.old_type}` to `{request.new_type}` preserves "
                    f"non-null values used by `{asset.name}`."
                ),
                (
                    f"Run backfill and regression checks for `{asset.name}` "
                    "against the parallel typed field before cutover."
                ),
            ],
        )
        for asset in assets
    ]


def _unsupported_actions(
    request: ChangeRequest,
    assets: list[LineageNode],
    impact: ImpactAssessment,
) -> list[RemediationAction]:
    if not assets:
        return [
            _source_action(
                request,
                f"Collect additional metadata evidence before editing `{request.source_file}`.",
                validation_checks=[
                    (
                        "Confirm the exact schema diff from typed fixtures "
                        "or the source project manifest."
                    ),
                    "Re-run manual review after expanding downstream lineage evidence.",
                ],
            )
        ]
    return [
        RemediationAction(
            asset_urn=asset.urn,
            asset_name=asset.name,
            action=(
                f"Review `{asset.name}` manually to determine how the "
                "unsupported schema change affects its dependency "
                "on the source model."
            ),
            reason=_asset_reason(asset, "the changed contract"),
            owner=_owner_for_asset(asset),
            validation_checks=[
                (
                    f"Confirm whether `{asset.name}` depends on the changed "
                    "contract using compiled SQL, tests, or fixture evidence."
                ),
                f"Record a reviewer-approved remediation step for `{asset.name}` before rollout.",
            ],
        )
        for asset in assets
    ] + (
        [
            _source_action(
                request,
                "Review unresolved impact evidence before drafting source edits.",
                validation_checks=[
                    "Expand lineage or ownership metadata for the unsupported change.",
                    "Re-run impact assessment after the evidence gaps are closed.",
                ],
            )
        ]
        if impact.confidence is not Confidence.HIGH
        else []
    )


def _source_action(
    request: ChangeRequest,
    action: str,
    *,
    validation_checks: list[str] | None = None,
) -> RemediationAction:
    return RemediationAction(
        asset_urn=request.dataset_urn or str(request.source_file),
        asset_name=request.source_file.stem,
        action=action,
        reason=(
            "No downstream asset-level automation can be justified from "
            "the observed evidence."
        ),
        validation_checks=validation_checks
        or [
            "Confirm the source model diff against typed fixtures before rollout.",
            "Obtain reviewer approval before editing the source contract.",
        ],
    )


def _common_risks(request: ChangeRequest, impact: ImpactAssessment) -> list[str]:
    risks: list[str] = [
        "Hidden consumers outside the observed lineage may still depend on "
        f"`{request.old_column or request.source_file.stem}`."
    ]
    if impact.critical_assets:
        risks.append(
            "Critical downstream assets require coordinated rollout: "
            + ", ".join(sorted(impact.critical_assets))
            + "."
        )
    if not impact.required_reviewers:
        risks.append(
            "No reviewers were observed in metadata, so ownership "
            "confirmation is still required."
        )
    if impact.confidence is not Confidence.HIGH:
        risks.append(
            "Observed metadata is incomplete, so the rollout must be treated "
            "as review-required."
        )
    return risks


def _asset_reason(asset: LineageNode, source_column: str) -> str:
    critical_note = " It is marked critical." if asset.critical else ""
    return (
        f"`{asset.name}` was observed {asset.hop} hop(s) downstream from `{source_column}`."
        f"{critical_note}"
    )


def _owner_for_asset(asset: LineageNode) -> str | None:
    return sorted(asset.owners)[0] if asset.owners else None


def _ordered_rollout_step(
    assets: list[LineageNode],
    old_column: str,
    new_column: str,
) -> str:
    if not assets:
        return (
            f"Review the rename from `{old_column}` to `{new_column}` manually "
            "because no downstream assets were observed."
        )
    ordered_assets = ", ".join(asset.name for asset in assets)
    return (
        "Update observed downstream assets in hop order "
        f"({ordered_assets}) to replace `{old_column}` with `{new_column}`."
    )


def _sorted_assets(nodes: list[LineageNode]) -> list[LineageNode]:
    return sorted(nodes, key=lambda node: (node.hop, node.name, node.urn))
