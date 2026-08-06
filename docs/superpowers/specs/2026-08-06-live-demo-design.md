# One-Command Live Demo Design

## Goal

Provide a judge-ready local demo that starts from seeded database rows, builds dbt models, publishes their metadata to DataHub, reads the resulting column lineage through the official DataHub MCP server, and displays that live evidence in ChangeProof.

## User Experience

The presenter runs:

```bash
make live-demo
```

The command:

1. Verifies required local tools are available.
2. Seeds SonicLedger rows into DuckDB and builds the dbt project.
3. Starts or reuses DataHub Quickstart.
4. Seeds schemas, owners, critical tags, table lineage, and fine-grained lineage.
5. Runs the opt-in live DataHub MCP integration check.
6. Starts ChangeProof in live-evidence mode.
7. Prints the ChangeProof and DataHub URLs plus the exact demo input.

DataHub and ChangeProof remain running for a live presentation or screen recording. The presenter later runs:

```bash
make demo-stop
```

## Architecture

The existing deterministic classifier, impact scorer, and remediation planner remain authoritative. Evidence becomes a replaceable input:

- Hosted mode uses bundled `MetadataEvidence` for a reliable public Railway demo.
- Live mode uses `DataHubMcpClient.get_downstream_context()` for the prepared `stg_streams.artist_id` scenario.

The FastAPI application selects live mode only when `CHANGE_PROOF_EVIDENCE_MODE=datahub`. A live MCP failure must produce a clear dashboard error and must never silently fall back to bundled evidence. This prevents the demo from claiming live DataHub when the connection failed.

## Components

### Analysis composition

Extract a small composition function that accepts a `ChangeRequest` and `MetadataEvidence`, then runs `assess_impact()` and `plan_remediation()`. The existing bundled demo and new live provider both use this function.

### Web evidence provider

The web application reads `CHANGE_PROOF_EVIDENCE_MODE` at analysis time:

- `bundled` or unset: use the existing deterministic demo.
- `datahub`: fetch live evidence for the fixed source URN and `artist_id`, then compose the decision.
- Any other value: reject startup or analysis with an explicit configuration error.

The hosted Railway deployment remains unchanged because the variable is not set there.

### Demo lifecycle scripts

Add `scripts/live_demo.sh` and `scripts/stop_live_demo.sh` plus `make live-demo` and `make demo-stop` targets.

The start script runs each dependency in order and exits immediately on failure. It starts Uvicorn in the background only after dbt, DataHub seeding, and the live MCP check pass. It records only the dashboard process ID in an ignored repository-local runtime directory. It reuses a healthy existing dashboard process rather than creating duplicates.

The stop script terminates only the recorded ChangeProof dashboard process, removes the stale PID file, and then invokes the existing bounded DataHub stop script. It must not use broad process-kill patterns.

## Failure Handling

- Missing Docker, `uv`, or required CLI access: stop with the missing prerequisite named.
- dbt failure: stop before touching DataHub metadata.
- DataHub startup or seed failure: return nonzero and preserve logs for diagnosis.
- MCP lineage mismatch: stop before starting the dashboard.
- Dashboard port conflict: report port 8000 as occupied and return nonzero.
- Stale PID file: remove it only after proving the process no longer exists.
- Live dashboard MCP failure: render a visible error; do not use bundled evidence.

## Verification

- Unit tests cover composing a decision from injected evidence.
- Web integration tests cover bundled mode, live mode, and visible live-provider failure.
- Script tests use controlled command doubles to verify ordering, failure stops, PID handling, and safe cleanup without starting Docker.
- Existing tests remain green.
- One bounded manual end-to-end run proves seeded dbt data, DataHub seed readback, live MCP lineage, local dashboard health, and live analysis output.

## Scope Boundaries

- The live demo uses realistic synthetic SonicLedger data, not production customer data.
- It covers the prepared `artist_id` type-change scenario.
- It does not add stored-procedure analysis or OpenAI-generated review.
- It does not change the public Railway demo mode.
