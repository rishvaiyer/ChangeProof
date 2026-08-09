# ChangeProof — Positioning against the judging criteria

Judge-facing arguments for the two criteria most likely to sink a DataHub
submission. Written to be pasted into Devpost with light edits.

**Elevator pitch:** Know what breaks before you ship a data contract change.

---

## Originality

> *"Submissions should clearly go beyond features DataHub already provides out of
> the box. Building on top of, extending, or composing shipped features is
> welcome; rebuilding them as if from scratch isn't."*

### The distinction that matters

DataHub's impact analysis answers a question about the world **as it is**:

> *What is downstream of `stg_streams` today?*

ChangeProof answers a question about a world that **does not exist yet**:

> *If I change `artist_id` from `varchar` to `bigint` tomorrow, what breaks, in
> what order, and how do I land it without an incident?*

Lineage is the input, not the output. DataHub tells you what is connected.
ChangeProof tells you what to **do about a change you have not made yet**.

### What is composed vs. what is new

| Layer | Source | Claim |
|---|---|---|
| Schemas, ownership, tags, table lineage, fine-grained column lineage | Read through the official DataHub MCP server | **Composed.** No traversal reimplemented. |
| Hypothetical change simulation | ChangeProof | **New.** DataHub has no notion of a proposed, unapplied change. |
| Evidence scoring across hop distance, ownership, critical tags | ChangeProof | **New.** DataHub exposes the signals; it does not weigh them against a specific edit. |
| Staged remediation plan: parallel typed field, ordered downstream migration, validation gates, rollback steps | ChangeProof | **New.** This is an artifact DataHub does not produce. |
| Writing the decision back as incidents, tags, and documentation | DataHub GraphQL mutations, behind a human approval gate | **Composed.** Standard DataHub write APIs. What is new is the draft-and-approve gate and the content ChangeProof puts in them. |

### The one-sentence version

> ChangeProof does not visualize lineage or rebuild impact analysis. It reads
> DataHub's lineage as evidence and returns a migration plan for a change that
> has not happened yet.

### Deliberately not rebuilt

- No lineage graph UI. DataHub's is better and already shipped.
- No metadata ingestion. The official MCP server is the read path.
- No catalog, search, or discovery surface.

---

## Real-World Usefulness

> *"Would a real data, ML, or AI platform team see clear value in this?"*

### The scenario, concretely

A one-line schema edit becomes a payout incident. In the SonicLedger demo,
`artist_id` flows through the royalty pipeline. Widening a type is the kind of
change that reviews clean, passes CI, and breaks revenue reporting three hops
downstream where nobody was looking.

### Why teams cannot already answer this

The information exists but is spread across lineage, ownership, and tags, and
none of it is organized around a **proposed** change. In practice the answer
comes from asking in Slack and hoping the person who knows still works there.

### What a team actually receives

Not a score or a dashboard. A **plan**:

1. Add a parallel typed field
2. Migrate downstream consumers in dependency order
3. Validation gates between stages
4. Explicit rollback steps

That is the artifact a platform engineer needs in a change review, and it maps
onto how migrations are really run.

### Who feels the pain

- **Data platform teams** owning contracts many teams depend on
- **Analytics engineers** whose models break from upstream edits
- **ML teams** whose features silently change type and skew a model

---

---

## Beyond metadata reading

> *"Depth of DataHub usage: does the submission go beyond basic metadata
> reading?"*

ChangeProof reads through the official MCP server and writes back through
DataHub's GraphQL mutations. The write path is deliberately gated:

1. Every analysis drafts its write-backs: an incident on the source dataset, a
   `changeproof-pending-change` tag on each critical downstream asset, and the
   migration plan as documentation.
2. Nothing is sent until a human approves specific drafts.
3. On approval the proposals are **rebuilt on the server** from the analysis.
   The request carries proposal ids, never content, so an approval cannot push
   arbitrary text into the catalog.
4. The hosted demo runs this in simulated mode so the whole flow is clickable
   without a DataHub behind it. Approving records the entry in a local demo
   catalog and renders it under a `SIMULATED` label; it makes no network call
   and never claims a DataHub write. Simulation must be opted into explicitly,
   so a misconfigured deploy refuses rather than quietly pretending.

The agent proposes. A human disposes. That gate is the point, not a limitation:
an agent that can silently write to a company's metadata catalog is not one a
platform team would install.

## Proof

- Repository: <https://github.com/rishvaiyer/ChangeProof>
- Live demo: <https://changeproof-production.up.railway.app/>
- Demo scenario: `stg_streams.artist_id`, `varchar` → `bigint`
- Verified locally against live DataHub MCP lineage, opt-in path

## Honest limits

State these plainly; they cost nothing and they protect every other claim.

- The hosted demo runs on bundled SonicLedger metadata for reliability.
- The live DataHub integration runs locally and is opt-in.
- Remediation plans are rule-derived. No AI-generated remediation is claimed.
- The hosted demo is not connected to DataHub Cloud.
- The hosted demo's write-back is simulated and labelled as such on screen. It
  records to a local demo catalog, not to DataHub. The real GraphQL write path
  runs under `make live-demo`.
