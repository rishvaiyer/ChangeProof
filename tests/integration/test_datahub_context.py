from __future__ import annotations

import os

import pytest

from changeproof.config import Settings


pytestmark = pytest.mark.skipif(
    os.getenv("CHANGE_PROOF_LIVE_DATAHUB") != "1",
    reason="Set CHANGE_PROOF_LIVE_DATAHUB=1 to run live DataHub checks.",
)


def test_live_datahub_lineage_contains_artist_payouts() -> None:
    settings = Settings.from_env()

    from scripts.seed_datahub import fetch_downstream_lineage

    downstream = fetch_downstream_lineage(
        gms_url=settings.datahub_gms_url,
        token=settings.datahub_gms_token,
        dataset_urn=(
            "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"
        ),
        source_field="artist_id",
    )

    assert "artist_payouts" in downstream
