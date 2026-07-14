"""Benchmark startup time by launching the app with DICOM_PERF_LOG=1."""

import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_PY = ROOT / "run.py"
BASELINES_DIR = ROOT / "dev-docs" / "perf-baselines"
CSV_FILE = BASELINES_DIR / "startup.csv"
N_RUNS = 5


def run_once() -> dict[str, float]:
    env = os.environ.copy()
    env["DICOM_PERF_LOG"] = "1"
    proc = subprocess.Popen(
        [sys.executable, str(RUN_PY), "--exit-after-init"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    t0 = time.perf_counter()
    try:
        out, _ = proc.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {}
    wall_ms = (time.perf_counter() - t0) * 1000

    result: dict[str, float] = {"wall_ms": wall_ms}
    # Parse [PERF] lines
    for line in out.splitlines():
        m = re.search(r"\[PERF\]\s+imports:\s+([\d.]+)ms.*app_init:\s+([\d.]+)ms.*total:\s+([\d.]+)ms", line)
        if m:
            result["imports_ms"] = float(m.group(1))
            result["app_init_ms"] = float(m.group(2))
            result["total_ms"] = float(m.group(3))
    return result


def main() -> None:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for i in range(N_RUNS):
        print(f"Run {i + 1}/{N_RUNS}...", end=" ", flush=True)
        r = run_once()
        if r:
            print(f"wall={r.get('wall_ms', 0):.0f}ms")
            results.append(r)
        else:
            print("TIMEOUT")

    if not results:
        print("No successful runs.")
        return

    # Print summary
    for key in ["wall_ms", "imports_ms", "app_init_ms", "total_ms"]:
        vals = [r[key] for r in results if key in r]
        if vals:
            vals.sort()
            median = vals[len(vals) // 2]
            print(f"  {key}: median={median:.0f}ms  min={min(vals):.0f}ms  max={max(vals):.0f}ms")

    # Append to CSV
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True
        ).strip()
    except Exception:
        sha = "unknown"

    write_header = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["timestamp", "git_sha", "wall_ms", "imports_ms", "app_init_ms", "total_ms"])
        from datetime import datetime
        ts = datetime.now().isoformat(timespec="seconds")
        for r in results:
            w.writerow([ts, sha, r.get("wall_ms", ""), r.get("imports_ms", ""), r.get("app_init_ms", ""), r.get("total_ms", "")])
    print(f"Results appended to {CSV_FILE}")


if __name__ == "__main__":
    main()
