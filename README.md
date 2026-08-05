# ChangeProof

Scaffold for the ChangeProof DataHub hackathon project.

## SonicLedger demo baseline

- Build the deterministic local dbt baseline with `make demo-baseline`.
- Start local DataHub with `make datahub-up`.
- Seed the DataHub demo metadata with `make datahub-seed`.
- Stop local DataHub with `make datahub-down`.

The verified quickstart stop invocation supported by the installed CLI is `uv run datahub docker quickstart --stop`.
