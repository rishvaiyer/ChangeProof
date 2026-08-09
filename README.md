# contextIsKey

**DataHub supplies the enterprise context. contextIsKey turns it into a reviewable investigation.**

contextIsKey maps incident requirements to DataHub assets and columns, composes a cross-domain chronological SQL investigation, traces proposed schema changes through hidden SQL and geographic exposure, and packages fixes behind human review. It is built on the ChangeProof decision engine.

[Existing public deployment](https://changeproof-production.up.railway.app/) · [Repository](https://github.com/rishvaiyer/ChangeProof) · [Apache-2.0 license](LICENSE)

> The public Railway demo uses deterministic synthetic DataHub-shaped context for speed and reliability. The repository also includes an opt-in integration verified against a local DataHub instance through the official MCP server.

## Judge flow

Use the prepared AsterVale Living scenario:

```text
Column:        customer_id
Current type: varchar
Proposed type: bigint
```

Start with the included accounts-receivable incident, then visit seven focused workspaces:

1. **Triage Composer:** map an SRS to datasets, columns, owners, domains, glossary terms, and a reviewable chronological SQL query.
2. **Analyze:** frame a proposed contract change and see the enterprise summary.
3. **Impact graph:** combine DataHub lineage with hidden SQL Server module findings.
4. **Regions:** map assets, stored procedures, owners, and review flags across Northeast, South, Midwest, West, and unknown metadata.
5. **Fix Studio:** review generated SQL, validation queries, rollback controls, JSON, and SARIF artifacts.
6. **Rollout:** follow a dependency-ordered migration with explicit gates.
7. **DataHub actions:** approve individual incident, tag, and documentation drafts.

## Enterprise scenario

AsterVale Living is a fictional national home-furnishings retailer with 420 stores and six regional distribution centers. All company, customer, procedure, and regional data is synthetic.

The Triage Composer begins with a cross-functional AR discrepancy. Nine SRS rules span Commerce, Finance, Payments, Returns, Fulfillment, Customer Identity, and Regional Policy. Seven bounded lookups against the hosted synthetic context select 7 datasets, 34 schema fields, 7 owners, 7 domains, and 7 glossary terms before composing the query. One unsupported rule stays visibly unmapped instead of being invented.

The proposed edit is:

```text
stg_orders.customer_id: varchar -> bigint
```

DataHub evidence exposes this downstream chain:

```text
stg_orders.customer_id
  -> fct_order_sales
  -> loyalty_customer_value [critical]
  -> regional_returns
  -> executive_revenue_dashboard [critical]
```

ChangeProof also searches SQL Server module definitions and finds four code-level consumers, including `CONVERT`, `CAST`, join logic, and dynamic SQL. Recognized convert and cast expressions receive reviewable drafts. Joins and dynamic SQL are marked for manual review unless a semantic rewrite can be verified.

## What DataHub contributes

DataHub is the governed context graph, not a normal application database. contextIsKey uses its relationships as reasoning inputs:

- Dataset discovery across functional domains
- Column-level lineage and hop distance
- Dataset and schema-field identity
- Ownership metadata
- Business glossary terms and domains
- Critical-asset tags
- Metadata completeness and freshness
- Business grouping that can be represented with domains
- Regional context that can be represented with structured properties
- Official MCP tool contracts for schema and lineage reads
- GraphQL write-back for incidents, tags, and documentation

contextIsKey adds the incident and change decision layer:

- SRS-to-metadata rule mapping with explicit unmapped results
- Cross-domain chronological query composition
- A numbered record of every hosted context lookup and query decision
- Change-specific evidence scoring
- Hidden SQL dependency discovery
- Geographic blast-radius aggregation
- Generated migration and validation artifacts
- Dependency-ordered rollout and rollback
- Explicit AI second-pass review
- Human-approved DataHub write-back

## Architecture

```mermaid
flowchart LR
    A["SRS or proposed schema change"] --> B["DataHub context graph via MCP"]
    B --> C["Bounded rule-to-asset mapping"]
    C --> D["Chronological SQL composer"]
    A --> E["Read-only SQL module scan"]
    B --> F["Deterministic impact engine"]
    E --> F
    F --> G["Regional exposure, fixes, rollout"]
    D --> H["Optional grounded AI review"]
    G --> I["Approval-gated DataHub write-back"]
```

Core design boundaries:

- Hosted mode executes no database SQL.
- Hosted Triage Composer context is bundled and synthetic; it reproduces the shape of the live integration without claiming a live cloud connection.
- Generated SQL never executes automatically.
- AI runs only after the user clicks **Run AI review**.
- AI is advisory only. It cannot change risk scores, deterministic evidence, execution, or write-back.
- Backtick-delimited identifiers are checked against the evidence bundle, but free-form AI prose is never treated as authoritative discovery.
- Approval requests carry proposal IDs only. Catalog content is rebuilt server-side.
- Missing lineage, ownership, or region metadata stays visible as uncertainty.

## Generated artifacts

Every result can be downloaded as TXT or PDF. The Triage Composer also downloads its query as SQL. The Fix Studio exposes six deterministic artifacts:

- `impact-report.json`
- `discovery-query.sql`
- `proposed-fixes.sql`
- `validation-queries.sql`
- `rollback.sql`
- `changeproof.sarif`

## Run locally

Requires Python 3.12.

```bash
uv sync --extra dev
CHANGE_PROOF_WRITEBACK_MODE=simulated uv run uvicorn changeproof.app:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

For the optional AI review:

```bash
export OPENAI_API_KEY="your-key"
```

The key alone makes no API request. A request occurs only after an explicit click.

## Live DataHub path

```bash
make live-demo
```

The current live integration:

- Builds the synthetic SonicLedger dbt and DuckDB fixture
- Emits schemas, owners, tags, table lineage, and fine-grained column lineage
- Reads schema and lineage through the official DataHub MCP server
- Uses the same deterministic impact and remediation engine
- Applies approved write-back proposals through DataHub GraphQL

Real GraphQL mutation mode is disabled by default. `make live-demo` enables it only for the trusted loopback runtime after the local DataHub checks pass.

The AsterVale regional properties are bundled synthetic evidence in hosted mode. They model the domains and structured properties an enterprise deployment would ingest. They are not presented as live DataHub Cloud data.

## Verify

```bash
uv run pytest -q
uv run ruff check .
```

The ordinary suite is credential-free. Live DataHub remains opt-in:

```bash
CHANGE_PROOF_LIVE_DATAHUB=1 uv run pytest tests/integration/test_datahub_context.py -q
```

## Context capability boundary

- **Used in the hosted flow:** datasets, columns, owners, domains, glossary terms, deterministic discovery, query composition, regional context, and reviewable exports.
- **Available through the included live path:** official MCP schema and lineage reads plus approval-gated GraphQL write-back.
- **Connect live DataHub to activate:** live quality and freshness signals, documentation relationships, dashboards and ML models, near-real-time metadata events, audit access, and governance policies.

## Current boundaries

- Hosted evidence is deterministic and synthetic, not a live DataHub Cloud connection.
- Hosted write-back is simulated and clearly labeled. It makes no network call.
- The local live path is the verified DataHub MCP and GraphQL integration.
- Static SQL discovery cannot guarantee complete dependency coverage.
- Dynamic SQL and absent region metadata require manual review.
- Regional flags are coordination signals, not legal-compliance determinations.

## License

contextIsKey, built on ChangeProof, is available under the [Apache License 2.0](LICENSE).
