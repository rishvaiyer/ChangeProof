from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

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
validate_expected_downstream_lineage = seed_datahub.validate_expected_downstream_lineage


def test_validate_expected_downstream_lineage_accepts_complete_seeded_chain() -> None:
    observed = ["fct_royalties", "artist_payouts", "finance_royalty_dashboard"]

    validate_expected_downstream_lineage(observed)


def test_validate_expected_downstream_lineage_raises_for_missing_seeded_lineage() -> None:
    observed = ["fct_royalties"]

    with pytest.raises(RuntimeError, match="artist_payouts"):
        validate_expected_downstream_lineage(observed)
