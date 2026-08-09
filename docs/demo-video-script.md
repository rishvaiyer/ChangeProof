# ChangeProof — 3-minute demo video script

Everything in **Say** is meant to be read out loud, first person, like you're
showing it to a coworker. Short sentences on purpose. Don't smooth it out.

**Record with:** QuickTime, File > New Screen Recording, or `Cmd+Shift+5`.
Record the browser window only, not the whole desktop.

**Before you hit record**
- Close other tabs, notifications, and anything personal on screen.
- Browser zoom 100%, window around 1280x800.
- Two tabs ready: the live demo, and the GitHub repo.
- Want the strong version of Shot 4? Run `make live-demo` first and let it
  finish, so DataHub is already up at localhost:9002. Otherwise skip to the
  fallback line and record entirely against the hosted demo.

---

## Shot 1 — why I built it (0:00 to 0:25)

**Screen:** the live demo landing page.

> So this started with a thing that keeps happening. Somebody widens a column
> type. It's one line. It reviews fine, it passes CI, and then three hops
> downstream revenue reporting breaks and nobody knows why.
>
> And the annoying part is DataHub already knows everything you'd need to catch
> it. It's just spread across lineage and ownership and tags, and none of it is
> pointed at a change you haven't made yet.

---

## Shot 2 — the change (0:25 to 0:50)

**Screen:** type it in slowly enough to read.

```
Column:        artist_id
Current type:  varchar
Proposed type: bigint
```

> This is ChangeProof. I give it a change I'm thinking about making, not one I
> already shipped. artist_id, varchar to bigint. In the demo warehouse that
> field runs straight through the royalty pipeline.

Click **Analyze**.

---

## Shot 3 — what it gives back (0:50 to 1:40)

**Screen:** pause on the four metrics, then scroll slowly down to the plan.

> Okay so it went and read the column level lineage, the ownership, and the
> critical tags through DataHub's MCP server. Three things downstream, three
> hops deep, two of them tagged critical. Artist payouts and the finance
> dashboard. Those are the ones you'd actually get paged about.
>
> But the part I care about isn't the number. It's this. It's a plan.
>
> Add a parallel typed field. Migrate the downstream stuff in dependency order.
> Validation gates between each step. And the old field stays live as the
> rollback until the owners say they're done.
>
> That's the thing I'd actually want in front of me in a change review.

---

## Shot 4 — it's real lineage (1:40 to 2:00) — optional

**Screen:** switch to DataHub at localhost:9002, show the `artist_id`
column-level lineage, switch back.

> And this isn't mocked. There's a dbt pipeline on DuckDB that builds the
> warehouse, pushes the schemas and ownership and column level lineage into
> DataHub, and ChangeProof reads that graph back out. One command runs the whole
> thing.

**Skipping this shot?** Say this over the README instead:

> The hosted demo runs on bundled metadata so it just works and doesn't need
> credentials. The real DataHub path runs locally with one command, and there's
> an integration test that checks it.

---

## Shot 4b — writing it back (2:00 to 2:35)

**Screen:** scroll to `04 · WRITE BACK`. Tick the incident and one tag. Click
**Approve and write back**. If DataHub is running, switch over and show the new
incident on `stg_streams`.

> It doesn't just stop at having an opinion though. It drafts the write backs.
> An incident on the source dataset with the blast radius in it, a pending
> change tag on each critical asset, and the plan as documentation.
>
> And then it stops. That's on purpose. I approve two of them, and only those
> two get sent.
>
> One thing I did deliberately here. When you approve, it rebuilds the content
> on the server from the analysis. The request only carries which ones you
> picked, never the text. So there's no way to use approve as a way to shove
> arbitrary stuff into somebody's catalog.
>
> I wouldn't install an agent that can quietly write to our metadata. So I
> didn't build one.

**Recording against the hosted demo only?** Tick the boxes, click approve, show
the refusal:

> There's no DataHub behind the public demo, so it just tells you that instead
> of pretending it wrote something.

---

## Shot 5 — what I didn't build (2:35 to 2:50)

**Screen:** the GitHub repo, briefly on `docs/judging-positioning.md`.

> I want to be clear about what I didn't do. I didn't rebuild anything DataHub
> already has. No lineage graph, no ingestion, no catalog. The traversal is
> theirs.
>
> What's mine is simulating a change that hasn't happened, weighing it against
> that specific edit, and turning it into a migration plan. DataHub tells you
> what's connected. This tells you what to do about something you're about to
> change.

---

## Shot 6 — the honest part (2:50 to 3:00)

**Screen:** the README's boundaries section.

> Last thing. Lineage is evidence, it's not proof. Dynamic SQL, someone querying
> it from a notebook, that stuff is invisible to it. So when the metadata is
> thin it lowers its own confidence and says so.
>
> I'd rather it tell you it isn't sure than sound sure and be wrong.

---

## Don't say these

Not true today, even in passing.

- That the hosted demo is connected to live DataHub or DataHub Cloud.
- That you can finish a write-back from the public demo URL. You can't. There's
  no DataHub behind it, and it refuses instead of faking it.
- That the remediation plans are AI generated. They're rule based.

## After recording

- Upload to YouTube or Vimeo, public or unlisted.
- Open the link in a private window before pasting it into Devpost.
