#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
datahub_quickstart_cmd=(uvx --python 3.11 --from acryl-datahub datahub docker quickstart)

cd "$repo_root"
help_output="$("${datahub_quickstart_cmd[@]}" --help)"
supported_stop_command="uvx --python 3.11 --from acryl-datahub datahub docker quickstart --stop"

if [[ "$help_output" != *"--stop"* ]]; then
  echo "Unsupported DataHub quickstart stop command. Expected: $supported_stop_command" >&2
  exit 1
fi

echo "Using supported stop command: $supported_stop_command"
"${datahub_quickstart_cmd[@]}" --stop
