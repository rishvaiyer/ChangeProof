from __future__ import annotations

import os
from dataclasses import replace

from .config import Settings
from .mcp_client import DataHubAssetContext, DataHubMcpClient
from .triage import DataHubStep, TriageResult


class TriageContextResult:
    def __init__(
        self,
        *,
        result: TriageResult,
        steps: tuple[DataHubStep, ...],
        evidence_mode: str,
    ) -> None:
        self.result = result
        self.steps = steps
        self.evidence_mode = evidence_mode


def enrich_triage_context(
    result: TriageResult,
    settings: Settings | None = None,
    client: DataHubMcpClient | None = None,
) -> TriageContextResult:
    settings = settings or Settings.from_env()
    if os.getenv("CHANGE_PROOF_TRIAGE_DATAHUB", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return TriageContextResult(
            result=result,
            steps=result.datahub_steps,
            evidence_mode=result.evidence_mode,
        )

    datahub_client = client or DataHubMcpClient(settings)
    replacements: dict[int, object] = {}
    steps: list[DataHubStep] = []
    try:
        for index, rule in enumerate(result.mappings, 1):
            if rule.status != "MAPPED" or not rule.asset_urn:
                continue
            context = datahub_client.get_asset_context(
                asset_urn=rule.asset_urn,
                source_field=rule.columns[0] if rule.columns else "*",
            )
            replacements[rule.number] = _replace_rule(rule, context)
            steps.append(_context_step(index, rule, context))
    except Exception:
        return TriageContextResult(
            result=result,
            steps=result.datahub_steps,
            evidence_mode="Bundled synthetic DataHub-shaped metadata; MCP fallback.",
        )

    rules = tuple(replacements.get(rule.number, rule) for rule in result.rules)
    mappings = tuple(rule for rule in rules if getattr(rule, "status", None) == "MAPPED")
    enriched = replace(
        result,
        rules=rules,
        mappings=mappings,
        datahub_steps=tuple(steps),
        evidence_mode="Live DataHub MCP context",
    )
    return TriageContextResult(
        result=enriched,
        steps=tuple(steps),
        evidence_mode=enriched.evidence_mode,
    )


def _replace_rule(rule: object, context: DataHubAssetContext) -> object:
    fields = context.fields or getattr(rule, "columns", ())
    owners = context.owners or (() if getattr(rule, "owner", None) is None else (rule.owner,))
    return replace(
        rule,
        columns=fields,
        owner=owners[0] if owners else getattr(rule, "owner", None),
        reason="Confirmed by live DataHub schema and context metadata.",
    )


def _context_step(index: int, rule: object, context: DataHubAssetContext) -> DataHubStep:
    asset_name = rule.asset_urn.rsplit(",", 2)[-2].removeprefix("astervale.").rstrip(")")
    search_detail = f"; search matched {context.search_matches} assets" if context.search_matches else ""
    query_detail = f"; query history returned {context.query_count} examples" if context.query_count else ""
    return DataHubStep(
        index,
        f"DataHub MCP lookup #{index} · {asset_name}",
        "Live DataHub returned schema fields "
        f"{', '.join(context.fields) or 'none'}, downstream lineage "
        f"{', '.join(context.lineage_assets) or 'none'}{search_detail}{query_detail}.",
    )
