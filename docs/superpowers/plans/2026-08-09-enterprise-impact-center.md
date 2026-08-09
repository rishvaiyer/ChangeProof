# ChangeProof Enterprise Impact Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing ChangeProof demo into a judge-ready enterprise impact center for a fictional national retailer, with DataHub evidence, hidden T-SQL dependencies, regional exposure, generated migration artifacts, optional AI review, and approved DataHub write-back.

**Architecture:** Extend the existing immutable `DemoAnalysis` contract with optional enterprise evidence so SonicLedger remains compatible. Keep hosted mode deterministic and stateless, derive every page from the same server-recomputed analysis, and isolate SQL, region, artifact, and AI responsibilities in focused modules. Preserve DataHub MCP for schema and lineage reads and the existing server-authoritative GraphQL write-back gate.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Jinja2, DataHub MCP, DataHub GraphQL/OpenAPI, sqlglot, OpenAI Responses API, pytest, Ruff, dbt, DuckDB, Railway.

**Deadline scope:** Tasks 1 through 6 and Task 9 are the working MVP. Task 7 is limited to enriching the existing safe write-back draft. Task 8 is stretch work and must not delay a beautiful, verified web experience.

## Global Constraints

- Use Apache License 2.0, as required by the hackathon submission page.
- Keep all AsterVale company, customer, procedure, and regional data synthetic.
- Keep SonicLedger available until the complete regression suite passes.
- Hosted mode executes no database SQL and makes no real DataHub write.
- No generated fix executes automatically.
- AI runs only after an explicit user action and never controls risk scores or write-back.
- Missing lineage, SQL coverage, ownership, or region metadata lowers confidence or creates a manual-review state.
- Use DataHub domains for business grouping and structured properties for geography.
- Use `UNKNOWN` for absent geographic metadata.
- Never claim legal compliance or complete dependency discovery.
- Keep the ordinary suite credential-free; live DataHub and OpenAI checks are opt-in.

---

## File Structure

- `src/changeproof/models.py`: enterprise SQL, region, artifact, and AI result models.
- `src/changeproof/demo.py`: generic scenario catalog plus AsterVale default scenario.
- `src/changeproof/sql_impact.py`: SQL Server discovery query, fixture module classification, and generated fixes.
- `src/changeproof/regions.py`: regional exposure aggregation and risk labels.
- `src/changeproof/artifacts.py`: JSON, SQL, rollback, validation, and SARIF artifacts.
- `src/changeproof/enterprise.py`: compose the existing impact/remediation analysis with SQL, region, and artifact evidence.
- `src/changeproof/ai_review.py`: explicit, bounded OpenAI review with deterministic fallback state.
- `src/changeproof/app.py`: multi-page routes, artifact downloads, and AI review endpoint.
- `src/changeproof/templates/base.html`: shared shell, evidence badge, source summary, and navigation.
- `src/changeproof/templates/analyze.html`: enterprise change form and scenario catalog.
- `src/changeproof/templates/impact.html`: DataHub lineage and hidden SQL evidence.
- `src/changeproof/templates/regions.html`: region map, accessible table, owners, and review flags.
- `src/changeproof/templates/fixes.html`: generated fixes, validation, rollback, artifacts, and AI review.
- `src/changeproof/templates/rollout.html`: dependency-ordered rollout and unresolved risks.
- `src/changeproof/templates/datahub.html`: existing draft-and-approve write-back flow.
- `src/changeproof/static/styles.css`: navigation, page layout, region map, SQL diffs, status states, and responsive behavior.
- `scripts/seed_datahub.py`: AsterVale entities, lineage, owners, tags, domains, and regional properties.
- `demo/astervale/`: synthetic dbt project, seed, staging model, marts, profiles, and tests.
- `examples/astervale/`: sample generated artifacts visible to judges.
- `tests/unit/test_enterprise.py`: AsterVale scenario composition.
- `tests/unit/test_sql_impact.py`: SQL query, classification, fixes, and manual review.
- `tests/unit/test_regions.py`: regional aggregation and unknown coverage.
- `tests/unit/test_artifacts.py`: deterministic bundle and SARIF output.
- `tests/unit/test_ai_review.py`: opt-in gate and structured response validation.
- `tests/integration/test_enterprise_web.py`: routes, navigation, downloads, and hosted safety.
- `tests/integration/test_demo_dbt.py`: add AsterVale dbt build checks.
- `tests/integration/test_datahub_context.py`: add opt-in AsterVale live metadata assertions.
- `LICENSE`: Apache License 2.0 text.
- `README.md`, `docs/devpost-draft.md`, `docs/demo-video-script.md`: verified enterprise claims and three-minute flow.

