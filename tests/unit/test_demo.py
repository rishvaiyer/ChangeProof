import pytest

from changeproof.demo import analyze_demo_change
from changeproof.models import ChangeType, Confidence


def test_analyze_demo_type_change_returns_impact_and_safe_plan() -> None:
    result = analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")

    assert result.request.change_type is ChangeType.COLUMN_TYPE_CHANGE
    assert result.impact.confidence is Confidence.HIGH
    assert [asset.name for asset in result.impact.impacted_assets] == [
        "fct_royalties",
        "artist_payouts",
        "finance_royalty_dashboard",
    ]
    assert result.plan.strategy == "parallel_typed_field"
    assert result.plan.rollout_steps


def test_analyze_demo_rejects_unknown_column() -> None:
    with pytest.raises(ValueError, match="Supported demo column: artist_id"):
        analyze_demo_change(column="unknown", old_type="varchar", new_type="bigint")
