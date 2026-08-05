from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import Settings
from .models import LineageNode, MetadataEvidence

REQUIRED_DATAHUB_TOOLS = frozenset({"get_lineage", "list_schema_fields"})
DATAHUB_LINEAGE_MAX_HOPS = 3

SessionFactory = Callable[[], AsyncIterator[Any]]


class DataHubMcpClient:
    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory or self._open_session

    def get_downstream_context(
        self,
        *,
        source_urn: str,
        source_field: str,
    ) -> MetadataEvidence:
        return anyio.run(self.get_downstream_context_async, source_urn, source_field)

    async def get_downstream_context_async(
        self,
        source_urn: str,
        source_field: str,
    ) -> MetadataEvidence:
        async with self._session_factory() as session:
            await self._verify_required_tools(session)

            schema_payload = await self._call_tool(
                session,
                "list_schema_fields",
                {"urn": source_urn},
            )
            field_names = {
                field_name
                for field_name in (
                    self._field_name(field) for field in self._as_list(schema_payload.get("fields"))
                )
                if field_name is not None
            }

            lineage_payload = await self._call_tool(
                session,
                "get_lineage",
                {
                    "urn": source_urn,
                    "column": source_field,
                    "upstream": False,
                    "max_hops": 3,
                },
            )
            search_results = self._as_list(
                (lineage_payload.get("downstreams") or {}).get("searchResults")
            )
            bounded_results = [
                (result, hop)
                for result in search_results
                if isinstance(result, Mapping)
                for hop in [self._hop(result.get("degree"))]
                if hop <= DATAHUB_LINEAGE_MAX_HOPS
            ]

            downstream_nodes: list[LineageNode] = []
            column_lineage_available = False
            for result, hop in bounded_results:
                entity = result.get("entity")
                if not isinstance(entity, Mapping):
                    continue

                entity_urn = self._entity_urn(entity)
                if entity_urn is None:
                    continue

                lineage_columns = self._lineage_columns(result)
                if lineage_columns:
                    column_lineage_available = True

                downstream_nodes.append(
                    LineageNode(
                        urn=entity_urn,
                        name=self._entity_name(entity, fallback_urn=entity_urn),
                        entity_type=self._entity_type(entity),
                        hop=hop,
                        fields=lineage_columns,
                        owners=self._owner_emails(entity),
                        critical=self._is_critical(entity),
                    )
                )

            missing: list[str] = []
            if source_field not in field_names:
                missing.append("source_field_missing")
            if bounded_results and not column_lineage_available:
                missing.append("column_lineage")

            return MetadataEvidence(
                source_urn=source_urn,
                source_field=source_field,
                column_lineage_available=column_lineage_available,
                downstream=downstream_nodes,
                owners=[],
                assertions_passing=None,
                metadata_age_hours=0.0,
                missing=missing,
            )

    @asynccontextmanager
    async def _open_session(self) -> AsyncIterator[ClientSession]:
        server = StdioServerParameters(
            command="uvx",
            args=["mcp-server-datahub@latest"],
            env={
                "DATAHUB_GMS_URL": self._settings.datahub_gms_url,
                "DATAHUB_GMS_TOKEN": self._settings.datahub_gms_token,
            },
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def _verify_required_tools(self, session: Any) -> None:
        tool_list = await session.list_tools()
        available = {tool.name for tool in tool_list.tools}
        missing = sorted(REQUIRED_DATAHUB_TOOLS - available)
        if missing:
            raise ValueError(f"Missing required DataHub MCP tools: {', '.join(missing)}")

    async def _call_tool(
        self,
        session: Any,
        tool_name: str,
        arguments: dict[str, object],
    ) -> Any:
        result = await session.call_tool(tool_name, arguments)
        if getattr(result, "is_error", False):
            raise RuntimeError(f"DataHub MCP tool failed: {tool_name}")
        return self._extract_payload(result)

    def _extract_payload(self, result: Any) -> Any:
        structured_content = getattr(result, "structured_content", None)
        if structured_content is not None:
            return structured_content

        for block in getattr(result, "content", []) or []:
            payload = self._decode_content_block(block)
            if payload is not None:
                return payload

        return {}

    def _decode_content_block(self, block: Any) -> Any:
        block_type = self._value(block, "type")
        if block_type == "text":
            return self._parse_json(self._value(block, "text"))
        if block_type == "resource":
            return self._decode_resource(self._value(block, "resource"))

        text_value = self._value(block, "text")
        if isinstance(text_value, str):
            return self._parse_json(text_value)
        return None

    def _decode_resource(self, resource: Any) -> Any:
        text_value = self._value(resource, "text")
        if isinstance(text_value, str):
            return self._parse_json(text_value)

        blob_value = self._value(resource, "blob")
        if isinstance(blob_value, str):
            decoded = base64.b64decode(blob_value).decode("utf-8")
            return self._parse_json(decoded)

        return None

    def _parse_json(self, raw_text: Any) -> Any:
        if not isinstance(raw_text, str):
            return None
        return json.loads(raw_text)

    def _lineage_columns(self, result: Mapping[str, Any]) -> list[str]:
        columns = result.get("lineageColumns")
        return [column for column in self._as_list(columns) if isinstance(column, str)]

    def _owner_emails(self, entity: Mapping[str, Any]) -> list[str]:
        ownership = entity.get("ownership")
        if not isinstance(ownership, Mapping):
            return []

        emails: list[str] = []
        for owner_entry in self._as_list(ownership.get("owners")):
            if not isinstance(owner_entry, Mapping):
                continue
            owner = owner_entry.get("owner")
            if not isinstance(owner, Mapping):
                continue

            properties = owner.get("properties")
            if isinstance(properties, Mapping):
                email = properties.get("email")
                if isinstance(email, str) and email and email not in emails:
                    emails.append(email)

            info = owner.get("info")
            if isinstance(info, Mapping):
                email = info.get("email")
                if isinstance(email, str) and email and email not in emails:
                    emails.append(email)

        return emails

    def _is_critical(self, entity: Mapping[str, Any]) -> bool:
        global_tags = entity.get("tags") or entity.get("globalTags")
        if not isinstance(global_tags, Mapping):
            return False

        for tag_entry in self._as_list(global_tags.get("tags")):
            if not isinstance(tag_entry, Mapping):
                continue
            tag = tag_entry.get("tag")
            if not isinstance(tag, Mapping):
                continue
            properties = tag.get("properties")
            if not isinstance(properties, Mapping):
                continue
            tag_name = properties.get("name")
            if isinstance(tag_name, str) and tag_name.lower() in {
                "critical",
                "changeproofcritical",
            }:
                return True
        return False

    def _entity_name(self, entity: Mapping[str, Any], *, fallback_urn: str) -> str:
        name = entity.get("name")
        if isinstance(name, str) and name:
            return name.rsplit(".", 1)[-1]
        return fallback_urn.split(",")[1].split(".")[-1]

    def _entity_type(self, entity: Mapping[str, Any]) -> str:
        entity_type = entity.get("type")
        if isinstance(entity_type, str) and entity_type:
            return entity_type.lower()
        return "unknown"

    def _entity_urn(self, entity: Any) -> str | None:
        if isinstance(entity, Mapping):
            urn = entity.get("urn")
            if isinstance(urn, str) and urn:
                return urn
        return None

    def _field_name(self, field: Any) -> str | None:
        if isinstance(field, Mapping):
            value = field.get("fieldPath")
            if isinstance(value, str) and value:
                return value
        return None

    def _hop(self, degree: Any) -> int:
        if isinstance(degree, int) and degree >= 1:
            return degree
        if isinstance(degree, str):
            bounded_degree = degree.strip()
            if bounded_degree == f"{DATAHUB_LINEAGE_MAX_HOPS}+":
                return DATAHUB_LINEAGE_MAX_HOPS
            if bounded_degree.isdigit():
                return max(1, int(bounded_degree))
        return 1

    def _value(self, item: Any, key: str) -> Any:
        if isinstance(item, Mapping):
            return item.get(key)
        return getattr(item, key, None)

    def _as_list(self, value: Any) -> list[Any]:
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return list(value)
        return []
