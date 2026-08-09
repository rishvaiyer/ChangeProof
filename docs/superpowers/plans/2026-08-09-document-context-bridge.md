# Document Context Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Triage Composer accept common SRS/incident documents, extract their text, ground the requirements in DataHub context, and produce reviewable SQL and exports.

**Architecture:** Add a format-specific text extraction module, an optional structured OpenAI interpretation step, and a DataHub MCP enrichment boundary. The live boundary supports DataHub Cloud Streamable HTTP through `DATAHUB_MCP_URL`/`DATAHUB_MCP_TOKEN` and the existing self-hosted stdio path. The existing deterministic catalog remains the hosted fallback; live MCP enrichment is enabled only when explicitly configured and is labeled in the result. The FastAPI route accepts multipart uploads and preserves the existing paste/export flow.

**Tech Stack:** Python 3.12, FastAPI, Starlette multipart forms, pypdf, stdlib ZIP/XML DOCX extraction, OpenAI Responses API structured output, existing MCP client, Jinja2, pytest, Ruff.

## Global Constraints

- Preserve the existing 20,000-character and 20-rule limits after extraction.
- Support PDF, DOCX, TXT, Markdown, SQL, and CSV; reject unsupported, empty, encrypted, unreadable, and oversized files plainly.
- Uploaded binaries and document contents are not persisted.
- OpenAI receives extracted text only when the user invokes the AI action; AI cannot invent metadata or execution results.
- DataHub MCP is authoritative only for metadata returned by bounded `search`, `get_entities`, `list_schema_fields`, `get_lineage`, and optional `get_dataset_queries` calls; otherwise label bundled synthetic context.
- Never execute generated SQL.
- Do not require Docker or a local DataHub instance for the hosted demo.

---

### Task 1: Add document text extraction

**Files:**
- Create: `src/changeproof/document_ingest.py`
- Modify: `pyproject.toml` dependencies to add `pypdf`
- Modify: `pyproject.toml` package data only if needed by packaging checks
- Test: `tests/unit/test_document_ingest.py`

**Interfaces:**
- Produces `DocumentText(filename: str, media_type: str, text: str, character_count: int)`.
- Produces `extract_document(filename: str, content: bytes) -> DocumentText`.
- Raises `DocumentIngestError` with user-safe messages.

- [ ] **Step 1: Write failing extractor tests**

  Cover plain text/Markdown/SQL/CSV, a generated minimal DOCX ZIP, a generated PDF, unsupported extension, empty document, oversized bytes, and extracted text over 20,000 characters.

- [ ] **Step 2: Run the focused tests to verify the expected failures**

  Run: `uv run pytest tests/unit/test_document_ingest.py -q`

  Expected: collection or assertion failures because `changeproof.document_ingest` does not exist.

- [ ] **Step 3: Implement the smallest extraction boundary**

  Use `pypdf.PdfReader` for PDF pages and `zipfile` plus `xml.etree.ElementTree` for DOCX `word/document.xml`, normalize whitespace, preserve line breaks, enforce a 10 MiB binary limit and the existing 20,000-character text limit, and map extensions to safe media types.

- [ ] **Step 4: Run the focused tests to verify extraction**

  Run: `uv run pytest tests/unit/test_document_ingest.py -q`

  Expected: all extractor tests pass.

- [ ] **Step 5: Update the lockfile and commit**

  Run: `uv lock && git add pyproject.toml uv.lock src/changeproof/document_ingest.py tests/unit/test_document_ingest.py && git commit -m "feat: add document text extraction"`

---

### Task 2: Add structured document interpretation

**Files:**
- Create: `src/changeproof/document_ai.py`
- Test: `tests/unit/test_document_ai.py`

**Interfaces:**
- Produces `DocumentInterpretation(incident_question: str, requirements: list[str], summary: str)`.
- Produces `interpret_document(document: DocumentText, settings: Settings | None = None, client: OpenAI | None = None) -> DocumentInterpretation`.
- Raises `DocumentAiUnavailable` for missing keys, provider failures, malformed output, or unsupported identifiers in grounded fields.

- [ ] **Step 1: Write failing structured-output tests**

  Test missing key, a fake structured response that returns a question and ordered rules, max-rule trimming/rejection, and provider error conversion. Assert the original binary is never part of the OpenAI input payload.

- [ ] **Step 2: Run the focused tests to verify red**

  Run: `uv run pytest tests/unit/test_document_ai.py -q`

  Expected: failures because the module and models do not exist.

- [ ] **Step 3: Implement the OpenAI Responses API adapter**

  Use `Settings.from_env()`, `OpenAI(api_key=...)`, `responses.parse`, a Pydantic output model, `store=False`, and a prompt that allows only normalization of supplied text. Send `document.text`, filename, and media type—not bytes—and enforce the existing limits on returned rules.

- [ ] **Step 4: Run focused AI tests**

  Run: `uv run pytest tests/unit/test_document_ai.py -q`

  Expected: all tests pass without network access.

- [ ] **Step 5: Commit the AI adapter**

  Run: `git add src/changeproof/document_ai.py tests/unit/test_document_ai.py && git commit -m "feat: add structured document interpretation"`

---

### Task 3: Add live DataHub MCP triage enrichment

**Files:**
- Modify: `src/changeproof/config.py`
- Modify: `src/changeproof/mcp_client.py`
- Modify: `src/changeproof/triage.py`
- Create: `src/changeproof/triage_context.py`
- Test: `tests/unit/test_triage_context.py`
- Modify: `tests/unit/test_mcp_client.py`