---

### Task 1: Apache 2.0 and Enterprise Evidence Models

**Files:**
- Modify: `LICENSE`
- Modify: `README.md`
- Modify: `src/changeproof/models.py`
- Modify: `src/changeproof/demo.py`
- Test: `tests/unit/test_models.py`
- Test: `tests/unit/test_demo.py`

**Interfaces:**
- Produces: `SqlMatchKind`, `SqlDependency`, `RegionRisk`, `RegionExposure`, `ArtifactBundle`, and `AiReview`.
- Produces: optional `company_name`, `sql_dependencies`, `region_exposures`, `artifacts`, and `ai_review` fields on `DemoAnalysis`.
- Preserves: `analyze_demo_change(column: str, old_type: str, new_type: str) -> DemoAnalysis`.

- [ ] **Step 1: Write failing compatibility and AsterVale model tests**

```python
def test_demo_analysis_defaults_keep_sonicledger_compatible():
    result = analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")
    assert result.company_name == "SonicLedger"
    assert result.sql_dependencies == ()
    assert result.region_exposures == ()


def test_customer_id_is_the_astervale_enterprise_scenario():
    entry = CATALOG["customer_id"]
    assert entry.company_name == "AsterVale Living"
    assert entry.source_table == "stg_orders"
    assert entry.source_urn.startswith("urn:li:dataset:(urn:li:dataPlatform:dbt,astervale.")
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/unit/test_models.py tests/unit/test_demo.py -q`

Expected: FAIL because enterprise fields and the `customer_id` scenario do not exist.

- [ ] **Step 3: Add enterprise models and backward-compatible defaults**

```python
class SqlMatchKind(StrEnum):
    CONVERT = "convert"
    CAST = "cast"
    JOIN = "join"
    PREDICATE = "predicate"
    ASSIGNMENT = "assignment"
    DYNAMIC_SQL = "dynamic_sql"


class RegionRisk(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    REVIEW = "REVIEW"


class SqlDependency(BaseModel):
    schema_name: str
    object_name: str
    object_type: str
    snippet: str
    match_kind: SqlMatchKind
    confidence: Confidence
    proposed_sql: str | None = None
    manual_review_reason: str | None = None


class RegionExposure(BaseModel):
    region: str
    asset_names: list[str] = Field(default_factory=list)
    sql_objects: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    policy_flags: list[str] = Field(default_factory=list)
    risk: RegionRisk


class ArtifactBundle(BaseModel):
    impact_report_json: str
    discovery_query_sql: str
    proposed_fixes_sql: str
    validation_queries_sql: str
    rollback_sql: str
    sarif_json: str


class AiReview(BaseModel):
    status: str = "AI_REVIEWED"
    summary: str
    fix_notes: list[str] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
```

Add these exact backward-compatible fields to frozen `DemoAnalysis`:

```python
company_name: str = "SonicLedger"
platform_name: str = "sonicledger.models"
sql_dependencies: tuple[SqlDependency, ...] = ()
region_exposures: tuple[RegionExposure, ...] = ()
artifacts: ArtifactBundle | None = None
ai_review: AiReview | None = None
```

- [ ] **Step 4: Add AsterVale to the generic scenario catalog**

Add a `company_name` and `platform_name` to `DemoColumn`, use them when building URNs, and add `customer_id` as the first catalog option with AsterVale owners and downstream assets. Keep every existing SonicLedger entry unchanged.

- [ ] **Step 5: Replace the license and update the README label**

Use the unmodified Apache License 2.0 text from <https://www.apache.org/licenses/LICENSE-2.0.txt>. Change the README license statement to `Apache-2.0` without claiming submission eligibility is otherwise complete.

- [ ] **Step 6: Run tests and repository checks**

Run: `uv run pytest tests/unit/test_models.py tests/unit/test_demo.py -q`

Run: `uv run ruff check src/changeproof/models.py src/changeproof/demo.py tests/unit/test_models.py tests/unit/test_demo.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add LICENSE README.md src/changeproof/models.py src/changeproof/demo.py tests/unit/test_models.py tests/unit/test_demo.py
git commit -m "feat: add AsterVale enterprise scenario"
```

