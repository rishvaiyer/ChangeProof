#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
datahub_quickstart_cmd=(uvx --python 3.11 --from acryl-datahub datahub docker quickstart)

cd "$repo_root"
"${datahub_quickstart_cmd[@]}"
uv run python scripts/check_datahub.py
