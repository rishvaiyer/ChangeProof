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
    unique_mappings = _unique_mappings(mapped)
    return TriageResult(
        rules=rules,
        mappings=mapped,
        datahub_steps=_datahub_steps(unique_mappings) if has_mapped_rules else (),
        sql=_compose_sql(question, unique_mappings) if has_mapped_rules else "",
        validation_sql=_validation_sql(unique_mappings) if has_mapped_rules else "",
        warnings=warnings,
        domains=domains,
        evidence_mode="Bundled synthetic DataHub-shaped metadata; generated SQL requires review.",
    )


def triage_export_text(result: TriageResult) -> str:
    lines = [
        "contextIsKey TRIAGE COMPOSER",
        "Built on ChangeProof.",
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


def _unique_mappings(mapped: tuple[TriageRule, ...]) -> tuple[TriageRule, ...]:
    unique: dict[str, TriageRule] = {}
    for rule in mapped:
        if rule.asset_urn and rule.asset_urn not in unique:
            unique[rule.asset_urn] = rule
    return tuple(unique.values())


def _asset_name(rule: TriageRule) -> str:
    assert rule.asset_urn is not None
    return rule.asset_urn.rsplit(",", 2)[-2].removeprefix("astervale.").rstrip(")")


def _datahub_steps(mapped: tuple[TriageRule, ...]) -> tuple[DataHubStep, ...]:
    return tuple(
        DataHubStep(
            index,
            f"Bundled context lookup #{index} · {_asset_name(rule)}",
            "Bundled catalog discovery selected the dataset; schema-shaped context selected "
            f"{', '.join(rule.columns)}; the context graph linked domain "
            f"{rule.domain}, owner {rule.owner}, and glossary term {rule.glossary}.",
        )
        for index, rule in enumerate(mapped, 1)
    )


def _compose_sql(question: str, mapped: tuple[TriageRule, ...]) -> str:
    if {rule.domain for rule in mapped} == {entry.domain for entry in CATALOG}:
        return _compose_full_ar_sql(question)
    return _compose_preview_sql(question, mapped)


def _sql_header(question: str) -> str:
    safe_question = question.replace("*/", "* /")
    return f"""/* Generated by contextIsKey · Built on ChangeProof; review required; not executed.
Incident question: {safe_question}
*/
"""


def _compose_full_ar_sql(question: str) -> str:
    return _sql_header(question) + """WITH customer_scope AS (
    -- Mapped DataHub context: identity customers with regional policy.
    SELECT c.customer_id, c.account_id, c.customer_region, p.credit_days,
           CASE WHEN p.region_code IS NULL THEN 1 ELSE 0 END AS policy_join_missing
    FROM identity.customers AS c
    LEFT JOIN policy.regional_ar_rules AS p ON p.region_code = c.customer_region
), order_events AS (
    SELECT o.order_id AS event_id, o.order_id, o.customer_id, o.ordered_at AS event_at,
           o.order_total AS amount, 0 AS source_join_missing
    FROM commerce.orders AS o
), invoice_events AS (
    SELECT a.invoice_id AS event_id, a.order_id, a.customer_id, a.posted_at AS event_at,
           a.amount, 0 AS source_join_missing
    FROM finance.ar_transactions AS a
), order_comparison AS (
    SELECT o.order_id, o.customer_id, o.event_at AS ordered_at, o.amount AS order_total,
           a.amount AS invoice_amount
    FROM order_events AS o
    LEFT JOIN invoice_events AS a ON a.order_id = o.order_id
), payment_events AS (
    SELECT s.settlement_id AS event_id, a.customer_id, s.settled_at AS event_at,
           -s.settled_amount AS amount,
           CASE WHEN a.invoice_id IS NULL THEN 1 ELSE 0 END AS source_join_missing
    FROM payments.settlements AS s
    LEFT JOIN finance.ar_transactions AS a ON a.invoice_id = s.invoice_id
), return_refund_events AS (
    SELECT r.return_id AS event_id, o.customer_id, r.returned_at AS event_at,
           -r.refund_amount AS amount,
           CASE WHEN o.order_id IS NULL THEN 1 ELSE 0 END AS source_join_missing
    FROM commerce.returns_refunds AS r
    LEFT JOIN commerce.orders AS o ON o.order_id = r.order_id
), fulfillment_events AS (
    SELECT s.shipment_id AS event_id, o.customer_id, s.delivered_at AS event_at,
           CAST(0 AS decimal(18, 2)) AS amount,
           CASE WHEN o.order_id IS NULL THEN 1 ELSE 0 END AS source_join_missing
    FROM fulfillment.shipments AS s
    LEFT JOIN commerce.orders AS o ON o.order_id = s.order_id
), normalized_events AS (
    SELECT event_id, customer_id, event_at, amount, 'ORDER' AS event_type, 0 AS affects_ar,
           source_join_missing
    FROM order_events
    UNION ALL
    SELECT event_id, customer_id, event_at, amount, 'INVOICE' AS event_type, 1 AS affects_ar,
           source_join_missing
    FROM invoice_events
    UNION ALL
    SELECT event_id, customer_id, event_at, amount, 'PAYMENT' AS event_type, 1 AS affects_ar,
           source_join_missing
    FROM payment_events
    UNION ALL
    SELECT event_id, customer_id, event_at, amount, 'REFUND' AS event_type, 1 AS affects_ar,
           source_join_missing
    FROM return_refund_events
    UNION ALL
    SELECT event_id, customer_id, event_at, amount, 'FULFILLMENT' AS event_type, 0 AS affects_ar,
           source_join_missing
    FROM fulfillment_events
), running_balance AS (
    SELECT event_id, customer_id, event_at, amount, event_type, affects_ar,
           source_join_missing,
           SUM(CASE WHEN affects_ar = 1 THEN amount ELSE CAST(0 AS decimal(18, 2)) END)
               OVER (PARTITION BY customer_id,
                                    CASE WHEN customer_id IS NULL THEN event_id END
                     ORDER BY event_at, event_id
                     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
    FROM normalized_events
), order_invoice_mismatches AS (
    SELECT order_id, customer_id
    FROM order_comparison
    WHERE invoice_amount IS NULL OR order_total <> invoice_amount
), final_results AS (
    SELECT r.event_id, r.customer_id, r.event_at, r.amount, r.event_type, r.affects_ar,
           r.running_balance, c.account_id, c.customer_region, c.credit_days,
           CASE
               WHEN r.source_join_missing = 1 OR c.customer_id IS NULL
                    OR c.policy_join_missing = 1 THEN 'MISSING_JOIN'
               WHEN m.order_id IS NOT NULL THEN 'ORDER_INVOICE_MISMATCH'
               WHEN r.affects_ar = 1 AND (r.running_balance < 0 OR r.amount IS NULL)
                   THEN 'AR_BALANCE_EXCEPTION'
               ELSE NULL
           END AS issue_label
    FROM running_balance AS r
    LEFT JOIN order_invoice_mismatches AS m
        ON m.customer_id = r.customer_id AND m.order_id = r.event_id
    LEFT JOIN customer_scope AS c ON c.customer_id = r.customer_id
)
SELECT f.*
FROM final_results AS f
ORDER BY f.customer_id, f.event_at, f.event_id;
"""


def _compose_preview_sql(question: str, mapped: tuple[TriageRule, ...]) -> str:
    previews = []
    for rule in mapped:
        previews.extend(
            [
                f"-- {_asset_name(rule)} · Owner: {rule.owner} · Glossary: {rule.glossary}",
                f"SELECT TOP (100) {', '.join(rule.columns)}",
                f"FROM {_asset_name(rule)};",
                "",
            ]
        )
    return _sql_header(question) + "\n".join(previews).rstrip() + "\n"


def _validation_sql(mapped: tuple[TriageRule, ...]) -> str:
    if {rule.domain for rule in mapped} == {entry.domain for entry in CATALOG}:
        return _full_validation_sql()
    checks = ["-- contextIsKey · Built on ChangeProof validation previews; review required."]
    for rule in mapped:
        checks.extend(
            [
                f"SELECT '{_asset_name(rule)}' AS asset_name, COUNT(*) AS row_count",
                f"FROM {_asset_name(rule)};",
            ]
        )
    return "\n".join(checks) + "\n"


def _full_validation_sql() -> str:
    return """-- contextIsKey · Built on ChangeProof validation checks.
-- Review and run only against an approved environment.
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
