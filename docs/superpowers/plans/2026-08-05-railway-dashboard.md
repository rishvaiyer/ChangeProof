# ChangeProof Railway Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a public ChangeProof dashboard that demonstrates downstream impact analysis and a proposed safe rollout using bundled SonicLedger metadata.

**Architecture:** A deterministic demo service will produce the same typed request, evidence, impact, and remediation models used by the live DataHub path. A small FastAPI application will render those results with Jinja2, expose a health endpoint, and run on Railway through a checked-in start command.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, Pydantic, Uvicorn, pytest, Ruff, Railway Nixpacks

## Global Constraints

- Deploy to a new Railway project without modifying existing Railway services.
- Hosted demo mode uses bundled SonicLedger metadata and clearly labels that evidence source.
- Preserve the existing live DataHub MCP adapter and its local integration test.
- Bind Uvicorn to `0.0.0.0:$PORT` in Railway.
- Do not require DataHub or OpenAI credentials for the hosted deterministic demo.
- Verify `/`, `/analyze`, and `/healthz` against the public Railway domain.

---

### Task 1: Deterministic Demo Analysis Service

**Files:**
- Create: `src/changeproof/demo.py`
- Create: `tests/unit/test_demo.py`

**Interfaces:**
- Consumes: `classify_schema_change(...)`, `assess_impact(evidence)`, and `plan_remediation(request, impact)`.
- Produces: `DemoAnalysis` and `analyze_demo_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis`.

- [ ] **Step 1: Write the failing service tests**

```python
from changeproof.demo import analyze_demo_change
from changeproof.models import ChangeType, Confidence


def test_analyze_demo_type_change_returns_impact_and_safe_plan() -> None:
    result = analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")

    assert result.request.change_type is ChangeType.COLUMN_TYPE_CHANGE
    assert result.impact.confidence is Confidence.HIGH
    assert [asset.name for asset in result.impact.impacted_assets] == [
        "fct_royalties",
        "artist_payouts",
        "finance_royalty_dashboard",
    ]
    assert result.plan.strategy == "parallel_typed_field"
    assert result.plan.rollout_steps


def test_analyze_demo_rejects_unknown_column() -> None:
    with pytest.raises(ValueError, match="Supported demo column: artist_id"):
        analyze_demo_change(column="unknown", old_type="varchar", new_type="bigint")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `uv run pytest tests/unit/test_demo.py -q`

Expected: collection fails because `changeproof.demo` does not exist.

- [ ] **Step 3: Implement the typed demo service**

```python
from dataclasses import dataclass
from pathlib import Path

from .classifier import classify_schema_change
from .impact import assess_impact
from .models import ChangeRequest, ImpactAssessment, LineageNode, MetadataEvidence, RemediationPlan
from .planner import plan_remediation

SOURCE_URN = "urn:li:dataset:(urn:li:dataPlatform:dbt,sonicledger.models.staging.stg_streams,PROD)"


@dataclass(frozen=True)
class DemoAnalysis:
    request: ChangeRequest
    evidence: MetadataEvidence
    impact: ImpactAssessment
    plan: RemediationPlan


def analyze_demo_change(*, column: str, old_type: str, new_type: str) -> DemoAnalysis:
    if column != "artist_id":
        raise ValueError("Supported demo column: artist_id")
    if not old_type.strip() or not new_type.strip() or old_type == new_type:
        raise ValueError("Old and new types must be different non-empty values.")

    request = classify_schema_change(
        before_schema=[{"fieldPath": column, "nativeDataType": old_type}],
        after_schema=[{"fieldPath": column, "nativeDataType": new_type}],
        source_file=Path("models/staging/stg_streams.sql"),
        dataset_urn=SOURCE_URN,
    )
    evidence = _demo_evidence()
    impact = assess_impact(evidence)
    return DemoAnalysis(
        request=request,
        evidence=evidence,
        impact=impact,
        plan=plan_remediation(request, impact),
    )
```

Implement `_demo_evidence()` with source owner `analytics@sonicledger.demo` and three ordered `LineageNode` values: `fct_royalties` at hop 1, `artist_payouts` at hop 2 and critical, and `finance_royalty_dashboard` at hop 3 and critical. All nodes use `artist_id`, finance ownership, fresh metadata, passing assertions, and complete column lineage.

- [ ] **Step 4: Run the service tests and verify GREEN**

Run: `uv run pytest tests/unit/test_demo.py -q`

Expected: `2 passed`.

- [ ] **Step 5: Commit the service**

```bash
git add src/changeproof/demo.py tests/unit/test_demo.py
git commit -m "feat: add deterministic ChangeProof demo analysis"
```

### Task 2: FastAPI Dashboard and Routes

**Files:**
- Create: `src/changeproof/app.py`
- Create: `src/changeproof/templates/index.html`
- Create: `src/changeproof/static/styles.css`
- Create: `tests/integration/test_web.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `analyze_demo_change(column, old_type, new_type) -> DemoAnalysis` from Task 1.
- Produces: ASGI application `changeproof.app:app` with `GET /`, `POST /analyze`, and `GET /healthz`.

- [ ] **Step 1: Add Jinja2 and package-data declarations**

Add `"jinja2"` to project dependencies and add:

```toml
[tool.setuptools.package-data]
changeproof = ["templates/*.html", "static/*.css"]
```

Run: `uv lock`

- [ ] **Step 2: Write failing route tests**

