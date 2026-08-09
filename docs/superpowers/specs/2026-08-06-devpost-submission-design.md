# ChangeProof Devpost Submission Design

## Goal

Create a judge-first Devpost draft for ChangeProof using only claims verified by the repository and deployed demo.

## Positioning

- Project name: ChangeProof
- Elevator pitch: Know what breaks before you ship a data contract change.
- Category: Agents That Do Real Work
- Core story: DataHub metadata becomes an operational decision graph that traces downstream impact and produces a staged remediation and rollback plan.

## Evidence and links

- Repository: https://github.com/rishvaiyer/context-is-key
- Demo: https://changeproof-production.up.railway.app/
- Demo scenario: change `stg_streams.artist_id` from `varchar` to `bigint`
- Verified local path: DataHub schemas, ownership, tags, table lineage, and fine-grained lineage read through the official DataHub MCP server

## Claim boundaries

- State that the hosted Railway demo uses bundled SonicLedger metadata.
- State that the live DataHub integration runs locally and is opt-in.
- Do not claim AI-generated remediation is enabled.
- Do not claim the hosted demo is connected to DataHub Cloud.
- Do not claim submission completion until Devpost confirms it.

## Form workflow

1. Complete and save project overview.
2. Complete and save project details with concise judge-facing sections.
3. Complete additional hackathon fields using verified links and category choices.
4. Leave video fields unfilled unless a valid public video URL exists.
5. Stop at final submission for explicit user approval.
