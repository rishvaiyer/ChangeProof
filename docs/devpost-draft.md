# ChangeProof — Devpost submission draft

Paste-ready copy for datahub.devpost.com. Every claim below is verified against
the repository and the deployed demo as of 2026-08-08. Nothing here asserts a
capability the code does not have.

---

## Project name

ChangeProof

## Elevator pitch

Know what breaks before you ship a data contract change.

## Category

Agents That Do Real Work

## Built with

Python, FastAPI, Uvicorn, DataHub, DataHub MCP Server, dbt, DuckDB, Jinja2,
pytest, Docker, Nixpacks, Railway

## Try it out

- Live demo: https://changeproof-production.up.railway.app/
- Repository: https://github.com/rishvaiyer/ChangeProof
- Demo scenario: column `artist_id`, current type `varchar`, proposed type `bigint`

---

# About the project

## Inspiration

A one-line schema edit becomes a payout incident.

Widening a column type is the kind of change that reviews clean, passes CI, and
then breaks revenue reporting three hops downstream where nobody was looking.
The information needed to catch it already exists, but it is scattered across
lineage, ownership, and tags, and none of it is organized around a change that
has not happened yet. In practice the answer comes from asking in Slack and
hoping the person who knows still works there.

DataHub already knows what is connected. What it does not do is tell you what to
do about an edit you are proposing tomorrow.

## What it does

ChangeProof takes a proposed schema change and returns a staged migration plan.

Give it a column and a type change. It reads column-level lineage, ownership,
critical-asset tags, and hop distance through the official DataHub MCP server,
scores the observed blast radius, and produces an ordered rollout with
validation gates and explicit rollback steps.

In the bundled SonicLedger demo, `artist_id` runs straight through the royalty
pipeline:

```
stg_streams.artist_id
  -> fct_royalties
  -> artist_payouts [critical]
  -> finance_royalty_dashboard [critical]
```

Changing that field in place can break royalty calculations, artist payouts,
and finance reporting. Analyzing `artist_id` from `varchar` to `bigint` returns:

| Signal | Result |
| --- | --- |
| Confidence | HIGH |
| Blast radius | 3 downstream assets |
| Maximum depth | 3 hops |
| Critical assets | 2 |
| Strategy | `parallel_typed_field` |

The recommended plan keeps the original field live while a parallel `bigint`
field is backfilled and validated, migrates downstream assets in lineage order,
and holds the original contract as the rollback path until owners confirm the
cutover.

What a team receives is not a score or another dashboard. It is the artifact a
platform engineer actually needs in a change review.

Then ChangeProof offers to put that decision back into DataHub: an incident on
the source dataset carrying the blast radius, a `changeproof-pending-change` tag
on each critical downstream asset, and the migration plan as documentation. It
drafts them and stops. Nothing is written until a human approves a specific
draft, and on approval the content is rebuilt on the server from the analysis,
so an approval can never carry arbitrary text into the catalog. The agent
proposes; a human disposes.

## How we built it

Three responsibilities are kept deliberately separate:

1. **Evidence collection** reads schema fields and bounded downstream lineage
   through the official DataHub MCP server. No traversal is reimplemented.
2. **Impact assessment** scores freshness and completeness of the observed
   metadata, identifies critical assets, and gathers the owners who must review.
3. **Remediation planning** turns the change shape and observed impact into
   ordered rollout, validation, and rollback actions.

The demo pipeline is real rather than mocked: dbt models over DuckDB generate a
SonicLedger warehouse, which is emitted to DataHub with schemas, ownership,
tags, table lineage, and fine-grained `artist_id` column propagation.
ChangeProof then asks DataHub which observed consumers are exposed. `make
live-demo` runs that entire path as one command and leaves the live-evidence
dashboard running next to the DataHub UI.

The web app is FastAPI with server-rendered Jinja templates, deployed to
Railway via Nixpacks behind a `/healthz` check.

## Challenges we ran into

The hardest problem was epistemic, not technical: deciding what the tool is
allowed to claim.

Lineage is evidence of observed dependencies, not proof of every consumer.
Dynamic SQL, ad-hoc queries, and external readers are invisible to it. It would
have been easy to render a confident number and let a judge assume completeness.
Instead ChangeProof scores the quality of its own evidence and lowers confidence
when the metadata is incomplete, and the boundaries are printed in the README
rather than buried.

The same discipline shaped the demo. The hosted deployment runs on bundled
metadata so it is deterministic and credential-free, and the live DataHub
integration is opt-in and local. Presenting the hosted demo as a live DataHub
connection would have been the easier story and the false one.

## Accomplishments that we're proud of

- The output is a plan, not a score. Parallel typed field, dependency-ordered
  migration, validation gates, explicit rollback.
- Write-back with a real approval gate. Proposals are rebuilt server-side on
  approval, so the endpoint cannot be used to write arbitrary text into DataHub.
- Column-level lineage end to end, from dbt models through DataHub to the
  decision, including fine-grained `artist_id` propagation.
- 64 passing tests covering the classifier, planner, impact scorer, MCP
  adapter, write-back proposals and approval gate, dbt demo, and the web app,
  plus an opt-in live DataHub integration test.
- One-command reproducibility. `make live-demo` builds the warehouse, starts
  and seeds DataHub, verifies lineage through the MCP server, and serves the
  dashboard.
- Claim boundaries stated in the README instead of hidden.

## What we learned

Composing shipped features beats rebuilding them. The early temptation was a
lineage graph UI, which DataHub already does better. Cutting it made the actual
contribution obvious: DataHub answers what is connected today, ChangeProof
answers what to do about a change that has not happened yet. Lineage became the
input rather than the output.

We also learned that stating limits makes the rest of the submission more
credible, not less.

## What's next for ChangeProof

- Hosted DataHub or DataHub Cloud connectivity for the public demo
- Stored-procedure parameter, result-set, and dependency-change analysis
- Bounded AI review that explains the deterministic evidence without inventing
  dependencies

---

# Claim boundaries (keep these visible in the submission)

- The hosted Railway demo uses bundled SonicLedger metadata for reliability.
- The live DataHub integration runs locally and is opt-in.
- Remediation plans are rule-derived. No AI-generated remediation is claimed.
- The hosted demo is not connected to DataHub Cloud.
- Write-back requires a reachable DataHub. On the hosted demo the drafts render
  and approval is refused rather than simulated, so do not promise a judge they
  can complete a write-back from the public URL. Show it via `make live-demo`.

# Notes before submitting

- Leave video fields empty until a real public URL exists.
- Do not mark the submission complete until Devpost confirms it.
- Devpost registration must be completed first.