### Task 2: Hidden T-SQL Dependencies and Generated Fixes

**Files:**
- Create: `src/changeproof/sql_impact.py`
- Create: `tests/unit/test_sql_impact.py`

**Interfaces:**
- Consumes: `SqlDependency`, `SqlMatchKind`, and `Confidence` from `models.py`.
- Produces: `build_discovery_query(column_name: str) -> str`.
- Produces: `analyze_sql_modules(column_name: str, old_type: str, new_type: str, modules: tuple[SqlModule, ...] = ASTERVALE_SQL_MODULES) -> tuple[SqlDependency, ...]`.
- Produces: `SqlModule(schema_name: str, object_name: str, object_type: str, definition: str, regions: tuple[str, ...])`.

- [ ] **Step 1: Write failing query and classification tests**

```python
def test_discovery_query_is_read_only_and_searches_system_modules():
    query = build_discovery_query("customer_id")
    assert "sys.sql_modules" in query
    assert "sys.objects" in query
    assert "@column_name" in query
    assert all(token not in query.upper() for token in ("UPDATE ", "DELETE ", "DROP "))


def test_convert_match_generates_reviewable_bigint_fix():
    findings = analyze_sql_modules("customer_id", "varchar", "bigint")
    match = next(item for item in findings if item.object_name == "usp_reconcile_loyalty_customer")
    assert match.match_kind is SqlMatchKind.CONVERT
    assert "TRY_CONVERT(BIGINT" in match.proposed_sql


def test_dynamic_sql_is_manual_review_not_auto_fixed():
    findings = analyze_sql_modules("customer_id", "varchar", "bigint")
    match = next(item for item in findings if item.object_name == "usp_export_customer_segments")
    assert match.match_kind is SqlMatchKind.DYNAMIC_SQL
    assert match.proposed_sql is None
    assert match.manual_review_reason
```

- [ ] **Step 2: Run focused test and confirm failure**

Run: `uv run pytest tests/unit/test_sql_impact.py -q`

Expected: FAIL because `changeproof.sql_impact` does not exist.

- [ ] **Step 3: Implement the allowlisted discovery query and synthetic modules**

Create four fixtures: one `CONVERT`, one join/predicate, one view with a cast, and one dynamic SQL procedure. Keep definitions synthetic and small enough to show in the UI.

- [ ] **Step 4: Implement classification and proposed fixes**

Parse with `sqlglot.parse_one(definition, read="tsql")`. Use bounded case-insensitive matching only when parsing fails. Generate a proposed replacement only for a recognized static expression. Assign `LOW` confidence and manual review to dynamic SQL and parser failures.

- [ ] **Step 5: Run tests and Ruff**

Run: `uv run pytest tests/unit/test_sql_impact.py -q`

Run: `uv run ruff check src/changeproof/sql_impact.py tests/unit/test_sql_impact.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/changeproof/sql_impact.py tests/unit/test_sql_impact.py
git commit -m "feat: analyze hidden T-SQL dependencies"
```

### Task 3: Regional Exposure Engine

**Files:**
- Create: `src/changeproof/regions.py`
- Create: `tests/unit/test_regions.py`

**Interfaces:**
- Consumes: `MetadataEvidence`, `SqlDependency`, `RegionExposure`, and `RegionRisk`.
- Produces: `assess_regions(evidence: MetadataEvidence, sql_dependencies: tuple[SqlDependency, ...], asset_regions: Mapping[str, AssetRegionMetadata]) -> tuple[RegionExposure, ...]`.
- Produces: `AssetRegionMetadata(regions: tuple[str, ...], owners: tuple[str, ...], policy_flags: tuple[str, ...], contains_customer_data: bool)`.

- [ ] **Step 1: Write failing aggregation tests**

```python
def test_regions_include_operating_areas_and_unknown():
    exposures = assess_regions(evidence(), dependencies(), metadata())
    assert [item.region for item in exposures] == [
        "NORTHEAST", "SOUTH", "MIDWEST", "WEST", "UNKNOWN"
    ]


def test_customer_data_and_critical_assets_raise_region_risk():
    west = next(item for item in assess_regions(evidence(), dependencies(), metadata()) if item.region == "WEST")
    assert west.risk is RegionRisk.HIGH
    assert "CA_PRIVACY_REVIEW" in west.policy_flags
```

