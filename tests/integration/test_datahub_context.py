from __future__ import annotations

import os

import pytest

from changeproof.config import Settings
from changeproof.mcp_client import DataHubMcpClient

SOURCE_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"

pytestmark = pytest.mark.skipif(
    os.getenv("CHANGE_PROOF_LIVE_DATAHUB") != "1",
    reason="Set CHANGE_PROOF_LIVE_DATAHUB=1 to run live DataHub checks.",
)


def test_live_datahub_lineage_contains_artist_payouts() -> None:
    settings = Settings.from_env()
    evidence = DataHubMcpClient(settings).get_downstream_context(
        source_urn=SOURCE_URN,
        source_field="artist_id",
    )

    assert evidence.column_lineage_available is True
    assert "artist_payouts" in {node.name for node in evidence.downstream}
