# contextIsKey submission prep

This is the plain-English guide for the person presenting the project.

## What am I submitting?

You are submitting a small enterprise change-investigation product called **contextIsKey**.

The fictional company is AsterVale Living, a national home-furnishings retailer with 420 stores. The example change is:

```text
stg_orders.customer_id: varchar -> bigint
```

That looks like one database edit. The product shows why it is not one edit. The identifier appears in customer, commerce, finance, returns, fulfillment, stored-procedure, dashboard, and regional operations data.

## Explain it like I am five

- **DataHub is the labeled map.** It knows what data things exist, how they connect, what they mean, and who owns them.
- **contextIsKey is the detective.** It reads an incident or SRS, asks the map for relevant clues, and builds an investigation.
- **The SQL is a draft.** A human can inspect and download it, but the app never runs it automatically.
- **The fix plan is a safety checklist.** It includes proposed fixes, validation, rollback, rollout order, and review flags.

## What happens in the demo

1. Upload or load an SRS about an accounts-receivable discrepancy.
2. Map each requirement to a dataset, column, owner, domain, and glossary term.
3. Show the numbered context trail: search, schema, entity, lineage, and query-history decisions.
4. Build a chronological SQL investigation across multiple functional areas.
5. Open the impact graph to show DataHub lineage and hidden SQL Server consumers.
6. Open Regional Exposure to show where the change affects operations.
7. Open Fix Studio to review proposed SQL, manual-review flags, validation, rollback, JSON, TXT, PDF, and SARIF exports.
8. Show DataHub Actions. Approval is explicit and hosted write-back is labeled simulated.

## What DataHub does here

DataHub is not being used as a normal application database. contextIsKey uses DataHub-style context to answer questions that rows alone cannot answer:

- What asset is this column part of?
- Who owns it?
- What business domain and glossary terms describe it?
- What depends on it downstream?
- What queries have used it?
- Which assets are critical?

The included MCP adapter can read live DataHub schema and lineage when a tenant is available. The hosted Railway demo uses deterministic synthetic DataHub-shaped context so the public demo stays reliable and does not pretend to have a Cloud connection.

## What is real and what is simulated?

### Real in the hosted product

- The document extraction flow
- Requirement mapping logic
- Chronological SQL composition
- Impact scoring and hidden SQL classification
- Regional aggregation
- Fix, validation, rollback, JSON, TXT, PDF, and SARIF generation
- Human-review gates
- Optional OpenAI advisory review after an explicit click

### Deliberately simulated or bundled

- Hosted DataHub metadata
- Hosted write-back to DataHub
- Database execution
- Enterprise customer and regional data

### Do not claim

- Do not say the Railway demo is connected to DataHub Cloud.
- Do not say generated SQL was executed.
- Do not say AI discovered or verified dependencies.
- Do not say the submission is complete until Devpost confirms it.

## Candid confidence report

### Overall

**Strong project, not an automatic winner.** Once the demo is recorded cleanly and the submission is completed, this is a credible challenge-level entry with a realistic chance of being shortlisted. The strongest advantage is the end-to-end workflow. The biggest weakness is that the public deployment uses synthetic DataHub-shaped context instead of a live Cloud tenant.

### Strengths

- The problem is concrete and expensive: an identifier migration can break many teams at once.
- DataHub has a real role in the product: context constrains the investigation.
- The app does more than chat: it creates inspectable SQL and operational artifacts.
- The hidden SQL scan makes the product meaningfully different from lineage-only tools.
- The safety boundaries are unusually clear for an AI demo.
- The regional view makes a technical change understandable to business operators.

### Risks

- A weak or overly long video will hide the product’s strengths.
- A judge may discount the integration if the synthetic-versus-live boundary is not explained in one sentence.
- The amount of functionality can feel scattered unless the presenter follows one incident from start to finish.
- Cloud onboarding is blocked by the company-email requirement and should not consume the remaining deadline time.

### My honest rating after a good video

| Area | Assessment |
| --- | --- |
| Problem and usefulness | Strong |
| DataHub alignment | Strong, with a live-connection caveat |
| Technical execution | Strong |
| Product polish | Strong |
| Demo readiness | Depends almost entirely on recording and rehearsal |
| Winner certainty | Impossible to promise; presentation quality is now the deciding variable |

## Demo plan: who does what

### Codex prepares

- Keep the public Railway deployment healthy.
- Keep the README and submission documents consistent.
- Verify the five-minute smoke path before recording.
- Fix regressions if the live app changes.

### Rishva does

- Log in to Devpost.
- Confirm registration and category.
- Record the voice/video walkthrough.
- Paste the prepared submission copy.
- Add the video URL and screenshots.
- Submit and confirm the Devpost email.

No company email or DataHub Cloud account is required to submit the current honest demo.

## Recording plan

Use a 1280x800 browser window at 100% zoom. Pre-open these routes:

1. `/triage`
2. `/impact`
3. `/regions`
4. `/fixes`
5. `/datahub`

### Three-minute script

**0:00–0:20 — Problem**

“A one-line customer ID type change can break finance, returns, dashboards, and stored procedures. contextIsKey investigates the change before it reaches production.”

**0:20–1:00 — Context**

Upload the SRS. Show the rule mappings and numbered context trail. Say: “DataHub provides the governed context: assets, schema, owners, glossary, lineage, and query usage. contextIsKey composes the incident investigation from those clues.”

**1:00–1:35 — Impact**

Open Impact graph. Show the critical downstream assets and hidden SQL consumers.

**1:35–1:55 — Regions**

Show the regional exposure map and explain that technical impact becomes owner coordination.

**1:55–2:30 — Fix Studio**

Show generated fixes, manual review, validation, rollback, and downloads. Say: “SQL is reviewable, never auto-executed.”

**2:30–2:50 — Safety and DataHub**

Show DataHub Actions. Say: “The hosted demo uses synthetic DataHub-shaped context for reliability. The MCP adapter supports live DataHub reads when a tenant is available. Writes stay behind human approval.”

**2:50–3:00 — Close**

“DataHub gives the system the map. contextIsKey turns that map into an evidence-backed change decision.”

## Final checklist

- [ ] Public Railway URL opens successfully.
- [ ] Homepage says contextIsKey.
- [ ] `/triage` loads the example and shows the context trail.
- [ ] Impact, Regions, Fix Studio, and DataHub Actions load.
- [ ] Screenshot files are attached.
- [ ] Video is public or unlisted and the link works in an incognito window.
- [ ] Repository URL is `https://github.com/rishvaiyer/context-is-key`.
- [ ] Apache-2.0 license is visible.
- [ ] Devpost confirmation email is received.

## If a live DataHub demo is attempted

Treat it as an optional bonus, not part of the critical path. Use `make live-demo` only if the local DataHub setup is already working. Give it a bounded ten-minute attempt. If it fails, record the hosted demo and explain the fallback honestly.
