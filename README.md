# ChangeProof

Scaffold for the ChangeProof DataHub hackathon project.

## SonicLedger demo baseline

- Build the deterministic local dbt baseline with `make demo-baseline`.
- Start local DataHub with `make datahub-up`.
- Seed the DataHub demo metadata with `make datahub-seed`.
- Stop local DataHub with `make datahub-down`.

The application/runtime stays on Python 3.12. The DataHub quickstart compatibility boundary runs through Python 3.11 only via `uvx --python 3.11 --from acryl-datahub datahub docker quickstart`.

The verified quickstart stop invocation supported by the installed CLI is `uvx --python 3.11 --from acryl-datahub datahub docker quickstart --stop`.
