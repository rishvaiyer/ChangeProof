from dataclasses import replace

from .artifacts import build_artifacts
from .demo import DemoAnalysis, analyze_demo_change
from .regions import ASTERVALE_ASSET_REGIONS, assess_regions
from .sql_impact import analyze_sql_modules


def analyze_enterprise_change(
    *, column: str, old_type: str, new_type: str
) -> DemoAnalysis:
    base = analyze_demo_change(column=column, old_type=old_type, new_type=new_type)
    if base.company_name != "AsterVale Living":
        return base

    dependencies = analyze_sql_modules(column, old_type, new_type)
    exposures = assess_regions(base.evidence, dependencies, ASTERVALE_ASSET_REGIONS)
    enriched = replace(
        base,
        sql_dependencies=dependencies,
        region_exposures=exposures,
    )
    return replace(enriched, artifacts=build_artifacts(enriched))
