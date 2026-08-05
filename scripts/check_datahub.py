from __future__ import annotations

import argparse
import time

import httpx

from changeproof.config import Settings


def check_datahub_health(
    gms_url: str,
    timeout_seconds: float = 5.0,
    attempts: int = 1,
    interval_seconds: float = 2.0,
) -> bool:
    endpoint = f"{gms_url.rstrip('/')}/config"
    for attempt in range(1, attempts + 1):
        try:
            response = httpx.get(endpoint, timeout=timeout_seconds)
            if response.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        if attempt < attempts:
            time.sleep(interval_seconds)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the local DataHub GMS health endpoint.")
    parser.add_argument("--gms-url", default=Settings.from_env().datahub_gms_url)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    args = parser.parse_args()

    healthy = check_datahub_health(
        gms_url=args.gms_url,
        timeout_seconds=args.timeout_seconds,
        attempts=args.attempts,
        interval_seconds=args.interval_seconds,
    )
    if healthy:
        print(f"DataHub GMS is healthy at {args.gms_url.rstrip('/')}/config")
        return 0

    print(f"DataHub GMS did not become healthy at {args.gms_url.rstrip('/')}/config")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
