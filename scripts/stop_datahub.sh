#!/usr/bin/env zsh
set -euo pipefail

script_dir=${0:A:h}
repo_root=${script_dir:h}

cd "$repo_root"
help_output=$(uv run datahub docker quickstart --help)
supported_stop_command="uv run datahub docker quickstart --stop"

if [[ "$help_output" != *"--stop"* ]]; then
  echo "Unsupported DataHub quickstart stop command. Expected: $supported_stop_command" >&2
  exit 1
fi

echo "Using supported stop command: $supported_stop_command"
uv run datahub docker quickstart --stop
