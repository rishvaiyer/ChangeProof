from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
START_SCRIPT = REPO_ROOT / "scripts/live_demo.sh"
STOP_SCRIPT = REPO_ROOT / "scripts/stop_live_demo.sh"


def _fake_commands(tmp_path: Path) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "commands.log"
    command = bin_dir / "command-double"
    command.write_text(
        """#!/usr/bin/env bash
set -eu
name="$(basename "$0")"
printf '%s %s\\n' "$name" "$*" >> "$CHANGE_PROOF_TEST_LOG"
case "$name" in
  docker) exit 0 ;;
  make)
    if [[ "${CHANGE_PROOF_TEST_FAIL_BASELINE:-0}" == "1" && "$*" == "demo-baseline" ]]; then
      exit 17
    fi
    ;;
  lsof) exit "${CHANGE_PROOF_TEST_PORT_OCCUPIED:-1}" ;;
  curl) exit 0 ;;
  uv)
    if [[ "$*" == *"uvicorn changeproof.app:app"* ]]; then
      exec sleep 60
    fi
    ;;
esac
exit 0
"""
    )
    command.chmod(0o755)
    for name in ("docker", "make", "uv", "curl", "lsof"):
        (bin_dir / name).symlink_to(command)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "CHANGE_PROOF_TEST_LOG": str(log_path),
            "CHANGE_PROOF_RUN_DIR": str(tmp_path / "run"),
        }
    )
    return env, log_path


def _stop_started_dashboard(env: dict[str, str]) -> None:
    pid_file = Path(env["CHANGE_PROOF_RUN_DIR"]) / "dashboard.pid"
    if pid_file.exists():
        os.kill(int(pid_file.read_text().strip()), 15)


def test_start_runs_live_pipeline_in_order(tmp_path: Path) -> None:
    env, log_path = _fake_commands(tmp_path)

    try:
        result = subprocess.run(
            [START_SCRIPT], env=env, text=True, capture_output=True, check=False
        )
    finally:
        _stop_started_dashboard(env)

    assert result.returncode == 0, result.stderr
    calls = log_path.read_text().splitlines()
    expected = [
        "docker info",
        "make demo-baseline",
        "make datahub-up",
        "make datahub-seed",
        "uv run pytest tests/integration/test_datahub_context.py -q",
        "uv run uvicorn changeproof.app:app --host 127.0.0.1 --port 8000",
    ]
    assert [next(i for i, call in enumerate(calls) if item in call) for item in expected] == sorted(
        next(i for i, call in enumerate(calls) if item in call) for item in expected
    )
    assert "ChangeProof live demo is ready" in result.stdout


def test_start_stops_after_failed_baseline(tmp_path: Path) -> None:
    env, log_path = _fake_commands(tmp_path)
    env["CHANGE_PROOF_TEST_FAIL_BASELINE"] = "1"

    result = subprocess.run(
        [START_SCRIPT], env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode != 0
    calls = log_path.read_text()
    assert "make demo-baseline" in calls
    assert "datahub-seed" not in calls
    assert "uvicorn" not in calls


def test_start_rejects_occupied_port_before_uvicorn(tmp_path: Path) -> None:
    env, log_path = _fake_commands(tmp_path)
    env["CHANGE_PROOF_TEST_PORT_OCCUPIED"] = "0"

    result = subprocess.run(
        [START_SCRIPT], env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode != 0
    assert "Port 8000 is already in use" in result.stderr
    assert "uvicorn" not in log_path.read_text()


def test_stop_terminates_recorded_pid_and_stops_datahub(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    process = subprocess.Popen(["sleep", "60"])
    (run_dir / "dashboard.pid").write_text(str(process.pid))
    stop_log = tmp_path / "stop.log"
    stop_double = tmp_path / "stop-datahub"
    stop_double.write_text(f"#!/usr/bin/env bash\necho stopped >> {stop_log!s}\n")
    stop_double.chmod(0o755)

    result = subprocess.run(
        [STOP_SCRIPT],
        env={
            **os.environ,
            "CHANGE_PROOF_RUN_DIR": str(run_dir),
            "CHANGE_PROOF_DATAHUB_STOP_SCRIPT": str(stop_double),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    process.wait(timeout=3)

    assert result.returncode == 0, result.stderr
    assert process.returncode == -15
    assert not (run_dir / "dashboard.pid").exists()
    assert stop_log.read_text().strip() == "stopped"


def test_stop_removes_stale_pid_without_signaling(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "dashboard.pid").write_text("99999999")
    stop_double = tmp_path / "stop-datahub"
    stop_double.write_text("#!/usr/bin/env bash\nexit 0\n")
    stop_double.chmod(0o755)

    result = subprocess.run(
        [STOP_SCRIPT],
        env={
            **os.environ,
            "CHANGE_PROOF_RUN_DIR": str(run_dir),
            "CHANGE_PROOF_DATAHUB_STOP_SCRIPT": str(stop_double),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (run_dir / "dashboard.pid").exists()
