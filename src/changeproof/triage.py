from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_REQUIREMENTS_CHARS = 20_000
MAX_RULES = 20

SAMPLE_INCIDENT_QUESTION = (
    "Why is AsterVale Living's accounts-receivable balance different from the "
    "customer-facing order and settlement records?"
)
SAMPLE_SRS_TEXT = (Path(__file__).parent / "static" / "astervale-ar-incident-srs.txt").read_text()


@dataclass(frozen=True)
class TriageRule:
    number: int
    text: str
    status: str
    domain: str | None = None
    asset_urn: str | None = None
    columns: tuple[str, ...] = ()
    owner: str | None = None
    glossary: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DataHubStep:
    number: int
    operation: str
    query_decision: str


@dataclass(frozen=True)
class TriageResult:
    rules: tuple[TriageRule, ...]
    mappings: tuple[TriageRule, ...]
    datahub_steps: tuple[DataHubStep, ...]
    sql: str
    validation_sql: str
    warnings: tuple[str, ...]
    domains: tuple[str, ...]
    evidence_mode: str


@dataclass(frozen=True)
class _CatalogEntry:
    domain: str
    asset_name: str
    columns: tuple[str, ...]
    owner: str
    glossary: str
    keywords: tuple[str, ...]

    @property
    def asset_urn(self) -> str:
        return f"urn:li:dataset:(urn:li:dataPlatform:mssql,astervale.{self.asset_name},PROD)"


CATALOG = (
    _CatalogEntry(
        "Commerce",
        "commerce.orders",
        ("order_id", "customer_id", "ordered_at", "order_total"),
        "Commerce Data",
        "Order lifecycle",
        ("order", "orders", "commerce"),
    ),
    _CatalogEntry(
        "Finance",
        "finance.ar_transactions",
        ("transaction_id", "invoice_id", "order_id", "customer_id", "amount", "posted_at"),
        "Accounts Receivable",
        "AR transaction",
        ("invoice", "invoices", "receivable", "ar balance", "ar", "finance"),
    ),
    _CatalogEntry(
        "Payments",
        "payments.settlements",
        ("settlement_id", "invoice_id", "settled_amount", "settled_at", "status"),
        "Payments Platform",
        "Settlement",
        ("payment", "payments", "settlement", "settled"),
    ),
    _CatalogEntry(
        "Returns & Refunds",
        "commerce.returns_refunds",
        ("return_id", "order_id", "refund_amount", "returned_at", "reason"),
        "Customer Care",
        "Refund",
        ("return", "returns", "refund", "refunds"),
    ),
    _CatalogEntry(
        "Fulfillment",
        "fulfillment.shipments",
        ("shipment_id", "order_id", "shipped_at", "delivered_at", "status"),
        "Fulfillment Operations",
        "Shipment",
        ("fulfillment", "shipment", "ship", "delivery", "delivered"),
    ),
    _CatalogEntry(
        "Customer Identity",
        "identity.customers",
        ("customer_id", "account_id", "customer_region", "status"),
        "Identity Platform",
        "Customer",
        ("customer", "account", "identity"),
    ),
    _CatalogEntry(
        "Regional Policy",
        "policy.regional_ar_rules",
        ("region_code", "effective_from", "effective_to", "tax_rate", "credit_days"),
        "Regional Policy",
        "Regional AR policy",
        ("region", "regional", "policy", "tax", "credit days"),
    ),
)


def build_triage_result(question: str, requirements_text: str) -> TriageResult:
    if len(requirements_text) > MAX_REQUIREMENTS_CHARS:
        raise ValueError("requirements text must be at most 20,000 characters")
    if len(question) > MAX_REQUIREMENTS_CHARS:
        raise ValueError("incident question must be at most 20,000 characters")

    rules = tuple(
        _map_rule(index, text)
        for index, text in enumerate(_extract_rules(requirements_text), 1)
    )
    mapped = tuple(rule for rule in rules if rule.status == "MAPPED")
    domains = tuple(dict.fromkeys(rule.domain for rule in mapped if rule.domain is not None))
    warnings = tuple(
        f"Rule {rule.number} is UNMAPPED; no bounded DataHub asset was selected."
        for rule in rules
        if rule.status == "UNMAPPED"
    )
    has_mapped_rules = bool(mapped)
    return TriageResult(
        rules=rules,
        mappings=rules,
        datahub_steps=_datahub_steps(domains) if has_mapped_rules else (),
        sql=_compose_sql(question) if has_mapped_rules else "",
        validation_sql=_validation_sql() if has_mapped_rules else "",
        warnings=warnings,
        domains=domains,
        evidence_mode="Bundled synthetic DataHub-shaped metadata; generated SQL requires review.",
    )


