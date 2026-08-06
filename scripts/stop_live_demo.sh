#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$script_dir/.." && pwd)"
run_dir="${CHANGE_PROOF_RUN_DIR:-$repo_root/.changeproof/run}"
pid_file="$run_dir/dashboard.pid"
start_file="$run_dir/dashboard.start"
datahub_stop_script="${CHANGE_PROOF_DATAHUB_STOP_SCRIPT:-$repo_root/scripts/stop_datahub.sh}"

process_start_token() {
  ps -o lstart= -p "$1" 2>/dev/null \
    | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
    || true
}

if [[ -f "$pid_file" ]]; then
  dashboard_pid="$(tr -d '[:space:]' < "$pid_file")"
  if [[ ! "$dashboard_pid" =~ ^[0-9]+$ ]]; then
    echo "Refusing invalid dashboard PID: $dashboard_pid" >&2
    exit 1
  fi

  recorded_start=""
  if [[ -f "$start_file" ]]; then
    recorded_start="$(sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$start_file")"
  fi
  current_start="$(process_start_token "$dashboard_pid")"

  if kill -0 "$dashboard_pid" 2>/dev/null \
    && [[ -n "$recorded_start" && "$current_start" == "$recorded_start" ]]; then
    kill -TERM "$dashboard_pid"
    for _ in {1..100}; do
      process_state="$(ps -o stat= -p "$dashboard_pid" 2>/dev/null | tr -d '[:space:]' || true)"
      if ! kill -0 "$dashboard_pid" 2>/dev/null || [[ "$process_state" == Z* ]]; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$dashboard_pid" 2>/dev/null; then
      process_state="$(ps -o stat= -p "$dashboard_pid" 2>/dev/null | tr -d '[:space:]' || true)"
      if [[ "$process_state" != Z* ]]; then
        echo "Dashboard PID $dashboard_pid did not stop within 10 seconds." >&2
        exit 1
      fi
    fi
  elif kill -0 "$dashboard_pid" 2>/dev/null; then
    echo "Recorded PID identity is stale; leaving PID $dashboard_pid untouched."
  fi
  rm -f "$pid_file" "$start_file"
fi

"$datahub_stop_script"
echo "ChangeProof live demo stopped"
