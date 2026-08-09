from .config import Settings
from .demo import DemoAnalysis, build_demo_request, compose_analysis, resolve_column
from .mcp_client import DataHubMcpClient


def analyze_live_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis:
    request = build_demo_request(column=column, old_type=old_type, new_type=new_type)
    entry = resolve_column(column)
    evidence = DataHubMcpClient(Settings.from_env()).get_downstream_context(
        source_urn=entry.source_urn,
        source_field=entry.column,
    )
    return compose_analysis(
        request=request,
        evidence=evidence,
        evidence_source="Live DataHub MCP evidence",
        company_name=entry.company_name,
        platform_name=entry.platform_name,
    )
