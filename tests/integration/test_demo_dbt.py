from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_DIR = Path("demo/sonicledger")


def test_sonicledger_baseline_builds() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "dbt",
            "build",
            "--project-dir",
            str(PROJECT_DIR),
            "--profiles-dir",
            str(PROJECT_DIR),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