- [ ] **Step 2: Run focused test and confirm failure**

Run: `uv run pytest tests/unit/test_regions.py -q`

Expected: FAIL because the region engine does not exist.

- [ ] **Step 3: Implement deterministic region aggregation**

Use the fixed display order `NORTHEAST`, `SOUTH`, `MIDWEST`, `WEST`, `UNKNOWN`. Deduplicate asset names, SQL objects, owners, and flags. Set risk to high for critical customer-data exposure, review for missing ownership or unknown region, and medium otherwise.

- [ ] **Step 4: Run tests and Ruff**

Run: `uv run pytest tests/unit/test_regions.py -q`

Run: `uv run ruff check src/changeproof/regions.py tests/unit/test_regions.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/changeproof/regions.py tests/unit/test_regions.py
git commit -m "feat: calculate geographic change exposure"
```

### Task 4: Artifact Bundle and Enterprise Composition

**Files:**
- Create: `src/changeproof/artifacts.py`
- Create: `src/changeproof/enterprise.py`
- Create: `tests/unit/test_artifacts.py`
- Create: `tests/unit/test_enterprise.py`
- Modify: `src/changeproof/app.py`

**Interfaces:**
- Consumes: AsterVale `DemoAnalysis`, SQL dependencies, and region exposures.
- Produces: `build_artifacts(analysis: DemoAnalysis) -> ArtifactBundle`.
- Produces: `analyze_enterprise_change(column: str, old_type: str, new_type: str) -> DemoAnalysis`.
- Changes default provider: bundled mode returns `analyze_enterprise_change`.

- [ ] **Step 1: Write failing composition and artifact tests**

```python
def test_enterprise_analysis_composes_all_evidence():
    result = analyze_enterprise_change(column="customer_id", old_type="varchar", new_type="bigint")
    assert result.company_name == "AsterVale Living"
    assert result.sql_dependencies
    assert result.region_exposures
    assert result.artifacts is not None


def test_artifact_bundle_contains_json_sql_and_sarif():
    bundle = analyze_enterprise_change(column="customer_id", old_type="varchar", new_type="bigint").artifacts
    assert json.loads(bundle.impact_report_json)["company"] == "AsterVale Living"
    assert "TRY_CONVERT" in bundle.proposed_fixes_sql
    assert json.loads(bundle.sarif_json)["version"] == "2.1.0"
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/unit/test_artifacts.py tests/unit/test_enterprise.py -q`

Expected: FAIL because composition and artifacts do not exist.

- [ ] **Step 3: Implement deterministic artifacts**

Use `json.dumps(..., indent=2, sort_keys=True)`. Include evidence source, confidence, affected assets, SQL matches, regions, proposed fixes, validation SQL, rollback SQL, and unresolved risks. SARIF results point to synthetic `database://schema/object` URIs and carry confidence plus manual-review text.

- [ ] **Step 4: Implement enterprise composition and default provider**

Call `analyze_demo_change`, enrich only the AsterVale `customer_id` scenario, and return SonicLedger analyses unchanged. Use `dataclasses.replace` on the frozen dataclass. Point bundled mode to the enterprise provider while preserving live mode.

- [ ] **Step 5: Run focused and existing provider tests**

Run: `uv run pytest tests/unit/test_artifacts.py tests/unit/test_enterprise.py tests/integration/test_web.py -q`

Expected: PASS after updating assertions that intentionally change the default scenario.

- [ ] **Step 6: Commit**

```bash
git add src/changeproof/artifacts.py src/changeproof/enterprise.py src/changeproof/app.py tests/unit/test_artifacts.py tests/unit/test_enterprise.py tests/integration/test_web.py
git commit -m "feat: compose enterprise change artifacts"
```

### Task 5: Multi-Page Enterprise Dashboard

**Files:**
- Create: `src/changeproof/templates/base.html`
- Create: `src/changeproof/templates/analyze.html`
- Create: `src/changeproof/templates/impact.html`
- Create: `src/changeproof/templates/regions.html`
- Create: `src/changeproof/templates/fixes.html`
- Create: `src/changeproof/templates/rollout.html`
- Create: `src/changeproof/templates/datahub.html`
- Modify: `src/changeproof/app.py`
- Modify: `src/changeproof/static/styles.css`
- Modify: `tests/integration/test_web.py`
- Create: `tests/integration/test_enterprise_web.py`

