from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from mcp.types import EmbeddedResource, TextContent, TextResourceContents

from changeproof.config import Settings
from changeproof.mcp_client import DataHubMcpClient

SOURCE_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"
PAYOUTS_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.artist_payouts,PROD)"
)
ROYALTIES_URN = (
    "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.fct_royalties,PROD)"
)
FAR_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.marts.far_asset,PROD)"


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeToolListResult:
    def __init__(self, names: list[str]) -> None:
        self.tools = [FakeTool(name) for name in names]


class FakeCallToolResult:
    def __init__(
        self,
        *,
        structured_content: object | None = None,
        content: list[object] | None = None,
        is_error: bool = False,
    ) -> None:
        self.structured_content = structured_content
        self.content = content or []
        self.is_error = is_error


class FakeSession:
    def __init__(
        self,
        *,
        tool_names: list[str],
        tool_results: dict[str, FakeCallToolResult],
    ) -> None:
        self._tool_names = tool_names
        self._tool_results = tool_results
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def list_tools(self) -> FakeToolListResult:
        return FakeToolListResult(self._tool_names)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
        **_: object,
    ) -> FakeCallToolResult:
        self.calls.append((name, arguments))
        return self._tool_results[name]


def build_client(session: FakeSession) -> DataHubMcpClient:
    @asynccontextmanager
    async def session_factory() -> AsyncIterator[FakeSession]:
        yield session

    return DataHubMcpClient(
        settings=Settings(
            datahub_gms_url="http://localhost:8080",
            datahub_gms_token="",
        ),
        session_factory=session_factory,
    )


def test_get_downstream_context_normalizes_fake_mcp_content_blocks() -> None:
    lineage_payload = {
        "downstreams": {
            "searchResults": [
                {
                    "entity": {
                        "urn": PAYOUTS_URN,
                        "type": "DATASET",
                        "name": "artist_payouts",
                    },
                    "degree": 2,
                    "lineageColumns": ["rights_holder_id"],
                }
            ]
        }
    }
    entities_payload = [
        {
            "urn": SOURCE_URN,
            "ownership": {
                "owners": [
                    {
                        "owner": {
                            "properties": {
                                "email": "analytics@sonicledger.demo",
                            }
                        }
                    }
                ]
            },
        },
        {
            "urn": PAYOUTS_URN,
            "ownership": {
                "owners": [
                    {
                        "owner": {
                            "properties": {
                                "email": "finance@sonicledger.demo",
                            }
                        }
                    }
                ]
            },
            "globalTags": {
                "tags": [
                    {
                        "tag": {
                            "properties": {
                                "name": "critical",
                            }
                        }
                    }
                ]
            },
        },
    ]
    session = FakeSession(
        tool_names=["list_schema_fields", "get_lineage", "get_entities"],
        tool_results={
            "list_schema_fields": FakeCallToolResult(
                structured_content={
                    "urn": SOURCE_URN,
                    "fields": [
                        {"fieldPath": "artist_id", "nativeDataType": "varchar"},
                        {"fieldPath": "track_id", "nativeDataType": "varchar"},
                    ],
                }
            ),
            "get_lineage": FakeCallToolResult(
                content=[TextContent(type="text", text=json.dumps(lineage_payload))]
            ),
            "get_entities": FakeCallToolResult(
                content=[
                    EmbeddedResource(
                        type="resource",
                        resource=TextResourceContents(
                            uri="file:///tmp/entities.json",
                            mime_type="application/json",
                            text=json.dumps(entities_payload),
                        ),
                    )
                ]
            ),
        },
    )

    evidence = build_client(session).get_downstream_context(
        source_urn=SOURCE_URN,
        source_field="artist_id",
    )

    assert evidence.source_urn.endswith("stg_streams,PROD)")
    assert evidence.source_field == "artist_id"
    assert evidence.column_lineage_available is True
    assert evidence.owners == ["analytics@sonicledger.demo"]
    assert [node.name for node in evidence.downstream] == ["artist_payouts"]
    assert evidence.downstream[0].fields == ["rights_holder_id"]
    assert evidence.downstream[0].owners == ["finance@sonicledger.demo"]
    assert evidence.downstream[0].critical is True
    assert session.calls == [
        (
            "list_schema_fields",
            {
                "urn": SOURCE_URN,
            },
        ),
        (
            "get_lineage",
            {
                "urn": SOURCE_URN,
                "column": "artist_id",
                "upstream": False,
                "max_hops": 3,
            },
        ),
        (
            "get_entities",
            {"urns": [SOURCE_URN, PAYOUTS_URN]},
        ),
    ]


