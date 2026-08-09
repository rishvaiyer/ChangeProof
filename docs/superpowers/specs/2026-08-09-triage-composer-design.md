# DataHub Triage Composer Design

## Goal

Add a judge-ready Triage Composer to ChangeProof that turns an enterprise incident question and pasted or uploaded SRS text into an evidence-backed, cross-domain chronological SQL investigation package.

## User story

An analyst investigating an accounts-receivable discrepancy should not need to manually search many SRS documents, guess which teams own each table, or rebuild a timeline query from scratch. They upload a plain-text requirements document or load the included AsterVale example. ChangeProof extracts bounded rules, maps them to DataHub metadata, and generates a reviewable SQL investigation with validation queries and explicit uncertainty.

## Demo scenario

AsterVale Living operates a national retail business. Its AR balance can be affected by commerce orders, invoices, payment settlement, returns and refunds, fulfillment, customer identity, and regional policy. The included example SRS describes the ordering and reconciliation rules for those systems.

## Product flow

1. The Triage Composer opens with the synthetic AsterVale AR example already rendered.
2. The user may paste requirements or select a `.txt`, `.md`, `.sql`, or `.csv` file. Browser JavaScript reads text locally into the form; the server never stores the uploaded file.
3. ChangeProof extracts at most 20 non-empty rules from at most 20,000 characters.
4. Deterministic keyword mapping links each rule to a bounded enterprise metadata catalog.
5. The result shows the rule, domain, DataHub asset URN, selected columns, owner, glossary context, and mapping reason.
6. ChangeProof generates a multi-CTE chronological SQL investigation plus separate validation SQL.
7. A numbered “How DataHub helped” trail identifies repeated metadata operations and the exact query decision each operation supported.
8. The user downloads SQL directly or exports the complete package as TXT or PDF.
9. When `OPENAI_API_KEY` is configured, the user may explicitly request a second-pass AI review that explains the query simply, challenges missing requirements, and lists unresolved query risks.

## DataHub boundary

- DataHub supplies metadata context: search/discovery, schema fields, lineage, ownership, domains, glossary terms, tags, and quality/freshness signals.
- ChangeProof performs the requirements mapping and SQL composition.
- ChangeProof does not execute the generated SQL and does not claim semantic correctness without human review and database validation.
- OpenAI receives only the extracted rule and bounded mapping package after an explicit click. It cannot add assets, change deterministic mappings, or execute SQL.
- Railway uses clearly labelled bundled synthetic DataHub-shaped metadata.
- The existing opt-in local DataHub mode remains the path for real MCP schema and lineage calls. Metadata categories not exposed by the pinned MCP server can use DataHub APIs in a later production integration.

## Query shape

The sample query uses SQL Server syntax and includes independently readable CTEs for customer scope, order events, invoice events, payment events, return/refund events, fulfillment events, a normalized event stream, a running balance, and reconciliation exceptions. Every source CTE contains a comment naming the DataHub evidence operation that justified it.

## Safety and truthfulness

- Accept only browser-readable text formats for the MVP.
- Do not upload or persist the original file; submit only the displayed text.
- Escape all template output through Jinja defaults.
- Bound request length and extracted rule count.
- Show unmapped rules and warnings instead of inventing assets.
- Label all SQL as generated and review-required.
- Label hosted evidence as synthetic demo metadata.
- Validate backtick-delimited identifiers in AI output against the deterministic mapping package and reject unsupported identifiers.

## UX

- Add “Triage composer” directly before Fix Studio in primary navigation.
- Use the existing bright orange, blue, and white visual system.
- Keep body text at readable sizes and avoid oversized headings.
- Explain each section in plain language with a short “Like I’m five” sentence.
- Make the judge story visible without requiring a form submission.

## Success criteria

- The included SRS maps at least six functional domains.
- The sample output contains at least eight CTEs and at least six joins or unions.
- The UI shows at least six distinct DataHub metadata operations.
- Every mapping identifies an asset and one or more columns.
- Unmatched requirements are visibly flagged.
- SQL and complete evidence exports work as SQL, TXT, and PDF.
- Existing tests and navigation remain green.
