# ChangeProof — 3-minute demo video script

A shot list for the Devpost submission video. Timings are targets, not rules.
Narration is written to be read aloud at a normal pace.

**Record with:** QuickTime Player, File > New Screen Recording, or `Cmd+Shift+5`.
Record the browser window only, not the full desktop.

**Before you hit record**
- Close unrelated tabs, notifications, and anything personal on screen.
- Browser zoom at 100%, window roughly 1280x800.
- Have two tabs ready: the live demo, and the GitHub repo.
- If you want to show the live DataHub path, run `make live-demo` first and let
  it finish, so DataHub is already up at localhost:9002. If you would rather keep
  it simple, skip Shot 4 and use the hosted demo throughout.

---

## Shot 1 — The problem (0:00 to 0:25)

**Screen:** the live demo landing page,
https://changeproof-production.up.railway.app/

**Say:**
> A one-line schema edit becomes a payout incident. Someone widens a column
> type. It reviews clean, it passes CI, and three hops downstream it breaks
> revenue reporting, where nobody was looking. The information to catch that
> already exists in DataHub, but it is spread across lineage, ownership, and
> tags, and none of it is organized around a change you have not made yet.

---

## Shot 2 — The change (0:25 to 0:50)

**Screen:** type into the form, slowly enough to read.

```
Column:        artist_id
Current type:  varchar
Proposed type: bigint
```

**Say:**
> This is ChangeProof. I give it a proposed change, not a change I already
> shipped. Column artist_id, from varchar to bigint. In the demo warehouse this
> field runs straight through the royalty pipeline.

Click **Analyze**.

---

## Shot 3 — The answer (0:50 to 1:40)

**Screen:** the results. Pause on the signal table, then scroll slowly to the plan.

**Say:**
> ChangeProof read column-level lineage, ownership, and critical-asset tags
> through the official DataHub MCP server. Three downstream assets, three hops
> deep, two of them tagged critical: artist payouts and the finance royalty
> dashboard. Confidence is high because the metadata backing that answer is
> complete.
>
> But the output is not a score. It is a plan. Add a parallel typed field.
> Migrate downstream consumers in dependency order. Validation gates between
> each stage. And the original contract stays live as the rollback path until
> owners confirm the cutover. That is the artifact you actually need in a change
> review.

---

## Shot 4 — It is real lineage (1:40 to 2:20) — optional

**Screen:** switch to DataHub at http://localhost:9002, show the `artist_id`
column-level lineage, then switch back.

**Say:**
> This is not a mock. A dbt pipeline over DuckDB builds the warehouse, emits
> schemas, ownership, tags and fine-grained column lineage into DataHub, and
> ChangeProof reads that graph back through the MCP server. One command,
> make live-demo, runs that whole path.

**If you skip this shot,** say instead, over the repo README:
> The hosted demo runs on bundled metadata so it is reliable and needs no
> credentials. The live DataHub path runs locally with one command, make
> live-demo, and it is verified by an opt-in integration test.

---

## Shot 4b — Write it back (2:00 to 2:35)

**Screen:** scroll to `04 · WRITE BACK`. Tick the incident draft and one tag
draft. Click **Approve and write back**. If DataHub is running from
`make live-demo`, switch to it and show the new incident on `stg_streams`.

**Say:**
> ChangeProof does not stop at an opinion. It drafts the write-backs: an
> incident on the source dataset carrying the blast radius, a pending-change tag
> on each critical asset, and the plan as documentation. And then it stops. I
> approve two of them, and only those two are sent. On approval the content is
> rebuilt from the analysis on the server, so approving can never push arbitrary
> text into the catalog. The agent proposes, a human disposes.

**If you are recording against the hosted demo only,** tick the boxes, click
approve, and show the refusal message instead:
> There is no DataHub behind the public demo, so it refuses rather than
> pretending it wrote something.

---

## Shot 5 — What is composed, what is new (2:20 to 2:50)

**Screen:** the GitHub repo, briefly showing `docs/judging-positioning.md`.

**Say:**
> I did not rebuild anything DataHub ships. No lineage graph UI, no ingestion,
> no catalog. The traversal is DataHub's. What is new is simulating a change
> that has not happened yet, weighing the evidence against that specific edit,
> and producing a migration plan. DataHub tells you what is connected.
> ChangeProof tells you what to do about a change you are proposing.

---

## Shot 6 — Honest limits and close (2:50 to 3:00)

**Screen:** the README's boundaries section.

**Say:**
> Lineage is evidence, not proof. Dynamic SQL and unobserved consumers still
> need a human. ChangeProof lowers its own confidence when the metadata is
> incomplete, and it says so out loud. That is the point: support the decision,
> do not manufacture confidence the metadata cannot justify.

---

## Do not say

These are not true today. Avoid them even in passing.

- That the hosted demo is connected to live DataHub or DataHub Cloud.
- That a write-back can be completed from the public demo URL. It cannot;
  there is no DataHub behind it, and approval is refused rather than faked.
- That remediation plans are AI-generated. They are rule-derived.

## After recording

- Upload to YouTube or Vimeo as public or unlisted, and confirm the link opens
  in a private window before pasting it into Devpost.