```python
from fastapi.testclient import TestClient
from changeproof.app import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "changeproof"}


def test_dashboard_labels_demo_evidence() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "ChangeProof" in response.text
    assert "Bundled SonicLedger demo metadata" in response.text


def test_analyze_renders_downstream_impact_and_safe_fix() -> None:
    response = client.post(
        "/analyze",
        data={"column": "artist_id", "old_type": "varchar", "new_type": "bigint"},
    )
    assert response.status_code == 200
    assert "artist_payouts" in response.text
    assert "parallel_typed_field" in response.text
    assert "Proposed safe rollout" in response.text


def test_analyze_returns_validation_message() -> None:
    response = client.post(
        "/analyze",
        data={"column": "unknown", "old_type": "varchar", "new_type": "bigint"},
    )
    assert response.status_code == 422
    assert "Supported demo column" in response.text
```

- [ ] **Step 3: Run route tests and verify RED**

Run: `uv run pytest tests/integration/test_web.py -q`

Expected: collection fails because `changeproof.app` does not exist.

- [ ] **Step 4: Implement the FastAPI application**

```python
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .demo import analyze_demo_change

PACKAGE_DIR = Path(__file__).parent
app = FastAPI(title="ChangeProof")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "changeproof"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    analysis = analyze_demo_change(column="artist_id", old_type="varchar", new_type="bigint")
    return templates.TemplateResponse(request, "index.html", {"analysis": analysis, "error": None})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(request: Request) -> HTMLResponse:
    form = parse_qs((await request.body()).decode("utf-8"))
    values = {key: items[0] if items else "" for key, items in form.items()}
    try:
        analysis = analyze_demo_change(
            column=values.get("column", ""),
            old_type=values.get("old_type", ""),
            new_type=values.get("new_type", ""),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"analysis": None, "error": str(exc), "values": values},
            status_code=422,
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"analysis": analysis, "error": None, "values": values},
    )
```

Build `index.html` as an accessible one-page dashboard with a header, evidence-source badge, three-field analysis form, confidence and strategy cards, downstream asset cards with hop/owner/critical labels, and ordered rollout/rollback sections. Use Jinja autoescaping and render only model values. Build responsive CSS with a dark navy interface, cyan and amber accents, readable focus states, and no external assets.

- [ ] **Step 5: Run route tests and verify GREEN**

Run: `uv run pytest tests/integration/test_web.py -q`

Expected: `4 passed`.

- [ ] **Step 6: Run the local app smoke check**

Run: `uv run uvicorn changeproof.app:app --host 127.0.0.1 --port 8765`

Verify in a second command: `curl -fsS http://127.0.0.1:8765/healthz`

Expected: `{"status":"ok","service":"changeproof"}`.

- [ ] **Step 7: Commit the dashboard**

```bash
git add pyproject.toml uv.lock src/changeproof/app.py src/changeproof/templates/index.html src/changeproof/static/styles.css tests/integration/test_web.py
git commit -m "feat: add ChangeProof impact dashboard"
```

### Task 3: Railway Configuration and Verification

**Files:**
- Create: `railway.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: ASGI target `changeproof.app:app` from Task 2.
- Produces: Railway Nixpacks deployment and public application URL.

- [ ] **Step 1: Add Railway configuration**

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {"builder": "NIXPACKS"},
  "deploy": {
    "startCommand": "uvicorn changeproof.app:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/healthz",
    "healthcheckTimeout": 120,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

Document local startup, hosted demo-mode truth, and the three public routes in `README.md`.

- [ ] **Step 2: Verify configuration and the full local suite**

Run:

```bash
python -m json.tool railway.json >/dev/null
uv run ruff check .
uv run pytest -q
git diff --check
```

Expected: JSON validation succeeds, Ruff reports no errors, and the test suite reports zero failures.

- [ ] **Step 3: Commit deployment configuration**

```bash
git add railway.json README.md
git commit -m "chore: configure ChangeProof for Railway"
```

- [ ] **Step 4: Create and deploy a new Railway project**

Confirm `railway whoami` reports the intended account. Run `railway init --name changeproof`, link the created project, and run `railway up --detach` from the clean `codex/changeproof-implementation` checkout. If the exact project name is unavailable, use `changeproof-demo`.

Do not set `DATAHUB_GMS_TOKEN` or `OPENAI_API_KEY`. Generate a public domain with `railway domain` after the deployment reaches success.

- [ ] **Step 5: Verify the exact public deployment**

Run `railway status` and `railway deployment list`. Copy the newest deployment identifier into `CHANGE_PROOF_DEPLOYMENT_ID`, then run `railway logs --deployment "$CHANGE_PROOF_DEPLOYMENT_ID"` to confirm the service started from the current commit.

Verify:

```bash
CHANGE_PROOF_PUBLIC_URL="$(railway domain | rg -o 'https://[^[:space:]]+' | tail -1)"
curl -fsS "$CHANGE_PROOF_PUBLIC_URL/healthz"
curl -fsS "$CHANGE_PROOF_PUBLIC_URL/" | rg "ChangeProof|Bundled SonicLedger demo metadata"
curl -fsS -X POST "$CHANGE_PROOF_PUBLIC_URL/analyze" \
  -H 'content-type: application/x-www-form-urlencoded' \
  --data 'column=artist_id&old_type=varchar&new_type=bigint' \
  | rg "artist_payouts|parallel_typed_field|Proposed safe rollout"
```

Expected: health JSON is correct and both page checks match all expected content.

- [ ] **Step 6: Record final deployment truth**

Report the public URL, Railway project/service names, deployed commit, test counts, and whether each live route passed. Do not call the hosted demo live-DataHub-connected.