def triage_export_text(result: TriageResult) -> str:
    lines = [
        "CHANGEProof TRIAGE COMPOSER",
        "Generated evidence package — review required; SQL was not executed.",
        f"Evidence mode: {result.evidence_mode}",
        "",
        "RULE MAPPINGS",
    ]
    for rule in result.rules:
        asset = rule.asset_urn or "(none)"
        lines.append(f"{rule.number}. [{rule.status}] {rule.text} -> {asset}")
    lines += ["", "DATAHUB TOUCHPOINTS"]
    lines.extend(
        f"{step.number}. {step.operation}: {step.query_decision}"
        for step in result.datahub_steps
    )
    lines += [
        "",
        "WARNINGS",
        *result.warnings,
        "",
        "GENERATED SQL",
        result.sql,
        "",
        "VALIDATION SQL",
        result.validation_sql,
    ]
    return "\n".join(lines) + "\n"


def _extract_rules(text: str) -> tuple[str, ...]:
    rules: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw_line).strip()
        if line and not line.startswith("#"):
            rules.append(line)
    if len(rules) > MAX_RULES:
        raise ValueError(f"requirements text contains more than the maximum of {MAX_RULES} rules")
    return tuple(rules)


def _map_rule(number: int, text: str) -> TriageRule:
    lowered = text.casefold()
    matches = []
    for catalog_index, entry in enumerate(CATALOG):
        keywords = tuple(
            keyword
            for keyword in entry.keywords
            if re.search(rf"\b{re.escape(keyword)}\b", lowered)
        )
        if keywords:
            matches.append((entry, keywords, catalog_index))
    if not matches:
        return TriageRule(
            number,
            text,
            "UNMAPPED",
            reason="No bounded catalog keyword matched this rule.",
        )
    entry, _, _ = max(
        matches,
        key=lambda match: (
            max(len(keyword) for keyword in match[1]),
            sum(len(keyword) for keyword in match[1]),
            len(match[1]),
            -match[2],
        ),
    )
    return TriageRule(
        number,
        text,
        "MAPPED",
        entry.domain,
        entry.asset_urn,
        entry.columns,
        entry.owner,
        entry.glossary,
        f"Matched bounded {entry.domain} catalog keywords and selected schema fields.",
    )


def _datahub_steps(domains: tuple[str, ...]) -> tuple[DataHubStep, ...]:
    operations = (
        ("Search/discover datasets", "Find candidate source assets for each mapped rule."),
        ("Inspect schema fields", "Select join keys, timestamps, and monetary columns."),
        ("Read lineage", "Order source events across the AR investigation path."),
        ("Resolve ownership", "Attach an accountable team to each mapped asset."),
        ("Read domains", "Group the investigation by enterprise functional domain."),
        ("Read glossary terms", "Explain the meaning of AR, settlement, and refund fields."),
        ("Check quality and freshness", "Keep validation focused on stale or incomplete evidence."),
    )
    count = max(6, len(domains))
    return tuple(
        DataHubStep(index, operation, decision)
        for index, (operation, decision) in enumerate(operations[:count], 1)
    )


