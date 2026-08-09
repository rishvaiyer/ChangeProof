from __future__ import annotations

from dataclasses import dataclass

from changeproof.mcp_client import DataHubAssetContext
from changeproof.triage import build_triage_result
from changeproof.triage_context import enrich_triage_context


class FakeDataHubClient:
    calls: list[tuple[str, str]] = []

    def __init__(self, settings: object):
        self.settings = settings

    def get_asset_context(self, *, asset_urn: str, source_field: str) -> DataHubAssetContext:
        self.calls.append((asset_urn, source_field))
        return DataHubAssetContext(
            asset_urn=asset_urn,
            fields=("invoice_id", "customer_id", "amount", "posted_at"),
            owners=("finance-owner@example.com",),
            lineage_assets=("finance.ar_transactions downstream",),
            query_count=2,
        )


def test_enrich_triage_context_keeps_bundled_mode_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CHANGE_PROOF_TRIAGE_DATAHUB", raising=False)
    result = build_triage_result("Investigate invoices", "Compare invoice totals.")

    enriched = enrich_triage_context(result)

    assert enriched.result == result
    assert enriched.evidence_mode == result.evidence_mode
    assert enriched.steps == result.datahub_steps


def test_enrich_triage_context_uses_live_schema_lineage_and_query_context(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE_PROOF_TRIAGE_DATAHUB", "1")
    monkeypatch.setattr("changeproof.triage_context.DataHubMcpClient", FakeDataHubClient)
    FakeDataHubClient.calls = []
    result = build_triage_result(
        "Investigate invoices and payments",
        "Compare invoice totals.\nCheck payment settlement timing.",
    )

    enriched = enrich_triage_context(result)

    assert len(FakeDataHubClient.calls) == 2
    assert enriched.evidence_mode == "Live DataHub MCP context"
    assert len(enriched.steps) == 2
    assert all(step.operation.startswith("DataHub MCP lookup") for step in enriched.steps)
    assert "schema fields" in enriched.steps[0].query_decision
    assert "lineage" in enriched.steps[0].query_decision
    assert "query history" in enriched.steps[0].query_decision
    assert enriched.result.mappings[0].columns == (
        "invoice_id",
        "customer_id",
        "amount",
        "posted_at",
    )
    assert enriched.result.mappings[0].owner == "finance-owner@example.com"


def test_enrich_triage_context_falls_back_when_mcp_fails(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE_PROOF_TRIAGE_DATAHUB", "1")

    @dataclass
    class BrokenClient:
        settings: object

        def get_asset_context(self, *, asset_urn: str, source_field: str) -> DataHubAssetContext:
            raise RuntimeError("DataHub unavailable")

    monkeypatch.setattr("changeproof.triage_context.DataHubMcpClient", BrokenClient)
    result = build_triage_result("Investigate invoices", "Compare invoice totals.")

    enriched = enrich_triage_context(result)

    assert enriched.result == result
    assert enriched.evidence_mode == "Bundled synthetic DataHub-shaped metadata; MCP fallback."
    assert enriched.steps == result.datahub_steps
