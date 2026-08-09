import json
from types import SimpleNamespace

import pytest

from changeproof.config import Settings
from changeproof.triage import SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT, build_triage_result
from changeproof.triage_ai import AiTriageReview, TriageAiUnavailable, review_triage


class FakeResponses:
    def parse(self, **kwargs):
        payload = json.loads(kwargs["input"])
        assert payload["rules"][0]["text"]
        assert payload["mappings"]
        assert payload["mapped_evidence"]
        assert "requirements_text" not in payload
        assert "original_document" not in payload
        assert "api_key" not in json.dumps(payload).lower()
        assert kwargs["store"] is False
        assert kwargs["text_format"] is AiTriageReview
        return SimpleNamespace(
            output_parsed=AiTriageReview(
                summary="The mapped AR rules point to `finance.ar_transactions`.",
                explain_like_five="We compare the mapped `Finance` records with their evidence.",
                query_risks=["The `amount` column needs validation."],
                missing_questions=["Who owns `finance.ar_transactions`?"],
            )
        )


class FakeOpenAI:
    responses = FakeResponses()


class UngroundedResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(
            output_parsed=AiTriageReview(
                summary="Investigate `invented.asset` before proceeding.",
                explain_like_five="The evidence needs review.",
            )
        )


class UngroundedOpenAI:
    responses = UngroundedResponses()


def _result():
    return build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)


def test_review_requires_a_configured_key():
    with pytest.raises(TriageAiUnavailable, match="OPENAI_API_KEY"):
        review_triage(_result(), settings=Settings(openai_api_key=""))


def test_review_returns_structured_grounded_output_from_bounded_evidence():
    result = review_triage(
        _result(),
        settings=Settings(openai_api_key="configured"),
        client=FakeOpenAI(),
    )

    assert isinstance(result, AiTriageReview)
    assert result.summary == "The mapped AR rules point to `finance.ar_transactions`."
    assert result.query_risks == ["The `amount` column needs validation."]


def test_review_rejects_an_identifier_absent_from_mapped_assets_columns_or_domains():
    with pytest.raises(TriageAiUnavailable, match="unsupported identifier"):
        review_triage(
            _result(),
            settings=Settings(openai_api_key="configured", CHANGE_PROOF_MODEL="grounding-test"),
            client=UngroundedOpenAI(),
        )
