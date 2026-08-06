# Hackathon README Design

## Goal

Make the ChangeProof repository understandable and compelling to DataHub hackathon judges within one minute while preserving accurate technical depth for reviewers who continue reading.

## Audience and Message

The primary audience is hackathon judges. The opening must establish the problem, product outcome, and live demo before discussing setup. ChangeProof predicts the observed downstream impact of a proposed schema change and generates a safer staged rollout with rollback guardrails.

## Structure

1. Hero with a concise value proposition, public Railway demo, and current verification status.
2. A three-step judge flow: propose a change, trace DataHub metadata, receive a safe rollout.
3. SonicLedger incident narrative showing `artist_id` flowing into royalties, payouts, and finance reporting.
4. Mermaid architecture diagram covering dbt and DuckDB, DataHub, the official MCP server, ChangeProof analysis, and the FastAPI dashboard.
5. DataHub integration depth: column lineage, ownership, critical tags, hop distance, and metadata completeness.
6. Example output including impact confidence, downstream assets, and `parallel_typed_field` remediation.
7. Honest demo modes: bundled metadata on Railway and live DataHub MCP locally.
8. Exact local setup, test, and live-integration commands.
9. Focused roadmap for stored-procedure analysis, bounded AI review, and hosted DataHub connectivity.

## Presentation Rules

- Lead with outcomes and proof, not installation instructions.
- Link directly to the live demo and repository license.
- Use one compact Mermaid diagram and one lineage flow instead of decorative diagrams.
- Avoid unverified claims, fake badges, invented benchmarks, and claims that Railway is connected to live DataHub.
- Keep setup commands copyable and distinguish Python 3.12 application commands from the Python 3.11 DataHub quickstart boundary.
- Mention that the project has 34 passing tests and one opt-in live DataHub test only while that remains verified.

## Verification

- Check every command against the Makefile and project configuration.
- Check every technical claim against source code or current verified deployment behavior.
- Render the Markdown structurally by inspecting headings, links, code fences, and Mermaid syntax.
- Run the existing test suite because README changes must not accompany accidental source changes.