**Interfaces:**
- Consumes: `analyze_enterprise_change` and one shared template context.
- Produces routes: `GET /`, `/impact`, `/regions`, `/fixes`, `/rollout`, `/datahub`.
- Produces route: `GET /artifacts/{artifact_name}` for six allowlisted artifact names.
- Preserves route: `POST /analyze` and `POST /writeback/apply`.

- [ ] **Step 1: Write failing route and safety tests**

```python
@pytest.mark.parametrize("path", ["/", "/impact", "/regions", "/fixes", "/rollout", "/datahub"])
def test_enterprise_pages_share_navigation_and_change(path):
    response = client.get(path)
    assert response.status_code == 200
    assert "AsterVale Living" in response.text
    assert "customer_id" in response.text
    for href in ("/impact", "/regions", "/fixes", "/rollout", "/datahub"):
        assert f'href="{href}"' in response.text


def test_artifacts_are_allowlisted():
    assert client.get("/artifacts/proposed-fixes.sql").status_code == 200
    assert client.get("/artifacts/secret.env").status_code == 404
```

- [ ] **Step 2: Run integration tests and confirm failure**

Run: `uv run pytest tests/integration/test_enterprise_web.py -q`

Expected: FAIL because the routes and templates do not exist.

- [ ] **Step 3: Extract a shared template shell**

Move the brand, evidence badge, source summary, persistent navigation, flash messages, and footer into `base.html`. Keep the evidence mode visible on every page and add active-page `aria-current="page"`.

- [ ] **Step 4: Implement six page templates**

Reuse current analyzer, lineage, rollout, and write-back markup. Add hidden SQL evidence, an accessible region table plus stylized region grid, side-by-side proposed SQL, validation and rollback blocks, artifact links, and unresolved-risk states.

- [ ] **Step 5: Implement stateless routes and allowlisted downloads**

Use one helper:

```python
def enterprise_context(request: Request, *, page: str) -> dict[str, object]:
    analysis = current_provider()(**DEFAULT_VALUES)
    return {
        "request": request,
        "page": page,
        "analysis": analysis,
        "values": DEFAULT_VALUES,
        "proposals": build_proposals(analysis),
        "simulated_mode": writeback_mode() == "simulated",
    }
```

Map artifact names to `(content, media_type)` in a constant dictionary created from the server-recomputed bundle. Return 404 for every other name.

- [ ] **Step 6: Add responsive styles and evidence states**

Use existing DataHub-aligned tokens. Add keyboard-visible navigation, CSS-only region geometry, code wrapping, two-column diffs, status chips, and breakpoints at 900px and 640px. Keep the region table visible to screen readers and mobile users.

- [ ] **Step 7: Run web tests and full template regression**

Run: `uv run pytest tests/integration/test_enterprise_web.py tests/integration/test_web.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/changeproof/app.py src/changeproof/templates src/changeproof/static/styles.css tests/integration/test_web.py tests/integration/test_enterprise_web.py
git commit -m "feat: add enterprise impact dashboards"
```

### Task 6: Explicit OpenAI Review

**Files:**
- Create: `src/changeproof/ai_review.py`
- Modify: `src/changeproof/app.py`
- Modify: `src/changeproof/templates/fixes.html`
- Modify: `src/changeproof/models.py`
- Create: `tests/unit/test_ai_review.py`
- Modify: `tests/integration/test_enterprise_web.py`

**Interfaces:**
- Consumes: deterministic `DemoAnalysis` and `Settings.openai_api_key`.
- Produces: `review_analysis(analysis: DemoAnalysis, settings: Settings | None = None, client: OpenAI | None = None) -> AiReview`.
- Produces route: `POST /ai-review`.

- [ ] **Step 1: Write failing gate and structured-review tests**

