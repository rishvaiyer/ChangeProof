import hashlib
import json
import re

from openai import OpenAI

from .config import Settings
from .demo import DemoAnalysis
from .models import AiReview

_CACHE: dict[str, AiReview] = {}


class AiReviewUnavailable(RuntimeError):
    pass


def review_analysis(
    analysis: DemoAnalysis,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> AiReview:
    settings = settings or Settings.from_env()
    if not settings.openai_api_key:
        raise AiReviewUnavailable(
            "OPENAI_API_KEY is not configured for this runtime. "
            "The deterministic fixes remain available."
        )

    payload = _evidence_payload(analysis)
    payload_json = json.dumps(payload, sort_keys=True)
    cache_key = hashlib.sha256(
        f"{settings.changeproof_model}:{payload_json}".encode()
    ).hexdigest()
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    openai_client = client or OpenAI(api_key=settings.openai_api_key)
    try:
        response = openai_client.responses.parse(
            model=settings.changeproof_model,
            instructions=(
                "You are a senior enterprise data migration reviewer. Review only "
                "the supplied deterministic synthetic evidence. Explain the safest "
                "fixes and unresolved risks. Do not invent assets, dependencies, "
                "regions, execution results, or compliance claims."
                " Put every asset, SQL object, field, region, and type identifier "
                "inside backticks so grounding can be validated."
            ),
            input=payload_json,
            text_format=AiReview,
            store=False,
            max_output_tokens=700,
        )
    except Exception as exc:
        raise AiReviewUnavailable(
            f"OpenAI review could not complete: {type(exc).__name__}. "
            "The deterministic analysis is still available."
        ) from exc

    result = response.output_parsed
    if not isinstance(result, AiReview):
        raise AiReviewUnavailable(
            "OpenAI returned no structured review. The deterministic analysis is unchanged."
        )
    _validate_grounding(result, analysis)
    _CACHE[cache_key] = result
    return result


def _validate_grounding(review: AiReview, analysis: DemoAnalysis) -> None:
    allowed = {
        analysis.source_label,
        analysis.source_table,
        analysis.evidence.source_field,
        analysis.request.old_type or "",
        analysis.request.new_type or "",
        analysis.plan.strategy,
    }
    allowed.update(asset.name for asset in analysis.impact.impacted_assets)
    allowed.update(item.region for item in analysis.region_exposures)
    for item in analysis.sql_dependencies:
        allowed.add(item.object_name)
        allowed.add(f"{item.schema_name}.{item.object_name}")

    text = "\n".join(
        [review.summary, *review.fix_notes, *review.unresolved_risks]
    )
    unsupported = sorted(set(re.findall(r"`([^`]+)`", text)) - allowed)
    if unsupported:
        raise AiReviewUnavailable(
            f"OpenAI referenced an unsupported identifier: {unsupported[0]}. "
            "The deterministic analysis is unchanged."
        )


def _evidence_payload(analysis: DemoAnalysis) -> dict[str, object]:
    return {
        "company": analysis.company_name,
        "change": {
            "source": analysis.source_label,
            "column": analysis.evidence.source_field,
            "old_type": analysis.request.old_type,
            "new_type": analysis.request.new_type,
        },
        "datahub": {
            "confidence": analysis.impact.confidence.value,
            "assets": [
                {
                    "name": asset.name,
                    "hop": asset.hop,
                    "critical": asset.critical,
                    "owners": asset.owners,
                }
                for asset in analysis.impact.impacted_assets
            ],
        },
        "sql_dependencies": [
            {
                "object": f"{item.schema_name}.{item.object_name}",
                "match": item.match_kind.value,
                "confidence": item.confidence.value,
                "regions": item.regions,
                "has_generated_fix": item.proposed_sql is not None,
                "manual_review_reason": item.manual_review_reason,
            }
            for item in analysis.sql_dependencies
        ],
        "regions": [item.model_dump(mode="json") for item in analysis.region_exposures],
        "rollout": analysis.plan.rollout_steps,
        "rollback": analysis.plan.rollback_steps,
        "unresolved_risks": analysis.plan.unresolved_risks,
    }
