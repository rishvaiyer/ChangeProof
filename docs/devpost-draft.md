# contextIsKey Devpost draft

Use only after the AsterVale branch is deployed and the public URL is reverified.

## Project

- **Name:** contextIsKey
- **Pitch:** Turn governed enterprise context into investigations you can inspect, download, and trust.
- **Category:** Agents That Do Real Work
- **License:** Apache-2.0
- **Built with:** DataHub, DataHub MCP, DataHub GraphQL, Python, FastAPI, Jinja2, dbt, DuckDB, OpenAI, Railway

## Inspiration

A one-line type change can become a national incident. The evidence needed to prevent it is often scattered across lineage, ownership, stored procedures, regional operations, and tribal knowledge.

DataHub supplies the context graph. contextIsKey asks: what evidence does this incident require, how do the domains connect, what query should a human review, and what changes safely land next?

## What it does

The demo models AsterVale Living, a fictional national retailer with 420 stores.

The prepared change is `stg_orders.customer_id` from `varchar` to `bigint`.

contextIsKey, built on ChangeProof:

1. Maps an uploaded or pasted SRS to DataHub datasets, columns, owners, domains, and glossary terms.
2. Composes a reviewable chronological SQL investigation across seven functional domains.
3. Shows every bounded hosted context lookup and the exact query choice it supported.
4. Reads observed downstream lineage, ownership, critical tags, and field identity from DataHub evidence.
5. Generates and classifies a read-only SQL Server discovery query for hidden procedures and views.
6. Maps affected assets and SQL consumers to operating regions and owners.
7. Produces proposed SQL, validation, rollback, JSON, SARIF, TXT, and PDF exports.
8. Offers a grounded OpenAI review only after an explicit click.
9. Drafts incidents, tags, and documentation for DataHub, then waits for item-level approval.

## Why DataHub matters

contextIsKey uses DataHub as a governed context graph:

- Discovery across datasets, columns, domains, owners, and glossary terms
- Official MCP schema and lineage reads
- Fine-grained column lineage
- Ownership and critical tags
- Evidence completeness and freshness
- Domain and structured-property patterns for business and geography metadata
- GraphQL write-back for incidents, tags, and documentation

The context graph is the foundation. The product is the evidence-backed incident or migration decision and its reviewable artifacts.

## Technical execution

- Deterministic impact, SQL, region, and artifact engines
- Server-rendered seven-page responsive dashboard
- SRS mapper and mapping-derived cross-domain SQL composer
- Six allowlisted downloadable artifacts
- Explicit OpenAI Responses API call with structured Pydantic output
- No AI call on page load
- No automatic SQL execution
- Approval requests contain IDs only, never arbitrary catalog text
- Hosted simulation and real DataHub write modes are visibly distinct
- Real GraphQL mutation mode is disabled by default and enabled only by the trusted local live-demo launcher
- Credential-free ordinary tests plus opt-in live DataHub verification

## Originality

DataHub answers what exists, how it connects, what it means, and who owns it. contextIsKey turns that context into answers:

- Which requirements map to trusted assets and columns?
- Which hosted context lookup changed each part of the query?
- What chronological cross-domain investigation should a human review?
- What observed assets are exposed?
- What hidden code also references the field?
- Which regions and owners must coordinate?
- What exact fixes, checks, rollout, and rollback should be reviewed?

It composes DataHub rather than rebuilding the catalog.

## Real-world usefulness

A platform engineer receives more than a risk score:

- An evidence-backed dependency graph
- A hidden-code inventory
- A regional coordination matrix
- Proposed SQL changes
- Validation and rollback scripts
- A dependency-ordered rollout
- DataHub drafts that preserve the decision for every downstream team

## Challenges

The hardest part was keeping confidence honest. Lineage cannot see every dynamic query or external reader. Static SQL scanning cannot resolve every runtime string. Region metadata can be absent.

contextIsKey exposes those limits. Unsupported SRS rules stay unmapped. Dynamic SQL gets manual review. Missing geography becomes `UNKNOWN`. Hosted simulation never claims a live DataHub read or write.

## What is next

- Seed the full AsterVale regional metadata model into a hosted DataHub environment
- Connect SQL discovery to approved read-only enterprise database credentials
- Add CI annotations from the SARIF output
- Add more database dialects and migration templates

## Required final links

- **Demo:** https://changeproof-production.up.railway.app/
- **Repository:** https://github.com/rishvaiyer/context-is-key
- **Video:** add the verified public YouTube or Vimeo URL

## Claim boundaries

- Hosted metadata is synthetic and deterministic.
- Hosted write-back is simulated and labeled.
- The local opt-in path is the real DataHub MCP and GraphQL integration.
- Generated SQL is a review draft and is never auto-executed.
- The AI reviewer is advisory. It explains deterministic evidence but does not discover dependencies, assign risk, execute fixes, or control write-back.
- Geographic flags are coordination prompts, not legal advice.
