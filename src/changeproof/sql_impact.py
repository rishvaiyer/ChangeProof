import re
from dataclasses import dataclass

import sqlglot
from sqlglot.errors import ParseError

from .models import Confidence, SqlDependency, SqlMatchKind


@dataclass(frozen=True)
class SqlModule:
    schema_name: str
    object_name: str
    object_type: str
    definition: str
    regions: tuple[str, ...]


ASTERVALE_SQL_MODULES = (
    SqlModule(
        schema_name="loyalty",
        object_name="usp_reconcile_loyalty_customer",
        object_type="SQL_STORED_PROCEDURE",
        definition=(
            "SELECT customer_id FROM loyalty.member_snapshot "
            "WHERE TRY_CONVERT(INT, customer_id) = @customer_id;"
        ),
        regions=("NORTHEAST", "WEST"),
    ),
    SqlModule(
        schema_name="operations",
        object_name="usp_match_regional_returns",
        object_type="SQL_STORED_PROCEDURE",
        definition=(
            "SELECT r.return_id FROM operations.returns r "
            "JOIN commerce.orders o ON r.customer_id = o.customer_id;"
        ),
        regions=("SOUTH", "MIDWEST", "WEST"),
    ),
    SqlModule(
        schema_name="finance",
        object_name="vw_customer_revenue_bridge",
        object_type="VIEW",
        definition=(
            "SELECT CAST(customer_id AS INT) AS customer_id, net_revenue "
            "FROM finance.revenue_daily;"
        ),
        regions=("NORTHEAST", "SOUTH", "MIDWEST", "WEST"),
    ),
    SqlModule(
        schema_name="exports",
        object_name="usp_export_customer_segments",
        object_type="SQL_STORED_PROCEDURE",
        definition=(
            "DECLARE @sql nvarchar(max) = N'SELECT customer_id FROM ' + @table; "
            "EXEC sys.sp_executesql @sql;"
        ),
        regions=(),
    ),
)


def build_discovery_query(column_name: str) -> str:
    safe_name = column_name.replace("'", "''")
    return f"""-- Read-only ChangeProof dependency discovery for SQL Server
DECLARE @column_name sysname = N'{safe_name}';

SELECT
    SCHEMA_NAME(o.schema_id) AS schema_name,
    o.name AS object_name,
    o.type_desc AS object_type,
    m.definition
FROM sys.sql_modules AS m
JOIN sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE N'%' + @column_name + N'%'
ORDER BY schema_name, object_name;
"""


def analyze_sql_modules(
    column_name: str,
    old_type: str,
    new_type: str,
    modules: tuple[SqlModule, ...] = ASTERVALE_SQL_MODULES,
) -> tuple[SqlDependency, ...]:
    del old_type
    column_pattern = re.compile(rf"\b{re.escape(column_name)}\b", re.IGNORECASE)
    matches: list[SqlDependency] = []
    for module in modules:
        if not column_pattern.search(module.definition):
            continue
        matches.append(_classify(module, column_name, new_type))
    return tuple(matches)


def _classify(module: SqlModule, column_name: str, new_type: str) -> SqlDependency:
    definition = module.definition
    upper = definition.upper()
    proposed_sql: str | None = None
    manual_review_reason: str | None = None

    try:
        sqlglot.parse_one(definition, read="tsql")
    except ParseError:
        return SqlDependency(
            schema_name=module.schema_name,
            object_name=module.object_name,
            object_type=module.object_type,
            snippet=definition,
            match_kind=SqlMatchKind.PREDICATE,
            confidence=Confidence.LOW,
            regions=list(module.regions),
            manual_review_reason=(
                "SQL parser could not verify this expression, so it needs manual review."
            ),
        )

    if "SP_EXECUTESQL" in upper or re.search(r"\bEXEC(?:UTE)?\b", upper):
        kind = SqlMatchKind.DYNAMIC_SQL
        confidence = Confidence.LOW
        manual_review_reason = (
            "Contains dynamic SQL, so the referenced object and runtime type need manual review."
        )
    elif re.search(r"\b(?:TRY_)?CONVERT\s*\(", upper):
        kind = SqlMatchKind.CONVERT
        confidence = Confidence.HIGH
        expression = re.compile(
            rf"(?:TRY_)?CONVERT\s*\(\s*[^,]+\s*,\s*{re.escape(column_name)}\s*\)",
            re.IGNORECASE,
        )
        proposed_sql = expression.sub(
            f"TRY_CONVERT({new_type.upper()}, {column_name})", definition
        )
    elif re.search(r"\bCAST\s*\(", upper):
        kind = SqlMatchKind.CAST
        confidence = Confidence.HIGH
        expression = re.compile(
            rf"CAST\s*\(\s*{re.escape(column_name)}\s+AS\s+[^)]+\)",
            re.IGNORECASE,
        )
        proposed_sql = expression.sub(
            f"TRY_CAST({column_name} AS {new_type.upper()})", definition
        )
    elif " JOIN " in upper:
        kind = SqlMatchKind.JOIN
        confidence = Confidence.MEDIUM
        manual_review_reason = (
            f"Verify both join operands are {new_type.upper()} before changing the source."
        )
    else:
        kind = SqlMatchKind.PREDICATE
        confidence = Confidence.MEDIUM
        manual_review_reason = "Static reference found, but the expression needs owner review."

    return SqlDependency(
        schema_name=module.schema_name,
        object_name=module.object_name,
        object_type=module.object_type,
        snippet=definition,
        match_kind=kind,
        confidence=confidence,
        regions=list(module.regions),
        proposed_sql=proposed_sql,
        manual_review_reason=manual_review_reason,
    )
