from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from .classifier import classify_schema_change
from .demo import CATALOG, DemoColumn
from .impact import assess_impact
from .models import (
    ChangeRequest,
    ChangeType,
    Confidence,
    ImpactAssessment,
    MetadataEvidence,
    RemediationPlan,
)
from .planner import plan_remediation

app = typer.Typer(
    add_completion=False,
    help="Evaluate a schema change against bundled synthetic metadata before rollout.",
)

PASS = "VERIFIED_WITHIN_BUNDLED_GRAPH"
REVIEW = "REVIEW_REQUIRED"
BLOCKED = "BLOCKED_INCOMPLETE_EVIDENCE"
UNSUPPORTED = "BLOCKED_UNSUPPORTED_CHANGE"


@app.callback()
def main() -> None:
    """Run deterministic, review-only schema-change checks."""


@dataclass(frozen=True)
class GateEvaluation:
    request: ChangeRequest
    status: str
    passed: bool
    evidence: MetadataEvidence | None
    impact: ImpactAssessment | None
    plan: RemediationPlan | None
    reasons: tuple[str, ...]


def load_change(path: Path) -> ChangeRequest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read schema-change fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Schema-change fixture is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Schema-change fixture must be a JSON object.")
    required = {"before_schema", "after_schema", "source_file"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Schema-change fixture is missing: {', '.join(missing)}")
    if not isinstance(payload["before_schema"], list) or not isinstance(
        payload["after_schema"], list
    ):
        raise ValueError("before_schema and after_schema must be JSON arrays.")
    if not isinstance(payload["source_file"], str) or not payload["source_file"]:
        raise ValueError("source_file must be a non-empty string.")

    return classify_schema_change(
        before_schema=payload["before_schema"],
        after_schema=payload["after_schema"],
        source_file=Path(payload["source_file"]),
        dataset_urn=payload.get("dataset_urn"),
    )


def evaluate_change(path: Path) -> GateEvaluation:
    request = load_change(path)
    if request.change_type is ChangeType.UNSUPPORTED:
        return GateEvaluation(
            request=request,
            status=UNSUPPORTED,
            passed=False,
            evidence=None,
            impact=None,
            plan=None,
            reasons=(
                "The fixture contains a change shape the deterministic planner does not support.",
            ),
        )

    entry = _catalog_entry(request)
    if entry is None:
        field = request.old_column or request.new_column or "unknown"
        return GateEvaluation(
            request=request,
            status=BLOCKED,
            passed=False,
            evidence=None,
            impact=None,
            plan=None,
            reasons=(
                f"No bundled synthetic evidence matches field `{field}` and its dataset.",
                "Absence from the bundled graph is not proof that downstream "
                "consumers do not exist.",
            ),
        )

    evidence = _metadata_evidence(entry)
    impact = assess_impact(evidence)
    plan = plan_remediation(request, impact)
    passed = (
        impact.confidence is Confidence.HIGH
        and plan.supported_automatically
        and not plan.requires_approval
    )
    status = PASS if passed else REVIEW
    reasons = tuple(impact.reasons)
    if not passed:
        reasons = (
            *reasons,
            "The proposed change remains review-gated; no SQL or metadata write was executed.",
        )
    return GateEvaluation(
        request=request,
        status=status,
        passed=passed,
        evidence=evidence,
        impact=impact,
        plan=plan,
        reasons=reasons,
    )


def _catalog_entry(request: ChangeRequest) -> DemoColumn | None:
    field = request.old_column or request.new_column
    entry = CATALOG.get(field or "")
    if entry is None:
        return None
    if request.dataset_urn and request.dataset_urn != entry.source_urn:
        return None
    return entry


def _metadata_evidence(entry: DemoColumn) -> MetadataEvidence:
    return MetadataEvidence(
        source_urn=entry.source_urn,
        source_field=entry.column,
        column_lineage_available=entry.column_lineage_available,
        downstream=list(entry.downstream),
        owners=list(entry.owners),
        assertions_passing=True,
        metadata_age_hours=entry.metadata_age_hours,
        missing=list(entry.missing),
    )


def markdown_report(result: GateEvaluation, fixture: Path) -> str:
    request = result.request
    impact = result.impact
    plan = result.plan
    lines = [
        "# contextIsKey schema-change gate",
        "",
        f"- Status: `{result.status}`",
        "- Evidence mode: `bundled-synthetic-datahub-shaped-metadata`",
        "- External calls: `none`",
        "- SQL execution: `none`",
        f"- Fixture: `{fixture.as_posix()}`",
        f"- Change type: `{request.change_type.value}`",
        f"- Source file: `{request.source_file.as_posix()}`",
        f"- Dataset: `{request.dataset_urn or 'unverified'}`",
        f"- Field: `{request.old_column or 'unknown'}` -> `{request.new_column or 'removed'}`",
        "",
        "## Decision evidence",
        "",
    ]
    lines.extend(f"- {reason}" for reason in result.reasons)
    if impact is not None:
        lines.extend(
            [
                f"- Confidence: `{impact.confidence.value}`",
                f"- Observed downstream assets: `{len(impact.impacted_assets)}`",
                "- Required reviewers: "
                f"`{', '.join(impact.required_reviewers) or 'none observed'}`",
            ]
        )
    if plan is not None:
        lines.extend(
            [
                "",
                "## Reviewable plan",
                "",
                f"- Strategy: `{plan.strategy}`",
                f"- Human approval required: `{str(plan.requires_approval).lower()}`",
                f"- Summary: {plan.summary}",
                "",
                "### Rollout",
                "",
            ]
        )
        lines.extend(f"{index}. {step}" for index, step in enumerate(plan.rollout_steps, 1))
        lines.extend(["", "### Rollback", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(plan.rollback_steps, 1))
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- This result is limited to the bundled synthetic graph.",
            "- Generated guidance is review material, not an execution receipt.",
            "- The gate does not execute SQL, contact DataHub, or perform write-back.",
            "",
        ]
    )
    return "\n".join(lines)