**Interfaces:**
- Produces `TriageContextResult(result: TriageResult, steps: tuple[DataHubStep, ...], evidence_mode: str)`.
- Produces `enrich_triage_context(result: TriageResult, settings: Settings | None = None) -> TriageContextResult`.
- Reuses `DataHubMcpClient` and its existing `list_schema_fields` and `get_lineage` MCP calls.

- [ ] **Step 1: Write failing MCP enrichment tests**

  Extend the fake session to return live schema fields and lineage for mapped assets. Assert one bounded schema lookup and one lineage lookup per unique mapped asset, returned columns replace fixture columns only when present, and the visible steps say “Live DataHub MCP”. Add a fallback test that preserves the bundled result when live mode is disabled.

- [ ] **Step 2: Run focused tests to verify red**

  Run: `uv run pytest tests/unit/test_mcp_client.py tests/unit/test_triage_context.py -q`

  Expected: failures for the new enrichment API.

- [ ] **Step 3: Implement bounded live enrichment**

  Add an asset-context method to `DataHubMcpClient` that calls `list_schema_fields` and `get_lineage` with a maximum of three hops, optionally reads `search`, `get_entities`, and `get_dataset_queries` when those tools are available, normalizes fields/owners/critical tags, and returns safe metadata. Support DataHub Cloud Streamable HTTP with `DATAHUB_MCP_URL` and `DATAHUB_MCP_TOKEN` while retaining the self-hosted stdio path. Add `triage_context.py` to enrich only mapped rules when `CHANGE_PROOF_TRIAGE_DATAHUB=1`; catch MCP failures and return the original deterministic result with an explicit fallback mode.

- [ ] **Step 4: Run focused MCP tests**

  Run: `uv run pytest tests/unit/test_mcp_client.py tests/unit/test_triage_context.py -q`

  Expected: all MCP tests pass with no external DataHub process.

- [ ] **Step 5: Commit the grounded context boundary**

  Run: `git add src/changeproof/mcp_client.py src/changeproof/triage.py src/changeproof/triage_context.py tests/unit/test_mcp_client.py tests/unit/test_triage_context.py && git commit -m "feat: ground triage in DataHub MCP context"`

---

### Task 4: Wire multipart document uploads and AI action into Triage Composer

**Files:**
- Modify: `pyproject.toml` to add `python-multipart`
- Modify: `src/changeproof/app.py`
- Modify: `src/changeproof/templates/triage.html`
- Modify: `src/changeproof/static/styles.css`
- Test: `tests/integration/test_enterprise_web.py`

**Interfaces:**
- The existing `POST /triage` accepts either URL-encoded pasted text or multipart `document` upload.
- The existing `POST /triage/ai-review` accepts the extracted textarea content and invokes the new document interpreter when a document receipt is present; deterministic evidence remains unchanged if the AI call fails.
- The existing export endpoints remain compatible with pasted and uploaded requirements.

- [ ] **Step 1: Write failing integration tests**

  Add multipart TXT and DOCX upload tests asserting the Triage Composer renders a document receipt, mapped evidence, and `accept=".pdf,.docx,.txt,.md,.sql,.csv"`. Add unsupported-file and empty-file error tests. Add a test that the AI action is shown only when `OPENAI_API_KEY` is configured and the document boundary copy says only extracted text is sent.

- [ ] **Step 2: Run integration tests to verify red**

  Run: `uv run pytest tests/integration/test_enterprise_web.py -q`

  Expected: new upload assertions fail because the route and UI do not handle multipart documents.

- [ ] **Step 3: Implement request parsing and rendering**

  Use `await request.form()`, read and immediately discard `UploadFile` bytes after extraction, keep a non-sensitive receipt in the render context, and route the resulting text through `build_triage_result`. Preserve form re-submission for AI and exports with hidden receipt fields and the existing textarea.

- [ ] **Step 4: Implement the readable upload and receipt UI**

  Add a clearly labeled “Upload SRS / incident document” control, supported-format copy, local-only notice, filename/type/character-count receipt, and a plain error panel. Keep the existing paste flow and use the current orange/blue/white visual system with readable font sizes.

- [ ] **Step 5: Run the integration tests**

  Run: `uv run pytest tests/integration/test_enterprise_web.py -q`

  Expected: all enterprise page, upload, AI boundary, and export tests pass.

- [ ] **Step 6: Commit the end-to-end upload flow**

  Run: `git add pyproject.toml src/changeproof/app.py src/changeproof/templates/triage.html src/changeproof/static/styles.css tests/integration/test_enterprise_web.py && git commit -m "feat: add SRS document triage upload"`

---

### Task 5: Verify, document, and prepare the hosted demo

**Files:**
- Modify: `README.md`
- Modify: `docs/demo-video-script.md`
- Test: existing full suite and Ruff output

- [ ] **Step 1: Add truthful README/demo instructions**

  Document the `/triage` upload flow, supported formats, `DATAHUB_MCP_URL`, `DATAHUB_MCP_TOKEN`, and `CHANGE_PROOF_TRIAGE_DATAHUB` activation variables, bundled fallback label, and the exact AI privacy boundary. Do not claim Railway is live-connected to DataHub unless the deployment has been independently verified.

- [ ] **Step 2: Run the full verification suite**

  Run: `uv run pytest -q && uv run ruff check src tests`

  Expected: all tests pass and Ruff reports no violations.

- [ ] **Step 3: Perform a local browser smoke test**

  Start the app using the repository’s existing development command, open `/triage`, upload the bundled SRS file, verify the receipt, mapping, DataHub context trail, SQL, and export controls, then stop the server.

- [ ] **Step 4: Commit documentation and handoff**

  Run: `git add README.md docs/demo-video-script.md && git commit -m "docs: explain document context demo"`