def _compose_sql(question: str) -> str:
    safe_question = question.replace("*/", "* /")
    return f"""/* Generated by ChangeProof; review required; not executed.
Incident question: {safe_question}
*/
WITH customer_scope AS (
    -- DataHub operation: inspect schema fields and identity ownership.
    SELECT customer_id, account_id, customer_region
    FROM identity.customers
), order_events AS (
    -- DataHub operation: search/discover commerce.orders and inspect timestamps.
    SELECT o.order_id, o.customer_id, o.ordered_at AS event_at, o.order_total AS amount
    FROM commerce.orders AS o
    JOIN customer_scope AS c ON c.customer_id = o.customer_id
), invoice_events AS (
    -- DataHub operation: read lineage from orders to finance.ar_transactions.
    SELECT a.invoice_id AS event_id, a.order_id AS order_id, a.customer_id,
           a.posted_at AS event_at, a.amount
    FROM finance.ar_transactions AS a
    JOIN customer_scope AS c ON c.customer_id = a.customer_id
), order_comparison AS (
    -- DataHub operation: compare commerce order totals to invoice debits separately.
    SELECT o.order_id, o.customer_id, o.event_at AS ordered_at, o.amount AS order_total,
           a.amount AS invoice_amount
    FROM order_events AS o
    LEFT JOIN invoice_events AS a ON a.order_id = o.order_id
), payment_events AS (
    -- DataHub operation: inspect payments.settlements schema and ownership.
    SELECT s.settlement_id AS event_id, a.customer_id, s.settled_at AS event_at,
           -s.settled_amount AS amount
    FROM payments.settlements AS s
    JOIN finance.ar_transactions AS a ON a.invoice_id = s.invoice_id
), return_refund_events AS (
    -- DataHub operation: read glossary and lineage for returns/refunds.
    SELECT r.return_id AS event_id, o.customer_id, r.returned_at AS event_at,
           -r.refund_amount AS amount
    FROM commerce.returns_refunds AS r
    JOIN commerce.orders AS o ON o.order_id = r.order_id
), fulfillment_events AS (
    -- DataHub operation: check fulfillment freshness before using delivery events.
    SELECT s.shipment_id AS event_id, o.customer_id, s.delivered_at AS event_at,
           CAST(0 AS decimal(18, 2)) AS amount
    FROM fulfillment.shipments AS s
    JOIN commerce.orders AS o ON o.order_id = s.order_id
), normalized_events AS (
    SELECT event_id, customer_id, event_at, amount, 'INVOICE' FROM invoice_events
    UNION ALL SELECT event_id, customer_id, event_at, amount, 'PAYMENT' FROM payment_events
    UNION ALL SELECT event_id, customer_id, event_at, amount, 'REFUND' FROM return_refund_events
), running_balance AS (
    SELECT customer_id, event_id, event_type, event_at, amount,
           SUM(amount) OVER (PARTITION BY customer_id ORDER BY event_at, event_id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
    FROM normalized_events
), reconciliation_exceptions AS (
    SELECT customer_id, event_id, event_type, event_at, amount, running_balance
    FROM running_balance
    WHERE running_balance < 0 OR amount IS NULL
), order_invoice_mismatches AS (
    SELECT customer_id, order_id AS event_id, 'ORDER_INVOICE_MISMATCH' AS event_type,
           ordered_at AS event_at,
           order_total - COALESCE(invoice_amount, CAST(0 AS decimal(18, 2))) AS amount,
           CAST(NULL AS decimal(18, 2)) AS running_balance
    FROM order_comparison
    WHERE invoice_amount IS NULL OR order_total <> invoice_amount
), final_results AS (
    SELECT customer_id, event_id, event_type, event_at, amount, running_balance
    FROM reconciliation_exceptions
    UNION ALL
    SELECT customer_id, event_id, event_type, event_at, amount, running_balance
    FROM order_invoice_mismatches
)
SELECT e.*, c.customer_region
FROM final_results AS e
JOIN customer_scope AS c ON c.customer_id = e.customer_id
ORDER BY e.customer_id, e.event_at, e.event_id;
"""


def _validation_sql() -> str:
    return """-- Generated validation checks; review and run only against an approved environment.
SELECT 'missing_customer_keys' AS check_name, COUNT(*) AS failure_count
FROM finance.ar_transactions AS a
LEFT JOIN identity.customers AS c ON c.customer_id = a.customer_id
WHERE c.customer_id IS NULL
UNION ALL
SELECT 'unsettled_invoices', COUNT(*)
FROM finance.ar_transactions AS a
LEFT JOIN payments.settlements AS s ON s.invoice_id = a.invoice_id
WHERE s.invoice_id IS NULL
UNION ALL
SELECT 'duplicate_settlement_ids', COUNT(*)
FROM payments.settlements
GROUP BY settlement_id
HAVING COUNT(*) > 1;
"""
