# ChangeProof Enterprise Impact Center Design

**Date:** 2026-08-09

**Status:** Pending written-spec review

**Primary demo:** AsterVale Living, a fictional national home furnishings retailer

## Outcome

ChangeProof will become a multi-page enterprise change intelligence tool built on
top of its existing DataHub evidence, impact scoring, remediation planning, and
human-approved write-back flow.

The judge-facing experience will answer six questions about a proposed schema
change:

1. What is changing?
2. What downstream assets does DataHub observe?
3. What hidden SQL consumers are not represented by that lineage?
4. Which business and geographic regions are exposed?
5. What fixes, validation queries, rollout steps, and rollback steps are proposed?
6. What approved knowledge should be written back to DataHub?

The product will generate fixes for every observed and successfully classified
consumer. It will never claim to find or safely repair every possible consumer.
Dynamic SQL, encrypted modules, external readers, missing metadata, and parse
failures remain explicit unresolved risks.

## Why this can score well

The hackathon evaluates use of DataHub, technical execution, originality,
real-world usefulness, and submission quality. It also favors meaningful
open-source contributions. The design targets those criteria directly:

| Criterion | ChangeProof evidence |
| --- | --- |
| Use of DataHub | MCP schema and lineage reads, ownership, tags, structured geographic properties, incidents, documentation, and approved write-back |
| Technical execution | Stateless multi-page app, deterministic evidence model, T-SQL analysis, generated artifacts, tests, and honest failure states |
| Originality | Combines DataHub's observed metadata graph with a hidden code-dependency graph for a change that has not shipped yet |
| Real-world usefulness | Produces migration artifacts that a platform team can review, validate, and carry into a pull request or change ticket |
| Submission quality | Enterprise scenario, three-minute flow, visible evidence labels, public deterministic demo, and reproducible local live mode |

Official references:

- [Hackathon requirements and judging criteria](https://datahub.devpost.com/)
- [DataHub metadata model](https://docs.datahub.com/docs/metadata-modeling/metadata-model)
- [DataHub lineage](https://docs.datahub.com/docs/features/feature-guides/lineage)
- [DataHub structured properties](https://docs.datahub.com/docs/api/tutorials/structured-properties)
- [DataHub incidents](https://docs.datahub.com/docs/api/tutorials/incidents)

## Existing foundation to preserve

The implementation must extend the current application rather than replace it.
The following behavior is already working and remains authoritative:

- Bundled and live DataHub evidence providers use one analysis contract.
- The official DataHub MCP server supplies schema fields and bounded downstream
  lineage.
- DataHub ownership and critical tags are normalized into impact evidence.
- Confidence falls when lineage is incomplete or stale.
- Remediation produces staged rollout and rollback steps.
- Write-back drafts incidents, critical tags, and documentation.
- The server rebuilds approved proposals rather than accepting arbitrary text.
- Hosted write-back is simulated and visibly labeled.
- Live DataHub write-back is explicit and fails closed when unavailable.

SonicLedger stays available as a regression fixture until AsterVale passes all
tests. It may remain as a secondary scenario, but it will not be the primary
judge-facing story.

## Enterprise scenario

### Fictional company

AsterVale Living is a synthetic national home furnishings retailer with:

- 420 stores
- one national e-commerce platform
- six regional distribution centers
- loyalty, returns, fraud, merchandising, and finance systems
- Northeast, South, Midwest, and West operating regions

No real company, customer, or transaction data will be used.

### Proposed change

The prepared judge scenario changes:

```text
astervale.models.staging.stg_orders.customer_id
varchar -> bigint
```

This keeps the original type-change story understandable while making the
consequences enterprise-scale.

### Observed DataHub lineage

The bundled and live fixtures will model the following chain:

```text
stg_orders.customer_id
  -> fct_order_sales.customer_id
  -> loyalty_customer_value.customer_id [critical]
  -> regional_returns.customer_id
  -> executive_revenue_dashboard.customer_id [critical]
```

Owners and business domains:

| Asset | Owner | DataHub domain |
| --- | --- | --- |
| `stg_orders` | `data-platform@astervale.demo` | Commerce |
| `fct_order_sales` | `analytics@astervale.demo` | Commerce |
| `loyalty_customer_value` | `loyalty@astervale.demo` | Customer |
| `regional_returns` | `operations@astervale.demo` | Operations |
| `executive_revenue_dashboard` | `finance@astervale.demo` | Finance |

DataHub domains group related business assets. Ownership remains separate
metadata. Geographic scope is modeled with structured properties because one
asset can belong to only one domain.

### Geographic metadata

Assets can carry these structured properties:

| Property | Type | Example |
| --- | --- | --- |
| `changeproof.businessRegion` | multi-value string | `NORTHEAST`, `WEST` |
| `changeproof.processingRegion` | multi-value string | `US_EAST`, `US_WEST` |
| `changeproof.dataResidency` | single string | `US` |
| `changeproof.regulatoryScope` | multi-value string | `CA_PRIVACY_REVIEW` |
| `changeproof.containsCustomerData` | single string | `true` |
| `changeproof.retentionDays` | number | `90` |

The hosted demo bundles equivalent typed metadata. The live fixture seeds the
properties into DataHub and reads them through a bounded metadata adapter.

## Product architecture

### One analysis, several views

All pages derive from one immutable `EnterpriseAnalysis` value:

```text
ChangeRequest
  + MetadataEvidence from DataHub
  + SqlImpactEvidence from module analysis
  + RegionImpact derived from affected assets
  + RemediationPlan
  + ArtifactBundle
  + WritebackProposals
```

The app remains stateless. Navigation carries only the prepared change inputs or
a deterministic run identifier derived from them. Every mutating action
recomputes server-authoritative analysis before applying an approval.

### Components

1. **Enterprise catalog provider**
   - Supplies AsterVale datasets, lineage, owners, tags, business domains, and
     regional properties in hosted mode.
   - Preserves the existing provider boundary for live DataHub MCP evidence.

2. **SQL discovery query generator**
   - Generates a read-only SQL Server query over `sys.sql_modules`,
     `sys.objects`, and `sys.schemas`.
   - Searches procedures, views, functions, and triggers for the affected
     identifier.
   - Displays the query before any optional execution.

3. **SQL impact analyzer**
   - Uses `sqlglot` with the T-SQL dialect where parsing succeeds.
   - Falls back to bounded lexical matching when a module cannot be parsed.
   - Classifies `CAST`, `CONVERT`, joins, predicates, assignments, parameters,
     grouping, concatenation, and dynamic SQL markers.
   - Records object, schema, object type, line or snippet, classification,
     confidence, and unresolved risks.

4. **Fix generator**
   - Produces reviewable SQL patches for classified fixture modules.
   - Produces compatibility migration SQL, backfill SQL, validation SQL, and
     rollback SQL.
   - Uses `TRY_CONVERT` and explicit invalid-row checks where appropriate.
   - Never executes a generated fix.
   - Labels parse failures and dynamic SQL as manual review.

5. **Region impact engine**
   - Aggregates regions from source, lineage assets, and SQL object ownership.
   - Detects cross-region dependencies.
   - Scores exposure using criticality, customer-data tags, missing ownership,
     and missing geographic metadata.
   - Uses `UNKNOWN` instead of inferring absent metadata.

6. **Artifact builder**
   - Produces `impact-report.json`, `proposed-fixes.sql`,
     `validation-queries.sql`, `rollback.sql`, and `changeproof.sarif`.
   - Artifacts contain generated proposals and evidence, not executed results.

7. **DataHub write-back builder**
   - Extends the current draft-and-approve flow.
   - Drafts one source incident, critical-asset tags, migration documentation,
     and a link or summary for the artifact bundle.
   - Adds regional exposure and hidden SQL findings to the incident body.
   - Uses DataHub APIs only after explicit item-level approval.

8. **Optional bounded AI reviewer**
   - Disabled when no API key is configured.
   - Runs only after the user selects `Run AI review`; key presence alone never
     triggers a paid request.
   - Receives only the deterministic evidence bundle and synthetic module text.
   - Explains proposed fixes and flags inconsistencies.
   - Cannot add dependencies, change risk scores, execute SQL, or write to
     DataHub.
   - The UI labels whether a review is deterministic-only or AI-reviewed.

The public demo must remain fully usable without AI credentials.

## Pages and navigation

### 1. Analyze

Route: `/`

- Introduces AsterVale and the prepared enterprise change.
- Supports the existing catalog scenarios as secondary examples.
- Shows evidence mode as bundled or live DataHub.
- Starts the analysis.

### 2. Impact

Route: `/impact`

- Shows DataHub-observed lineage, owners, critical assets, and confidence.
- Adds a second section for hidden SQL consumers.
- Distinguishes `DataHub observed`, `code matched`, and `unknown` evidence.
- Shows why confidence changed.

### 3. Regions

Route: `/regions`

- Shows a stylized United States region map and accessible region table.
- Summarizes affected assets, SQL objects, owners, and policy-review flags.
- Shows cross-region edges and migration readiness.
- Includes an explicit `UNKNOWN` region for incomplete metadata.
- Never claims row-level geographic counts.

### 4. Fixes

Route: `/fixes`

- Shows each affected SQL object beside its proposed replacement.
- Shows discovery, compatibility, validation, and rollback queries.
- Marks fixes as generated proposals requiring review.
- Offers the artifact bundle for download.

### 5. Rollout

Route: `/rollout`

- Shows dependency-ordered rollout and rollback.
- Groups actions by team and region.
- Shows validation gates and unresolved risks.
- Shows a CI-ready SARIF/JSON status without claiming that CI ran.

### 6. DataHub

Route: `/datahub`

- Shows draft incidents, tags, and documentation.
- Preserves the existing checkbox approval gate.
- Shows simulated and real write-back modes prominently.
- Rebuilds proposals server-side on approval.

Every page includes persistent navigation, the source change summary, evidence
mode, confidence, and an honest hosted/live label.

## SQL Server discovery query

The first generated dialect is SQL Server because the motivating example uses
T-SQL `CONVERT`. The query must be parameterized in live execution code and
read only from system catalogs. Conceptually it searches:

```sql
SELECT
    s.name AS schema_name,
    o.name AS object_name,
    o.type_desc,
    m.definition
FROM sys.sql_modules AS m
JOIN sys.objects AS o ON o.object_id = m.object_id
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
WHERE m.definition LIKE '%' + @column_name + '%';
```

The generated query is an evidence collector, not a complete dependency parser.
Encrypted modules, generated SQL, external jobs, and strings assembled at
runtime remain visible limitations.

## Generated fix example

Observed fixture:

```sql
CONVERT(INT, o.customer_id) = l.customer_id
```

Proposed compatibility form:

```sql
TRY_CONVERT(BIGINT, o.customer_id) = l.customer_id
```

Required validation:

```sql
SELECT COUNT(*) AS invalid_customer_ids
FROM sales.orders
WHERE customer_id IS NOT NULL
  AND TRY_CONVERT(BIGINT, customer_id) IS NULL;
```

The final migration plan should prefer a parallel typed field when the blast
radius is critical. An in-place expression rewrite alone is not considered a
complete migration.

## Hosted and live modes

### Hosted judge mode

- Uses bundled AsterVale metadata and synthetic SQL modules.
- Generates real queries and artifacts deterministically.
- Executes no database SQL.
- Uses simulated DataHub write-back with visible labels.
- Requires no credentials and remains stable for judges.

### Local live DataHub mode

- Seeds AsterVale dbt models, lineage, owners, tags, domains, and structured
  properties into local DataHub.
- Reads schema and lineage through the official DataHub MCP server.
- Reads additional bounded metadata through the supported DataHub API where the
  MCP tool contract does not expose it.
- Uses the existing human-approved DataHub write-back path.

### Optional live SQL Server mode

- Is not required for the public judge flow.
- Uses a dedicated read-only credential and allowlisted system-catalog query.
- Applies query timeout and result-size limits.
- Never runs generated fixes.
- Is a follow-up unless it can be verified without jeopardizing the submission.

## Safety and evidence rules

- No generated SQL executes in hosted mode.
- No write reaches DataHub without item-level approval.
- No request can submit arbitrary write-back content.
- No page equates missing lineage with no impact.
- No region is inferred when geographic metadata is absent.
- No legal conclusion is generated. Policy metadata produces a review flag.
- No production database credentials are stored in the repository.
- No AI call occurs without an explicit configured key.
- No source code or procedure text is sent to AI in production mode without a
  separate opt-in and redaction policy.
- Generated fixes are proposals for review, not verified production patches.

## Testing and verification

### Unit tests

- AsterVale catalog and lineage normalization
- Geographic property normalization and `UNKNOWN` handling
- Cross-region exposure calculation
- T-SQL discovery query generation
- SQL classification for convert, cast, join, predicate, assignment, and
  dynamic SQL cases
- Fix, validation, and rollback generation
- Artifact bundle contents and stable identifiers
- Extended DataHub write-back proposals
- AI-off deterministic behavior

### Integration tests

- Every page renders from the same prepared change
- Navigation preserves the active analysis
- Hosted mode performs no external database calls
- Simulated write-back never claims a real DataHub write
- Downloaded artifacts match displayed evidence
- Existing SonicLedger scenarios still render
- Opt-in live DataHub test verifies AsterVale lineage and regional metadata

### Visual verification

- Desktop judge flow
- Mobile layout
- Region map plus accessible table
- Long SQL snippets and diff wrapping
- High, medium, low, blocked, simulated, and unknown states
- Navigation and evidence labels on every page

### Completion command

```bash
uv run pytest -q
```

The live DataHub test remains opt-in and separate from the ordinary test suite.

## Delivery slices

### Slice 1: Enterprise foundation

- Add AsterVale catalog, dbt fixtures, synthetic SQL modules, and tests.
- Preserve SonicLedger.
- Introduce shared enterprise analysis models.

### Slice 2: Hidden SQL impact

- Generate the SQL Server discovery query.
- Analyze fixture modules.
- Generate fixes, validation, and rollback SQL.
- Build downloadable JSON, SQL, and SARIF artifacts.

### Slice 3: Multi-page judge experience

- Add persistent navigation and the six routes.
- Add Impact, Regions, Fixes, Rollout, and DataHub pages.
- Keep one evidence model across pages.

### Slice 4: Deeper DataHub loop

- Seed/read AsterVale structured properties and domains.
- Extend incidents and documentation with regional and SQL findings.
- Verify live MCP lineage and real approved write-back locally.

### Slice 5: Submission polish

- Run full tests and visual QA.
- Update README, Devpost copy, and three-minute demo script.
- Record only claims verified in the final build.
- Keep optional AI and live SQL Server out of the public claim unless they pass
  current live verification.

## Three-minute judge flow

1. **0:00 to 0:25:** Introduce AsterVale and propose `customer_id varchar -> bigint`.
2. **0:25 to 0:55:** Show DataHub lineage, owners, critical assets, and evidence quality.
3. **0:55 to 1:25:** Reveal hidden stored procedures and views that lineage missed.
4. **1:25 to 1:50:** Show regional exposure, cross-region impact, and unknown metadata.
5. **1:50 to 2:25:** Show generated fixes, validation queries, rollback, and artifacts.
6. **2:25 to 2:50:** Show dependency-ordered rollout and CI-ready report.
7. **2:50 to 3:00:** Approve one DataHub incident and emphasize inherited context.

## Non-goals for the submission build

- Rebuilding DataHub's lineage graph or catalog search
- Editing a real production stored procedure
- Running database migrations
- Claiming legal compliance
- Adding real customer or company data
- Supporting every SQL dialect
- Replacing DataHub as the metadata source of truth
- Hiding hosted simulation behind live-sounding language

## Acceptance criteria

The enterprise expansion is ready when:

1. AsterVale is the default hosted scenario and SonicLedger remains available.
2. The same proposed change drives all six pages.
3. DataHub evidence and hidden SQL evidence are visibly distinct.
4. The Regions page shows Northeast, South, Midwest, West, and Unknown exposure.
5. Every classified SQL consumer has a proposed fix or explicit manual-review state.
6. Validation and rollback queries are downloadable.
7. DataHub write-back includes the observed blast radius, hidden SQL findings,
   regional exposure, and evidence limitations.
8. Hosted mode executes no SQL and makes no real DataHub write.
9. The ordinary test suite passes and live verification remains opt-in.
10. README and submission claims match the final verified behavior.
