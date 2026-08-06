#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
run_dir="${CHANGE_PROOF_RUN_DIR:-$repo_root/.changeproof/run}"
make_bin="${CHANGE_PROOF_MAKE_BIN:-make}"
uv_bin="${CHANGE_PROOF_UV_BIN:-uv}"
uvicorn_bin="${CHANGE_PROOF_UVICORN_BIN:-$repo_root/.venv/bin/uvicorn}"
docker_bin="${CHANGE_PROOF_DOCKER_BIN:-docker}"
curl_bin="${CHANGE_PROOF_CURL_BIN:-curl}"
lsof_bin="${CHANGE_PROOF_LSOF_BIN:-lsof}"
ps_bin="${CHANGE_PROOF_PS_BIN:-ps}"
pid_file="$run_dir/dashboard.pid"
start_file="$run_dir/dashboard.start"
log_file="$run_dir/dashboard.log"

process_start_token() {
  "$ps_bin" -o lstart= -p "$1" 2>/dev/null \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
    || true
}

recorded_process_matches() {
  [[ -f "$pid_file" && -f "$start_file" ]] || return 1
  local candidate_pid candidate_start current_start
  candidate_pid="$(tr -d '[:space:]' < "$pid_file")"
  candidate_start="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$start_file")"
  [[ "$candidate_pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$candidate_pid" 2>/dev/null || return 1
  current_start="$(process_start_token "$candidate_pid")"
  [[ -n "$candidate_start" && "$current_start" == "$candidate_start" ]]
}

for command_name in "$make_bin" "$uv_bin" "$docker_bin" "$curl_bin" "$lsof_bin" "$ps_bin"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command not found: $command_name" >&2
    exit 1
  fi
done

mkdir -p "$run_dir"
cd "$repo_root"

if [[ -f "$pid_file" ]]; then
  recorded_pid="$(tr -d '[:space:]' < "$pid_file")"
  if recorded_process_matches; then
    if "$curl_bin" --fail --silent --show-error \
      --data 'column=artist_id&old_type=varchar&new_type=bigint' \
      http://127.0.0.1:8000/analyze \
      | grep -q 'Live DataHub MCP evidence'; then
      echo "ChangeProof live demo is already running with PID $recorded_pid"
      echo "ChangeProof: http://localhost:8000"
      echo "DataHub: http://localhost:9002"
      echo "Stop: make demo-stop"
      exit 0
    fi
    echo "Recorded ChangeProof PID $recorded_pid is running but unhealthy. Run make demo-stop." >&2
    exit 1
  fi
  rm -f "$pid_file" "$start_file"
fi

"$docker_bin" info >/dev/null
"$make_bin" demo-baseline
if ! command -v "$uvicorn_bin" >/dev/null 2>&1; then
  echo "Uvicorn executable not found after environment setup: $uvicorn_bin" >&2
  exit 1
fi
"$make_bin" datahub-up
"$make_bin" datahub-seed
CHANGE_PROOF_LIVE_DATAHUB=1 "$uv_bin" run pytest tests/integration/test_datahub_context.py -q

if "$lsof_bin" -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop that service before starting ChangeProof." >&2
  exit 1
fi

nohup env CHANGE_PROOF_EVIDENCE_MODE=datahub \
  "$uvicorn_bin" changeproof.app:app --host 127.0.0.1 --port 8000 \
  </dev/null >"$log_file" 2>&1 &
dashboard_pid=$!
printf '%s\n' "$dashboard_pid" > "$pid_file"
dashboard_start="$(process_start_token "$dashboard_pid")"
if [[ -z "$dashboard_start" ]]; then
  echo "Could not record dashboard process identity; PID $dashboard_pid was left untouched." >&2
  exit 1
fi
printf '%s\n' "$dashboard_start" > "$start_file"

cleanup_failed_start() {
  if recorded_process_matches \
    && [[ "$(tr -d '[:space:]' < "$pid_file")" == "$dashboard_pid" ]]; then
    kill -TERM "$dashboard_pid" 2>/dev/null || true
  fi
  rm -f "$pid_file" "$start_file"
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
  if ! recorded_process_matches; then
    echo "ChangeProof dashboard exited during startup. See $log_file" >&2
    cleanup_failed_start
    exit 1
  fi
  sleep 1
done

echo "ChangeProof dashboard did not become healthy within 30 seconds. See $log_file" >&2
cleanup_failed_start
exit 1
