from .config import Settings
from .demo import SOURCE_URN, DemoAnalysis, build_demo_request, compose_analysis
from .mcp_client import DataHubMcpClient


def analyze_live_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis:
    request = build_demo_request(column=column, old_type=old_type, new_type=new_type)
    evidence = DataHubMcpClient(Settings.from_env()).get_downstream_context(
        source_urn=SOURCE_URN,
        source_field="artist_id",
    )
    return compose_analysis(
        request=request,
        evidence=evidence,
        evidence_source="Live DataHub MCP evidence",
    )
