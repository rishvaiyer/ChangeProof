# Task 2 report: Optional grounded AI triage review

## Status

Implemented Task 2 as a new optional AI review boundary for Task 1's `TriageResult`.

## Changes

- Added `src/changeproof/triage_ai.py`.
  - Defines structured `AiTriageReview` output with `summary`, `explain_like_five`, `query_risks`, and `missing_questions`.
  - Exposes `review_triage(result, settings=None, client=None)`.
  - Requires `OPENAI_API_KEY` and raises `TriageAiUnavailable` when unavailable or when the review cannot be safely used.
  - Uses the OpenAI Responses API `parse` path with `text_format=AiTriageReview`, `store=False`, bounded instructions, and a caller-injectable client.
  - Caches successful reviews by model and deterministic bounded-evidence payload.
  - Sends extracted rule text, mapped rule evidence, domains, DataHub steps, warnings, and evidence mode only. It does not serialize an original requirements-document field or any API key.
  - Validates every backtick-delimited output token against mapped asset URNs/full names, mapped columns, and mapped domains.
- Added `tests/unit/test_triage_ai.py` with structured fake clients only.
  - Configured-key requirement.
  - Structured output and bounded payload assertions.
  - `store=False`, typed response format, and API-key exclusion assertions.
  - Unsupported identifier rejection.

## Verification

- RED: `uv run pytest tests/unit/test_triage_ai.py -q` initially failed during collection with `ModuleNotFoundError: No module named 'changeproof.triage_ai'`.
- GREEN: `uv run pytest tests/unit/test_triage_ai.py -q` passed: `3 passed`.

## Fix round 1: malformed backtick grounding

- Root cause: the grounding regex extracted only closed backtick pairs, so an unclosed unsupported identifier could produce no extracted token and bypass validation.
- RED: after adding `test_review_rejects_an_unclosed_unsupported_identifier`, `uv run pytest tests/unit/test_triage_ai.py -q` failed with `1 failed, 3 passed` because no `TriageAiUnavailable` was raised.
- GREEN: added balanced-delimiter validation before identifier extraction; `uv run pytest tests/unit/test_triage_ai.py -q` passed: `4 passed`.
- Valid closed-backtick grounding remains covered by the existing structured-output and unsupported-identifier tests.

## Concerns

- The review is optional and remains unavailable without a configured key; deterministic triage remains the fallback.
- This task does not make a live API call or claim that generated SQL was executed.
