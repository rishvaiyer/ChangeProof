from __future__ import annotations

import json
import re

from openai import OpenAI
from pydantic import BaseModel, Field

from .config import Settings
from .triage import TriageResult


class AiTriageReview(BaseModel):
    summary: str
    explain_like_five: str
    query_risks: list[str] = Field(default_factory=list)
    missing_questions: list[str] = Field(default_factory=list)


class TriageAiUnavailable(RuntimeError):
    pass


def review_triage(
    result: TriageResult,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> AiTriageReview:
    settings = settings or Settings.from_env()
    if not settings.openai_api_key:
        raise TriageAiUnavailable(
            "OPENAI_API_KEY is not configured for this runtime. "
            "The deterministic triage result remains available."
        )

    payload = _evidence_payload(result)
    payload_json = json.dumps(payload, sort_keys=True)

    openai_client = client or OpenAI(api_key=settings.openai_api_key)
    try:
        response = openai_client.responses.parse(
            model=settings.changeproof_model,
            instructions=(
                "You are a careful incident triage reviewer. Review only the supplied "
                "bounded extracted rules and mapped synthetic evidence. Explain the "
                "triage plainly, identify query risks, and ask only useful missing "
                "questions. Do not invent assets, columns, domains, dependencies, "
                "owners, or execution results. Put every asset, column, and domain "
                "identifier inside backticks so grounding can be validated."
            ),
            input=payload_json,
            text_format=AiTriageReview,
            store=False,
            max_output_tokens=700,
        )
    except Exception as exc:
        raise TriageAiUnavailable(
            f"OpenAI triage review could not complete: {type(exc).__name__}. "
            "The deterministic triage result is still available."
        ) from exc

    review = response.output_parsed
    if not isinstance(review, AiTriageReview):
        raise TriageAiUnavailable(
            "OpenAI returned no structured triage review. "
            "The deterministic triage result is unchanged."
        )
    _validate_grounding(review, result)
    return review


def _evidence_payload(result: TriageResult) -> dict[str, object]:
    return {
        "rules": [
            {
                "number": rule.number,
                "text": rule.text,
                "status": rule.status,
                "domain": rule.domain,
                "asset_urn": rule.asset_urn,
                "columns": list(rule.columns),
                "owner": rule.owner,
                "glossary": rule.glossary,
                "reason": rule.reason,
            }
            for rule in result.rules
        ],
        "mappings": [
            {
                "number": rule.number,
                "domain": rule.domain,
                "asset_urn": rule.asset_urn,
                "columns": list(rule.columns),
                "owner": rule.owner,
                "glossary": rule.glossary,
            }
            for rule in result.mappings
            if rule.status == "MAPPED"
        ],
        "mapped_evidence": {
            "domains": list(result.domains),
            "datahub_steps": [
                {
                    "number": step.number,
                    "operation": step.operation,
                    "query_decision": step.query_decision,
                }
                for step in result.datahub_steps
            ],
            "warnings": list(result.warnings),
            "evidence_mode": result.evidence_mode,
        },
    }


def _validate_grounding(review: AiTriageReview, result: TriageResult) -> None:
    allowed: set[str] = set(result.domains)
    for rule in result.mappings:
        if rule.status != "MAPPED":
            continue
        allowed.update(rule.columns)
        if rule.asset_urn:
            allowed.add(rule.asset_urn)
            asset_name = (
                rule.asset_urn.rsplit(",", 2)[-2]
                if "," in rule.asset_urn
                else rule.asset_urn
            )
            allowed.add(asset_name.removeprefix("astervale.").rstrip(")"))

    text = "\n".join(
        [review.summary, review.explain_like_five, *review.query_risks, *review.missing_questions]
    )
    identifiers = _backtick_identifiers(text)
    unsupported = sorted(set(identifiers) - allowed)
    if unsupported:
        raise TriageAiUnavailable(
            f"OpenAI referenced an unsupported identifier: {unsupported[0]}. "
            "The deterministic triage result is unchanged."
        )


def _backtick_identifiers(text: str) -> list[str]:
    if text.count("`") % 2:
        raise TriageAiUnavailable(
            "OpenAI returned an unsupported identifier with an unclosed backtick. "
            "The deterministic triage result is unchanged."
        )
    return re.findall(r"`([^`]+)`", text)