```python
def test_review_requires_configured_key():
    with pytest.raises(AiReviewUnavailable, match="OPENAI_API_KEY"):
        review_analysis(analysis(), settings=Settings(openai_api_key=""))


def test_review_uses_only_deterministic_evidence(fake_openai):
    result = review_analysis(analysis(), settings=Settings(openai_api_key="configured"), client=fake_openai)
    assert result.status == "AI_REVIEWED"
    assert result.summary
    assert fake_openai.last_input["company"] == "AsterVale Living"
    assert "api_key" not in fake_openai.last_input
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `uv run pytest tests/unit/test_ai_review.py -q`

Expected: FAIL because the AI reviewer does not exist.

- [ ] **Step 3: Implement the bounded Responses API call**

Build a compact JSON evidence payload from the existing analysis. Request JSON containing `summary`, `fix_notes`, and `unresolved_risks`. Validate with `AiReview.model_validate_json`. Reject output that names an asset or SQL object absent from the evidence bundle. Cache successful reviews by a SHA-256 hash of the deterministic payload for the process lifetime.

- [ ] **Step 4: Add the explicit route and UI action**

`GET /fixes` makes no OpenAI call. `POST /ai-review` recomputes the analysis, calls the reviewer, and renders `fixes.html` with either a labeled `AI_REVIEWED` result or a visible unavailable/error state. Never include the key in logs or templates.

- [ ] **Step 5: Run unit and web tests**

Run: `uv run pytest tests/unit/test_ai_review.py tests/integration/test_enterprise_web.py -q`

Expected: PASS with a fake client and no network request.

- [ ] **Step 6: Commit**

```bash
git add src/changeproof/ai_review.py src/changeproof/app.py src/changeproof/templates/fixes.html src/changeproof/models.py tests/unit/test_ai_review.py tests/integration/test_enterprise_web.py
git commit -m "feat: add bounded AI fix review"
```

### Task 7: Richer DataHub Write-Back and Live AsterVale Metadata

**Files:**
- Modify: `src/changeproof/writeback.py`
- Modify: `scripts/seed_datahub.py`
- Modify: `tests/unit/test_writeback.py`
- Modify: `tests/unit/test_seed_datahub.py`
- Modify: `tests/integration/test_datahub_context.py`

**Interfaces:**
- Consumes: enterprise SQL and region evidence already present on `DemoAnalysis`.
- Produces: incident body sections `Hidden SQL consumers`, `Regional exposure`, and `Evidence limits`.
- Preserves: item-level proposal IDs and server-side proposal reconstruction.

- [ ] **Step 1: Write failing write-back content tests**

```python
def test_enterprise_incident_includes_sql_regions_and_limits(enterprise_analysis):
    incident = next(p for p in build_proposals(enterprise_analysis) if p.action is ProposalAction.RAISE_INCIDENT)
    assert "Hidden SQL consumers" in incident.body
    assert "Regional exposure" in incident.body
    assert "dynamic SQL" in incident.body
    assert "UNKNOWN" in incident.body
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `uv run pytest tests/unit/test_writeback.py tests/unit/test_seed_datahub.py -q`

Expected: FAIL because enterprise evidence is not included or seeded.

- [ ] **Step 3: Extend deterministic proposal content**

Format bounded lists of SQL objects and regions. Include counts and manual-review reasons. Do not embed full procedure definitions or artifact bodies in DataHub descriptions.

- [ ] **Step 4: Seed AsterVale metadata into local DataHub**

Emit AsterVale datasets, owners, critical tags, table and fine-grained column lineage, Commerce/Customer/Operations/Finance domains, and the namespaced regional structured properties from the design. Keep SonicLedger seeding available behind its existing path until the new live test passes.

- [ ] **Step 5: Run unit tests and optional live verification when DataHub is available**

Run: `uv run pytest tests/unit/test_writeback.py tests/unit/test_seed_datahub.py -q`

Optional live run: `CHANGE_PROOF_LIVE_DATAHUB=1 uv run pytest tests/integration/test_datahub_context.py -q`

Expected: unit tests PASS; live test PASS only when local DataHub is running.

- [ ] **Step 6: Commit**

```bash
git add src/changeproof/writeback.py scripts/seed_datahub.py tests/unit/test_writeback.py tests/unit/test_seed_datahub.py tests/integration/test_datahub_context.py
git commit -m "feat: write enterprise findings to DataHub"
```

### Task 8: Synthetic dbt Project and Judge-Visible Samples