def test_get_downstream_context_keeps_table_lineage_when_column_lineage_is_missing() -> None:
    session = FakeSession(
        tool_names=["list_schema_fields", "get_lineage", "get_entities"],
        tool_results={
            "list_schema_fields": FakeCallToolResult(
                structured_content={
                    "urn": SOURCE_URN,
                    "fields": [{"fieldPath": "artist_id", "nativeDataType": "varchar"}],
                }
            ),
            "get_lineage": FakeCallToolResult(
                structured_content={
                    "downstreams": {
                        "searchResults": [
                            {
                                "entity": {
                                    "urn": ROYALTIES_URN,
                                    "type": "DATASET",
                                    "name": "fct_royalties",
                                },
                                "degree": 1,
                            }
                        ]
                    }
                }
            ),
            "get_entities": FakeCallToolResult(
                structured_content=[
                    {"urn": SOURCE_URN},
                    {"urn": ROYALTIES_URN},
                ]
            ),
        },
    )

    evidence = build_client(session).get_downstream_context(
        source_urn=SOURCE_URN,
        source_field="artist_id",
    )

    assert evidence.column_lineage_available is False
    assert evidence.missing == ["column_lineage"]
    assert [node.name for node in evidence.downstream] == ["fct_royalties"]
    assert evidence.downstream[0].fields == []


def test_get_downstream_context_bounds_official_three_plus_degree_as_hop_three() -> None:
    session = FakeSession(
        tool_names=["list_schema_fields", "get_lineage", "get_entities"],
        tool_results={
            "list_schema_fields": FakeCallToolResult(
                structured_content={
                    "urn": SOURCE_URN,
                    "fields": [{"fieldPath": "artist_id", "nativeDataType": "varchar"}],
                }
            ),
            "get_lineage": FakeCallToolResult(
                structured_content={
                    "downstreams": {
                        "searchResults": [
                            {
                                "entity": {
                                    "urn": PAYOUTS_URN,
                                    "type": "DATASET",
                                    "name": "artist_payouts",
                                },
                                "degree": "3+",
                                "lineageColumns": ["artist_id"],
                            },
                            {
                                "entity": {
                                    "urn": FAR_URN,
                                    "type": "DATASET",
                                    "name": "far_asset",
                                },
                                "degree": 4,
                                "lineageColumns": ["artist_id"],
                            },
                        ]
                    }
                }
            ),
            "get_entities": FakeCallToolResult(
                structured_content=[
                    {"urn": SOURCE_URN},
                    {"urn": PAYOUTS_URN},
                    {"urn": FAR_URN},
                ]
            ),
        },
    )

    evidence = build_client(session).get_downstream_context(
        source_urn=SOURCE_URN,
        source_field="artist_id",
    )

    assert [(node.name, node.hop) for node in evidence.downstream] == [("artist_payouts", 3)]
    assert all(1 <= node.hop <= 3 for node in evidence.downstream)


def test_get_downstream_context_rejects_missing_required_tools() -> None:
    session = FakeSession(
        tool_names=["list_schema_fields", "get_lineage"],
        tool_results={},
    )

    with pytest.raises(ValueError, match="Missing required DataHub MCP tools: get_entities"):
        build_client(session).get_downstream_context(
            source_urn=SOURCE_URN,
            source_field="artist_id",
        )
