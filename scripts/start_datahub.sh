#!/usr/bin/env zsh
set -euo pipefail

script_dir=${0:A:h}
repo_root=${script_dir:h}

cd "$repo_root"
uv run datahub docker quickstart
uv run python scripts/check_datahub.py
