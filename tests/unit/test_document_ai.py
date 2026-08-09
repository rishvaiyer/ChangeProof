from __future__ import annotations

from dataclasses import dataclass

import pytest

from changeproof.config import Settings
from changeproof.document_ai import (
    DocumentAiUnavailable,
    DocumentInterpretation,
    interpret_document,
)
from changeproof.document_ingest import DocumentText

DOCUMENT = DocumentText("incident.txt", "text/plain", "Compare invoices with settlements.", 36)


@dataclass
class FakeResponse:
    output_parsed: object


class FakeResponses:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> FakeResponse:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


def test_interpret_document_requires_an_api_key() -> None:
    with pytest.raises(DocumentAiUnavailable, match="OPENAI_API_KEY"):
        interpret_document(DOCUMENT, Settings(openai_api_key=""))


def test_interpret_document_returns_structured_rules_without_sending_binary_data() -> None:
    parsed = DocumentInterpretation(
        incident_question="Why do invoice and settlement totals differ?",
        requirements=["Compare invoice totals", "Compare settlement totals"],
        summary="Compare the two financial sources in event order.",
    )
    responses = FakeResponses(FakeResponse(parsed))

    result = interpret_document(
        DOCUMENT,
        Settings(openai_api_key="sk-test"),
        FakeClient(responses),
    )

    assert result == parsed
    payload = responses.calls[0]
    assert DOCUMENT.text in str(payload["input"])
    assert DOCUMENT.filename in str(payload["input"])
    assert "bytes" not in str(payload["input"])
    assert payload["store"] is False


def test_interpret_document_rejects_more_than_twenty_returned_rules() -> None:
    parsed = DocumentInterpretation(
        incident_question="Investigate",
        requirements=[f"Rule {index}" for index in range(21)],
        summary="Too many rules.",
    )
    responses = FakeResponses(FakeResponse(parsed))

    with pytest.raises(DocumentAiUnavailable, match="20 rules"):
        interpret_document(DOCUMENT, Settings(openai_api_key="sk-test"), FakeClient(responses))


def test_interpret_document_converts_provider_errors() -> None:
    responses = FakeResponses(error=RuntimeError("provider down"))

    with pytest.raises(DocumentAiUnavailable, match="could not complete"):
        interpret_document(DOCUMENT, Settings(openai_api_key="sk-test"), FakeClient(responses))
