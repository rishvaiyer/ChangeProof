# ChangeProof

Predict downstream impact from DataHub metadata and propose a safer schema-change rollout.

## Dashboard

Start the deterministic SonicLedger demo locally:

```bash
uv sync --extra dev
uv run uvicorn changeproof.app:app --reload
```

- `GET /` renders the impact dashboard.
- `POST /analyze` evaluates a proposed schema type change.
- `GET /healthz` reports application health.

The hosted demo uses bundled SonicLedger metadata so it remains reliable without credentials.
The live DataHub MCP adapter is exercised separately through the opt-in local integration test.

## SonicLedger demo baseline

- Build the deterministic local dbt baseline with `make demo-baseline`.
- Start local DataHub with `make datahub-up`.
- Seed the DataHub demo metadata with `make datahub-seed`.
- Stop local DataHub with `make datahub-down`.

The application/runtime stays on Python 3.12. The DataHub quickstart compatibility boundary runs through Python 3.11 only via `uvx --python 3.11 --from acryl-datahub datahub docker quickstart`.

The verified quickstart stop invocation supported by the installed CLI is `uvx --python 3.11 --from acryl-datahub datahub docker quickstart --stop`.
