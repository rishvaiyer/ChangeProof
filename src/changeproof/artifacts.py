import json

from .demo import DemoAnalysis
from .models import ArtifactBundle
from .sql_impact import build_discovery_query


def build_artifacts(analysis: DemoAnalysis) -> ArtifactBundle:
    column = analysis.request.old_column or analysis.evidence.source_field
    old_type = analysis.request.old_type or "unknown"
    new_type = analysis.request.new_type or "unknown"

    report = {
        "company": analysis.company_name,
        "change": {
            "column": column,
            "current_type": old_type,
            "proposed_type": new_type,
            "source": analysis.source_label,
        },
        "evidence": {
            "source": analysis.evidence_source,
            "confidence": analysis.impact.confidence.value,
            "datahub_assets": len(analysis.impact.impacted_assets),
            "hidden_sql_objects": len(analysis.sql_dependencies),
            "regions": len(analysis.region_exposures),
        },
        "affected_assets": [
            {
                "name": asset.name,
                "hop": asset.hop,
                "critical": asset.critical,
                "owners": asset.owners,
            }
            for asset in analysis.impact.impacted_assets
        ],
        "sql_dependencies": [item.model_dump(mode="json") for item in analysis.sql_dependencies],
        "regional_exposure": [item.model_dump(mode="json") for item in analysis.region_exposures],
        "unresolved_risks": analysis.plan.unresolved_risks
        + [
            item.manual_review_reason
            for item in analysis.sql_dependencies
            if item.manual_review_reason
        ],
    }

    return ArtifactBundle(
        impact_report_json=json.dumps(report, indent=2, sort_keys=True),
        discovery_query_sql=build_discovery_query(column),
        proposed_fixes_sql=_proposed_fixes(analysis),
        validation_queries_sql=_validation_queries(analysis),
        rollback_sql=_rollback(analysis),
        sarif_json=json.dumps(_sarif(analysis), indent=2, sort_keys=True),
    )


def _proposed_fixes(analysis: DemoAnalysis) -> str:
    sections = [
        "-- ChangeProof generated review draft",
        "-- No statement in this file has been executed.",
    ]
    for item in analysis.sql_dependencies:
        sections.extend(
            [
                "",
                f"-- {item.schema_name}.{item.object_name} [{item.confidence.value}]",
            ]
        )
        if item.proposed_sql:
            sections.append(item.proposed_sql)
        else:
            sections.append(
                f"-- MANUAL REVIEW: {item.manual_review_reason or 'No safe rewrite generated.'}"
            )
            sections.append(f"-- Original: {item.snippet}")
    return "\n".join(sections) + "\n"


def _validation_queries(analysis: DemoAnalysis) -> str:
    table = analysis.source_table
    column = analysis.evidence.source_field
    return f"""-- Validate conversion coverage before cutover
SELECT
    COUNT_BIG(*) AS total_rows,
    SUM(CASE WHEN {column} IS NOT NULL AND TRY_CONVERT(BIGINT, {column}) IS NULL
        THEN 1 ELSE 0 END) AS conversion_failures
FROM {table};

-- Validate downstream null and key behavior after migration
SELECT {column}, COUNT_BIG(*) AS row_count
FROM {table}
GROUP BY {column}
HAVING {column} IS NULL;
"""


def _rollback(analysis: DemoAnalysis) -> str:
    column = analysis.evidence.source_field
    return f"""-- ROLLBACK RUNBOOK, owner approval required
-- 1. Keep the original {column} VARCHAR contract available during rollout.
-- 2. Route consumers back to the original field or compatibility view.
-- 3. Revert stored procedure drafts in reverse dependency order.
-- 4. Re-run validation queries and confirm regional owners have recovered.
"""


def _sarif(analysis: DemoAnalysis) -> dict[str, object]:
    results = []
    for item in analysis.sql_dependencies:
        results.append(
            {
                "ruleId": f"changeproof/{item.match_kind.value}",
                "level": "warning" if item.manual_review_reason else "note",
                "message": {
                    "text": item.manual_review_reason
                    or f"Review generated {item.match_kind.value} migration fix."
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {
                                "uri": f"database://{item.schema_name}/{item.object_name}"
                            }
                        }
                    }
                ],
                "properties": {"confidence": item.confidence.value},
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "ChangeProof", "version": "0.1.0"}},
                "results": results,
            }
        ],
    }
