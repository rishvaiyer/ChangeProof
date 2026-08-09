# Readability and Orange Palette Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ChangeProof enterprise dashboard easier to read and replace the purple visual system with an orange, white, navy, and blue palette.

**Architecture:** Keep the existing page templates and component structure unchanged. Update the shared CSS tokens, typography scale, contrast, and responsive rules in `src/changeproof/static/styles.css`, then verify all routes and the deployed Railway service.

**Tech Stack:** FastAPI/Jinja templates, shared CSS, pytest, Railway CLI.

## Global Constraints

- Keep the existing AsterVale Living content, dashboard routes, and interaction behavior unchanged.
- Use orange and white as the primary visual language; use dark navy for text and blue only for links/data accents.
- Improve readability without introducing new frontend dependencies.
- Preserve mobile layout behavior at approximately 390px wide.
- Deploy only the focused verified change to the existing ChangeProof Railway service.

---

### Task 1: Refresh shared dashboard typography and palette

**Files:**
- Modify: `src/changeproof/static/styles.css`

**Interfaces:**
- Consumes: existing template class names and CSS custom properties.
- Produces: the same selectors with larger body text, restrained headings, stronger contrast, and orange/white/blue styling.

- [ ] **Step 1: Inspect the current CSS tokens and responsive rules**

Run: `sed -n '1,360p' src/changeproof/static/styles.css`

Expected: identify the existing color variables, heading sizes, body text sizes, and mobile media query before editing.

- [ ] **Step 2: Apply the focused CSS update**

Use the existing selector structure. Set the primary background to white/warm white, text to dark navy, orange to `#f97316`/`#ea580c`, and blue accents to `#2563eb`. Set body copy to at least `16px` with a readable line height, reduce oversized headings to approximately `36px` desktop and `28px` mobile, and raise muted text contrast.

- [ ] **Step 3: Run the focused UI test suite**

Run: `pytest -q tests/integration/test_enterprise_web.py tests/integration/test_web.py`

Expected: all selected tests pass.

- [ ] **Step 4: Check the working tree and whitespace**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only the stylesheet and this plan are changed.

### Task 2: Add universal TXT and PDF exports

**Files:**
- Create: `src/changeproof/exports.py`
- Modify: `src/changeproof/app.py`
- Modify: `src/changeproof/templates/base.html`
- Modify: `src/changeproof/templates/fixes.html`
- Modify: `src/changeproof/static/styles.css`
- Modify: `tests/integration/test_enterprise_web.py`
- Modify: `pyproject.toml` and `uv.lock`

**Interfaces:**
- Consumes: the existing allowlisted `ArtifactBundle` fields.
- Produces: `/exports/<artifact>.txt`, `/exports/<artifact>.pdf`, and complete `/exports/all-results.txt` and `.pdf` bundles.

- [ ] **Step 1: Test export availability and allowlisting**

Add integration coverage for all six artifacts, both formats, the complete bundle, and the rendered export center.

- [ ] **Step 2: Generate text and PDF responses**

Use ReportLab for readable PDFs, preserve server-side artifact generation, and keep the OpenAI key out of all rendered content.

- [ ] **Step 3: Add the export center to the shared layout**

Expose one-click TXT/PDF links for the complete bundle and every individual result from any analysis page.

### Task 3: Release and verify the refreshed dashboard

**Files:**
- No additional source files.

**Interfaces:**
- Consumes: the verified local stylesheet change.
- Produces: a successful Railway deployment at `https://changeproof-production.up.railway.app`.

- [ ] **Step 1: Deploy the current ChangeProof directory**

Run: `railway up --detach -m "Improve dashboard readability and refresh palette"`

Expected: Railway returns a deployment ID in a queued/building state.

- [ ] **Step 2: Poll the scoped deployment**

Run: `railway deployment list --project <project-id> --environment <environment-id> --service <service-id> --limit 1 --json`

Expected: the new deployment reaches `SUCCESS`.

- [ ] **Step 3: Verify live routes and content**

Run: `curl -fsS` against `/healthz`, `/`, `/impact`, `/regions`, `/fixes`, `/rollout`, and `/datahub`, plus a POST to `/analyze` with `customer_id`, `varchar`, and `bigint`.

Expected: every route returns HTTP 200, the analysis returns the expected AsterVale content, and the health check reports `ok`.
