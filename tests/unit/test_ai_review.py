import json
from types import SimpleNamespace

import pytest

from changeproof.ai_review import AiReviewUnavailable, review_analysis
from changeproof.config import Settings
from changeproof.enterprise import analyze_enterprise_change
from changeproof.models import AiReview


class FakeResponses:
    def parse(self, **kwargs):
        payload = json.loads(kwargs["input"])
        assert payload["company"] == "AsterVale Living"
        assert payload["change"]["column"] == "customer_id"
        assert "api_key" not in json.dumps(payload).lower()
        assert kwargs["store"] is False
        assert kwargs["text_format"] is AiReview
        return SimpleNamespace(
            output_parsed=AiReview(
                summary="The compatibility-field rollout is well supported by the evidence.",
                fix_notes=["Review the dynamic export procedure with its owner."],
                unresolved_risks=["One SQL module has unknown region metadata."],
            )
        )


class FakeOpenAI:
    responses = FakeResponses()


class UngroundedResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(
            output_parsed=AiReview(
                summary="Update `invented_customer_table` before rollout.",
            )
        )


class UngroundedOpenAI:
    responses = UngroundedResponses()


def _analysis():
    return analyze_enterprise_change(
        column="customer_id", old_type="varchar", new_type="bigint"
    )


def test_review_requires_a_configured_key() -> None:
    with pytest.raises(AiReviewUnavailable, match="OPENAI_API_KEY"):
        review_analysis(_analysis(), settings=Settings(openai_api_key=""))


def test_review_returns_structured_bounded_analysis() -> None:
    result = review_analysis(
        _analysis(),
        settings=Settings(openai_api_key="configured"),
        client=FakeOpenAI(),
    )

    assert result.status == "AI_REVIEWED"
    assert "compatibility-field" in result.summary
    assert result.fix_notes == ["Review the dynamic export procedure with its owner."]


def test_review_rejects_an_identifier_absent_from_the_evidence() -> None:
    with pytest.raises(AiReviewUnavailable, match="unsupported identifier"):
        review_analysis(
            _analysis(),
            settings=Settings(
                openai_api_key="configured", CHANGE_PROOF_MODEL="grounding-test"
            ),
            client=UngroundedOpenAI(),
        )
