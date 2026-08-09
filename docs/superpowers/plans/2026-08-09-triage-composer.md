# DataHub Triage Composer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a transparent SRS-to-metadata mapper that produces a complex cross-domain incident query and shows every DataHub metadata use.

**Architecture:** A focused `triage.py` module owns bounded rule extraction, deterministic metadata mapping, query composition, and text export. FastAPI routes render one new page and stateless POST exports; the browser reads allowed text files into the existing textarea, so uploaded files are never persisted.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, Jinja2, SQL Server SQL, pytest, existing ReportLab PDF helper, vanilla browser JavaScript.

## Global Constraints

- Hosted Railway output must say it uses bundled synthetic DataHub-shaped metadata.
- Generated SQL is review-required and is never executed.
- Accept at most 20,000 characters and extract at most 20 rules.
- Browser upload allowlist is `.txt,.md,.sql,.csv`; no uploaded file is persisted.
- Preserve the existing orange, blue, and white design and readable body text.
- Every major section includes a concise “Like I’m five” explanation.

---

### Task 1: Deterministic triage and query engine

**Files:**
- Create: `src/changeproof/triage.py`
- Create: `src/changeproof/static/astervale-ar-incident-srs.txt`
- Create: `tests/unit/test_triage.py`

**Interfaces:**
- Produces: `SAMPLE_INCIDENT_QUESTION: str`, `SAMPLE_SRS_TEXT: str`, `TriageResult`, `build_triage_result(question: str, requirements_text: str) -> TriageResult`, and `triage_export_text(result: TriageResult) -> str`.
- `TriageResult` exposes `rules`, `mappings`, `datahub_steps`, `sql`, `validation_sql`, `warnings`, `domains`, and `evidence_mode` for Task 2.

- [ ] **Step 1: Write failing behavioral tests**

```python
def test_sample_srs_maps_cross_domain_rules_and_builds_complex_sql():
    result = build_triage_result(SAMPLE_INCIDENT_QUESTION, SAMPLE_SRS_TEXT)
    assert len(result.domains) >= 6
    assert result.sql.count(" AS (") >= 8
    assert "UNION ALL" in result.sql
    assert "running_balance" in result.sql
    assert len(result.datahub_steps) >= 6

def test_unknown_rule_is_flagged_instead_of_inventing_an_asset():
    result = build_triage_result("Investigate", "Use lunar weather color.")
    assert result.rules[0].status == "UNMAPPED"
    assert result.rules[0].asset_urn is None
    assert result.warnings

def test_input_limits_are_enforced():
    with pytest.raises(ValueError, match="20,000"):
        build_triage_result("Investigate", "x" * 20_001)
```

- [ ] **Step 2: Run `uv run pytest tests/unit/test_triage.py -q` and confirm collection or import fails because the feature does not exist.**
- [ ] **Step 3: Implement the bounded catalog, rule mapper, at-least-eight-CTE SQL composer, validation SQL, touchpoint trail, and plain-text export.**
- [ ] **Step 4: Run `uv run pytest tests/unit/test_triage.py -q` and confirm all tests pass.**
- [ ] **Step 5: Commit only Task 1 files with `feat: add DataHub triage query engine`.**

### Task 2: Triage Composer web experience and downloads

**Files:**
- Modify: `src/changeproof/app.py`
- Modify: `src/changeproof/templates/base.html`
- Create: `src/changeproof/templates/triage.html`
- Modify: `src/changeproof/static/styles.css`
- Modify: `tests/integration/test_enterprise_web.py`

**Interfaces:**
- Consumes: Task 1’s `build_triage_result`, `triage_export_text`, sample constants, and `TriageResult` fields.
- Produces: GET `/triage`, POST `/triage`, and POST `/triage/export/{format}` where format is `sql`, `txt`, or `pdf`.

- [ ] **Step 1: Add failing integration tests**

```python
def test_triage_page_shows_sample_mapping_complex_sql_and_datahub_trail():
    response = client.get("/triage")
    assert response.status_code == 200
    assert "Triage Composer" in response.text
    assert "How DataHub helped" in response.text
    assert "finance.ar_transactions" in response.text
    assert "running_balance" in response.text

def test_triage_accepts_requirements_and_flags_unknown_rules():
    response = client.post("/triage", data={"question": "Investigate", "requirements_text": "Use lunar weather color."})
    assert response.status_code == 200
    assert "UNMAPPED" in response.text

@pytest.mark.parametrize(("format", "content_type"), [("sql", "text/plain"), ("txt", "text/plain"), ("pdf", "application/pdf")])
def test_triage_exports(format, content_type):
    response = client.post(f"/triage/export/{format}", data={"question": SAMPLE_INCIDENT_QUESTION, "requirements_text": SAMPLE_SRS_TEXT})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
```

- [ ] **Step 2: Run the three new tests and confirm they fail because `/triage` does not exist.**
- [ ] **Step 3: Register the template and routes, reuse `pdf_bytes`, validate export format before running generation, and keep all processing stateless.**
- [ ] **Step 4: Build the accessible page with local file reading, example loading, mapping table, domain summary, DataHub touchpoint cards, readable SQL, warnings, and SQL/TXT/PDF submit buttons.**
- [ ] **Step 5: Add responsive orange/blue/white styles with body and code text no smaller than 13px in primary result areas.**
- [ ] **Step 6: Run `uv run pytest tests/integration/test_enterprise_web.py -q` and confirm all integration tests pass.**
- [ ] **Step 7: Commit Task 2 files with `feat: add SRS triage composer experience`.**

### Task 3: Judge narrative and full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-video-script.md`
- Modify: `docs/judging-positioning.md`

**Interfaces:**
- Consumes: the verified routes and truthful hosted/local boundary from Tasks 1–2.
- Produces: a concise judge flow explaining repeated DataHub use and the complex query output.

- [ ] **Step 1: Update the README feature list and judge demo path with `/triage` first, preserving the synthetic-hosted versus real-local boundary.**
- [ ] **Step 2: Add a 45–60 second Triage Composer segment to the video script: upload SRS, show six domains, show repeated DataHub touchpoints, reveal generated SQL, download evidence.**
- [ ] **Step 3: Update judging positioning with the sentence: “DataHub supplies the enterprise context; ChangeProof composes the investigation and proves where every input came from.”**
- [ ] **Step 4: Run `uv run ruff check .` and `uv run pytest -q`; resolve any failures.**
- [ ] **Step 5: Commit Task 3 files with `docs: add triage composer judge story`.**

