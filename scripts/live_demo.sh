#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
run_dir="${CHANGE_PROOF_RUN_DIR:-$repo_root/.changeproof/run}"
make_bin="${CHANGE_PROOF_MAKE_BIN:-make}"
uv_bin="${CHANGE_PROOF_UV_BIN:-uv}"
docker_bin="${CHANGE_PROOF_DOCKER_BIN:-docker}"
curl_bin="${CHANGE_PROOF_CURL_BIN:-curl}"
lsof_bin="${CHANGE_PROOF_LSOF_BIN:-lsof}"
pid_file="$run_dir/dashboard.pid"
log_file="$run_dir/dashboard.log"

for command_name in "$make_bin" "$uv_bin" "$docker_bin" "$curl_bin" "$lsof_bin"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
done

mkdir -p "$run_dir"
cd "$repo_root"

if [[ -f "$pid_file" ]]; then
  recorded_pid="$(tr -d '[:space:]' < "$pid_file")"
  if [[ "$recorded_pid" =~ ^[0-9]+$ ]] && kill -0 "$recorded_pid" 2>/dev/null; then
    echo "ChangeProof is already running with PID $recorded_pid" >&2
    exit 1
  fi
  rm -f "$pid_file"
fi

"$docker_bin" info >/dev/null
"$make_bin" demo-baseline
"$make_bin" datahub-up
"$make_bin" datahub-seed
CHANGE_PROOF_LIVE_DATAHUB=1 "$uv_bin" run pytest tests/integration/test_datahub_context.py -q

if "$lsof_bin" -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop that service before starting ChangeProof." >&2
  exit 1
fi

CHANGE_PROOF_EVIDENCE_MODE=datahub \
  "$uv_bin" run uvicorn changeproof.app:app --host 127.0.0.1 --port 8000 \
  >"$log_file" 2>&1 &
dashboard_pid=$!
printf '%s\n' "$dashboard_pid" > "$pid_file"

cleanup_failed_start() {
  if kill -0 "$dashboard_pid" 2>/dev/null; then
    kill -TERM "$dashboard_pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
}

for _ in {1..30}; do
  if "$curl_bin" --fail --silent --show-error http://127.0.0.1:8000/healthz >/dev/null; then
    echo "ChangeProof live demo is ready"
    echo "ChangeProof: http://localhost:8000"
    echo "DataHub: http://localhost:9002"
    echo "Input: artist_id / varchar / bigint"
    echo "Stop: make demo-stop"
    exit 0
  fi
  if ! kill -0 "$dashboard_pid" 2>/dev/null; then
    echo "ChangeProof dashboard exited during startup. See $log_file" >&2
    cleanup_failed_start
    exit 1
  fi
  sleep 1
done

echo "ChangeProof dashboard did not become healthy within 30 seconds. See $log_file" >&2
cleanup_failed_start
exit 1
