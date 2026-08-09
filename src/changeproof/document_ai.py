from __future__ import annotations

import json

from openai import OpenAI
from pydantic import BaseModel, Field

from .config import Settings
from .document_ingest import DocumentText
from .triage import MAX_REQUIREMENTS_CHARS, MAX_RULES


class DocumentInterpretation(BaseModel):
    incident_question: str
    requirements: list[str] = Field(default_factory=list)
    summary: str


class DocumentAiUnavailable(RuntimeError):
    """The optional AI interpretation could not provide a safe result."""


def interpret_document(
    document: DocumentText,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> DocumentInterpretation:
    settings = settings or Settings.from_env()
    if not settings.openai_api_key:
        raise DocumentAiUnavailable(
            "OPENAI_API_KEY is not configured for this runtime. "
            "The deterministic document mapping remains available."
        )

    openai_client = client or OpenAI(api_key=settings.openai_api_key)
    try:
        response = openai_client.responses.parse(
            model=settings.changeproof_model,
            instructions=(
                "You are a careful requirements analyst. Extract only requirements and "
                "incident intent explicitly supported by the supplied document text. "
                "Preserve important business nouns, joins, dates, and constraints in each "
                "rule. Do not invent datasets, columns, owners, lineage, metrics, or query "
                "results. Return at most 20 concise ordered rules."
            ),
            input=json.dumps(
                {
                    "filename": document.filename,
                    "media_type": document.media_type,
                    "extracted_text": document.text,
                },
                ensure_ascii=False,
            ),
            text_format=DocumentInterpretation,
            store=False,
            max_output_tokens=900,
        )
    except Exception as exc:
        raise DocumentAiUnavailable(
            f"OpenAI document interpretation could not complete: {type(exc).__name__}. "
            "The deterministic document mapping remains available."
        ) from exc

    interpretation = getattr(response, "output_parsed", None)
    if not isinstance(interpretation, DocumentInterpretation):
        raise DocumentAiUnavailable(
            "OpenAI returned no structured document interpretation. "
            "The deterministic document mapping remains available."
        )
    _validate_interpretation(interpretation)
    return interpretation


def _validate_interpretation(interpretation: DocumentInterpretation) -> None:
    if not interpretation.incident_question.strip():
        raise DocumentAiUnavailable("OpenAI returned an empty incident question.")
    if len(interpretation.incident_question) > MAX_REQUIREMENTS_CHARS:
        raise DocumentAiUnavailable("OpenAI returned an incident question over 20,000 characters.")
    if not interpretation.requirements:
        raise DocumentAiUnavailable("OpenAI returned no document requirements.")
    if len(interpretation.requirements) > MAX_RULES:
        raise DocumentAiUnavailable("OpenAI returned more than the maximum of 20 rules.")
    if any(not rule.strip() for rule in interpretation.requirements):
        raise DocumentAiUnavailable("OpenAI returned an empty document requirement.")
    if sum(len(rule) for rule in interpretation.requirements) > MAX_REQUIREMENTS_CHARS:
        raise DocumentAiUnavailable("OpenAI returned requirements over 20,000 characters.")