**Files:**
- Create: `demo/astervale/dbt_project.yml`
- Create: `demo/astervale/profiles.yml`
- Create: `demo/astervale/seeds/raw_orders.csv`
- Create: `demo/astervale/models/staging/stg_orders.sql`
- Create: `demo/astervale/models/marts/fct_order_sales.sql`
- Create: `demo/astervale/models/marts/loyalty_customer_value.sql`
- Create: `demo/astervale/models/marts/regional_returns.sql`
- Create: `demo/astervale/models/schema.yml`
- Modify: `Makefile`
- Modify: `tests/integration/test_demo_dbt.py`
- Create: `examples/astervale/impact-report.json`
- Create: `examples/astervale/proposed-fixes.sql`
- Create: `examples/astervale/validation-queries.sql`
- Create: `examples/astervale/rollback.sql`
- Create: `examples/astervale/changeproof.sarif`
- Create: `scripts/generate_astervale_artifacts.py`

**Interfaces:**
- Produces: `make enterprise-baseline`.
- Produces: judge-readable sample artifacts generated from the same deterministic builders as the app.

- [ ] **Step 1: Write failing dbt integration test**

```python
def test_astervale_dbt_project_builds(tmp_path):
    result = run_dbt("build", project="demo/astervale", target_path=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "model.astervale.stg_orders" in manifest["nodes"]
    assert "model.astervale.loyalty_customer_value" in manifest["nodes"]
```

- [ ] **Step 2: Run the test and confirm failure**

Run: `uv run pytest tests/integration/test_demo_dbt.py -q`

Expected: FAIL because `demo/astervale` does not exist.

- [ ] **Step 3: Add synthetic rows and dbt lineage**

Use ten clearly synthetic customer IDs and orders spanning Northeast, South, Midwest, West, plus one unknown region. Models must carry `customer_id` through fine-grained lineage and include no real names, addresses, emails, or payment details.

- [ ] **Step 4: Add the Make target and generate samples**

Add:

```make
enterprise-baseline:
	uv run dbt seed --project-dir demo/astervale --profiles-dir demo/astervale
	uv run dbt build --project-dir demo/astervale --profiles-dir demo/astervale
```

Generate sample files with `scripts/generate_astervale_artifacts.py`, which calls `build_artifacts(analyze_enterprise_change(...))`. Verify the files equal current builder output in `test_artifacts.py`.

- [ ] **Step 5: Run dbt and artifact tests**

Run: `uv run pytest tests/integration/test_demo_dbt.py tests/unit/test_artifacts.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add demo/astervale Makefile tests/integration/test_demo_dbt.py examples/astervale tests/unit/test_artifacts.py
git commit -m "feat: add AsterVale data pipeline and samples"
```

### Task 9: Submission Documentation and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/devpost-draft.md`
- Modify: `docs/demo-video-script.md`
- Modify: `docs/judging-positioning.md`

**Interfaces:**
- Consumes: only behavior verified in Tasks 1 through 8.
- Produces: exact setup commands, public-demo boundaries, sample-output links, and a sub-three-minute script.

- [ ] **Step 1: Update documentation with verified capabilities**

Document AsterVale, all six pages, DataHub evidence, SQL evidence, regions, generated artifacts, explicit AI review, simulation labels, Apache 2.0, ordinary setup, and optional live DataHub setup. Do not claim live SQL Server execution unless separately implemented and verified.

- [ ] **Step 2: Run the complete automated suite**

Run: `uv run pytest -q`

Expected: all ordinary tests pass; the live DataHub test remains skipped unless explicitly enabled.

- [ ] **Step 3: Run static checks**

Run: `uv run ruff check .`

Run: `git diff --check`

Expected: both exit 0.

- [ ] **Step 4: Run local visual QA**

Start: `CHANGE_PROOF_WRITEBACK_MODE=simulated uv run uvicorn changeproof.app:app --port 8000`

Inspect all six routes at desktop and mobile widths. Verify navigation, active state, region table, SQL wrapping, artifact downloads, AI-off state, simulated write-back label, and error pages.

- [ ] **Step 5: Run a safe OpenAI smoke test only if explicitly enabled**

Run against the deployed Railway service or a local environment with a configured key by clicking `Run AI review` once. Verify a labeled AI response and confirm no key or raw credential appears in logs. If the call fails, keep deterministic mode and remove AI claims from submission materials.

- [ ] **Step 6: Commit documentation and final source state**

```bash
git add README.md docs/devpost-draft.md docs/demo-video-script.md docs/judging-positioning.md
git commit -m "docs: prepare enterprise judge submission"
```

- [ ] **Step 7: Stop before external release actions**

Report local, committed, and verified states separately. Do not push, deploy, record/upload the video, or submit Devpost until those external actions are explicitly authorized and each preceding verification is current.