def sarif_report(result: GateEvaluation) -> dict[str, Any]:
    message = "; ".join(result.reasons)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "contextIsKey schema-change gate",
                        "version": "0.1.0",
                        "rules": [
                            {
                                "id": "contextiskey/schema-change-gate",
                                "shortDescription": {
                                    "text": (
                                        "Review schema changes against observed "
                                        "metadata evidence"
                                    )
                                },
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "contextiskey/schema-change-gate",
                        "level": "note" if result.passed else "error",
                        "message": {"text": f"{result.status}: {message}"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {
                                        "uri": result.request.source_file.as_posix()
                                    }
                                }
                            }
                        ],
                        "properties": {
                            "status": result.status,
                            "evidenceMode": "bundled-synthetic-datahub-shaped-metadata",
                            "syntheticOnly": True,
                            "sqlExecuted": False,
                        },
                    }
                ],
            }
        ],
    }


def write_reports(result: GateEvaluation, fixture: Path, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "contextiskey-gate.md"
    sarif_path = output_dir / "contextiskey-gate.sarif"
    markdown_path.write_text(markdown_report(result, fixture), encoding="utf-8")
    sarif_path.write_text(
        json.dumps(sarif_report(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return markdown_path, sarif_path


@app.command()
def gate(
    fixture: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("gate-output"),
) -> None:
    """Evaluate one schema-change fixture using bundled synthetic evidence."""
    try:
        result = evaluate_change(fixture)
        markdown_path, sarif_path = write_reports(result, fixture, output_dir)
    except ValueError as exc:
        typer.echo(f"contextIsKey gate input error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(result.status)
    typer.echo(f"Markdown: {markdown_path}")
    typer.echo(f"SARIF: {sarif_path}")
    if not result.passed:
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
