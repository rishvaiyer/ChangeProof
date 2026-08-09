# ChangeProof demo script

Target length: 2 minutes 45 seconds. Keep the video under 3 minutes.

## Before recording

- Deploy and verify the AsterVale branch.
- Use a 1280 by 800 browser window at 100 percent zoom.
- Close notifications and personal tabs.
- Open the live demo, GitHub README, and optional local DataHub page.
- Confirm Railway shows `SIMULATED` for hosted write-back.

## 0:00 to 0:20, the problem

**Screen:** Analyze page.

> A schema change can be one line of code and still become a national incident. DataHub knows the observed lineage, owners, and critical assets. But a migration decision also needs hidden code, regional coordination, fixes, validation, and rollback. That is ChangeProof.

## 0:20 to 0:45, the enterprise change

**Screen:** Prepared AsterVale card and metrics.

> AsterVale Living is a fictional retailer with 420 stores. We are changing stg_orders.customer_id from varchar to bigint. Before shipping, ChangeProof scores the observed DataHub evidence and shows four downstream assets, four hidden SQL modules, five region groups, and two critical consumers.

Click **Explore impact**.

## 0:45 to 1:15, DataHub plus hidden SQL

**Screen:** Impact graph, then hidden SQL table.

> DataHub supplies the column lineage, ownership, critical tags, and hop distance. ChangeProof then complements that graph with a read-only SQL Server module query. It finds a convert, a cast, a join, and dynamic SQL. Verified convert and cast expressions receive draft fixes. The join and dynamic SQL stay in manual review.

Click **Regions**.

## 1:15 to 1:40, geographic coordination

**Screen:** Regional map and owner matrix.

> The same technical change does not have the same operational impact everywhere. Northeast and West include critical customer-data exposure. South and Midwest are managed exposure. One dynamic module has no region metadata, so ChangeProof says unknown instead of guessing.

Click **Fix Studio**.

## 1:40 to 2:10, generated artifacts and AI

**Screen:** Artifact cards and side-by-side SQL fixes.

> ChangeProof generates the discovery query, proposed fixes, validation SQL, rollback, a JSON report, and SARIF for CI. Nothing executes automatically. The optional AI review runs only when clicked and can explain this deterministic evidence, but it cannot change scores or invent dependencies.

Click **Rollout**.

## 2:10 to 2:30, release plan

**Screen:** Release readiness and timeline.

> The rollout keeps the original field available, migrates consumers in dependency order, validates each stage, and preserves a reverse-order rollback until owners approve cutover.

Click **DataHub actions**.

## 2:30 to 2:45, close the loop

**Screen:** Approval queue. Select one proposal, then approve.

> Finally, ChangeProof drafts an incident, tags, and documentation back into DataHub. It stops for item-level approval, and the server rebuilds the content from the analysis. This public demo is simulated and says so. The repository also includes the real local MCP read and GraphQL write path.

## Do not claim

- Do not say the hosted demo is connected to DataHub Cloud.
- Do not say simulated approval wrote to a real DataHub.
- Do not say generated SQL was executed.
- Do not say AI discovers dependencies or assigns risk.
- Do not claim complete SQL coverage or legal compliance.

## After recording

- Upload to YouTube or Vimeo as public or unlisted.
- Verify the link in a private browser window.
- Confirm duration is under 3 minutes.
- Add the verified URL to Devpost.
