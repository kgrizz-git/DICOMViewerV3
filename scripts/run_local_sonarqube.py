#!/usr/bin/env python3
"""Run an opt-in local SonarQube Community Build analysis for this repository.

This is deliberately not a Git hook. It submits source analysis only by
default; pass --with-coverage when the additional full pytest run is wanted.
The script records the most recent successful scanner submission in
.sonar-local/last-analysis.json, which is intentionally ignored by Git.

Usage (from the repository root, with the project venv active):
    export SONAR_TOKEN=<analysis-token>
    python scripts/run_local_sonarqube.py
    python scripts/run_local_sonarqube.py --with-coverage
    python scripts/run_local_sonarqube.py --status
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_SETTINGS = Path("tools/sonarqube/sonar-project.properties")
DEFAULT_HOST_URL = "http://localhost:9000"
DEFAULT_PROJECT_KEY = "dicom-viewer-v3"
SCANNER_IMAGE = "sonarsource/sonar-scanner-cli:latest"
SCANNER_CACHE_VOLUME = "dicom-viewer-v3-sonar-scanner-cache"
STATE_DIRECTORY = Path(".sonar-local")
STATE_FILE_NAME = "last-analysis.json"


def normalize_host_url(value: str) -> str:
    """Validate a SonarQube server URL and remove its trailing slash."""
    url = value.rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("SONAR_HOST_URL must be a full http(s) URL, for example http://localhost:9000")
    return url


def docker_host_url(host_url: str, override: str | None = None) -> str:
    """Return a URL that a Dockerized scanner can use to reach SonarQube."""
    if override:
        return normalize_host_url(override)

    parsed = urlsplit(host_url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return host_url

    netloc = "host.docker.internal"
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def state_path(repo_root: Path) -> Path:
    """Return the ignored per-checkout record of successful submissions."""
    return repo_root / STATE_DIRECTORY / STATE_FILE_NAME


def read_last_submission(repo_root: Path) -> dict[str, Any] | None:
    """Return the saved submission record, or None when this checkout has none."""
    path = state_path(repo_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        print(f"Ignoring malformed local SonarQube record: {path.relative_to(repo_root)}", file=sys.stderr)
        return None
    return data if isinstance(data, dict) else None


def write_last_submission(
    repo_root: Path,
    *,
    host_url: str,
    project_key: str,
    scanner: str,
    included_coverage: bool,
) -> Path:
    """Atomically record a scanner submission that completed successfully."""
    path = state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "submitted_at_utc": datetime.now(UTC).isoformat(),
        "host_url": host_url,
        "project_key": project_key,
        "dashboard_url": f"{host_url}/dashboard?id={quote(project_key, safe='')}",
        "scanner": scanner,
        "included_coverage": included_coverage,
    }
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
    return path


def print_last_submission(repo_root: Path) -> int:
    """Display the saved submission record without contacting the server."""
    record = read_last_submission(repo_root)
    if record is None:
        print("No completed local SonarQube analysis submission is recorded for this checkout.")
        return 1

    print(f"Last submission: {record.get('submitted_at_utc', 'unknown time')}")
    print(f"Project: {record.get('project_key', 'unknown')}")
    print(f"Scanner: {record.get('scanner', 'unknown')}")
    print(f"Coverage included: {record.get('included_coverage', False)}")
    print(f"Dashboard: {record.get('dashboard_url', 'unknown')}")
    return 0


def get_server_status(host_url: str, timeout_seconds: float = 5.0) -> str:
    """Return SonarQube's system status or raise an actionable connection error."""
    endpoint = f"{host_url}/api/system/status"
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"could not reach {endpoint}: {exc}") from exc

    status = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(status, str):
        raise RuntimeError(f"unexpected response from {endpoint}")
    return status


def scanner_mode(requested_mode: str) -> str:
    """Select the installed native scanner first, then the Docker scanner."""
    if requested_mode != "auto":
        return requested_mode
    if shutil.which("sonar-scanner"):
        return "local"
    if shutil.which("docker"):
        return "docker"
    raise RuntimeError("Neither sonar-scanner nor Docker is available on PATH.")


def scanner_properties(project_key: str, include_coverage: bool, *, docker: bool) -> list[str]:
    """Build scanner arguments shared by native and Docker scanner modes."""
    working_directory = "/tmp/sonar-work" if docker else ".sonar-local/work"
    properties = [
        f"-Dproject.settings={PROJECT_SETTINGS.as_posix()}",
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.working.directory={working_directory}",
    ]
    if include_coverage:
        properties.append("-Dsonar.python.coverage.reportPaths=.sonar-local/coverage.xml")
    return properties


def build_scanner_command(
    repo_root: Path,
    *,
    mode: str,
    project_key: str,
    include_coverage: bool,
) -> list[str]:
    """Build a token-free scanner command; SONAR_TOKEN stays in the environment."""
    if mode == "local":
        return ["sonar-scanner", *scanner_properties(project_key, include_coverage, docker=False)]
    if mode == "docker":
        return [
            "docker",
            "run",
            "--rm",
            "--add-host",
            "host.docker.internal:host-gateway",
            "-e",
            "SONAR_HOST_URL",
            "-e",
            "SONAR_TOKEN",
            "--mount",
            f"type=bind,src={repo_root},dst=/usr/src,readonly",
            "--mount",
            f"type=volume,src={SCANNER_CACHE_VOLUME},dst=/opt/sonar-scanner/.sonar/cache",
            "-w",
            "/usr/src",
            SCANNER_IMAGE,
            *scanner_properties(project_key, include_coverage, docker=True),
        ]
    raise ValueError(f"Unsupported scanner mode: {mode}")


def run_coverage(repo_root: Path) -> int:
    """Generate the optional coverage report with the project's active Python."""
    coverage_path = repo_root / STATE_DIRECTORY / "coverage.xml"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "--cov=src",
        f"--cov-report=xml:{coverage_path}",
    ]
    print("Running pytest with coverage before SonarQube analysis...")
    return subprocess.run(command, cwd=repo_root).returncode


def parse_args() -> argparse.Namespace:
    """Parse the narrow local-analysis command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show the last successful local scanner submission without contacting SonarQube.",
    )
    parser.add_argument(
        "--with-coverage",
        action="store_true",
        help="Run the full pytest suite with coverage before submitting analysis.",
    )
    parser.add_argument(
        "--host-url",
        default=os.environ.get("SONAR_HOST_URL", DEFAULT_HOST_URL),
        help="SonarQube Community Build URL (default: %(default)s).",
    )
    parser.add_argument(
        "--docker-host-url",
        default=os.environ.get("SONAR_DOCKER_HOST_URL"),
        help="Override the URL used inside the Docker scanner container.",
    )
    parser.add_argument(
        "--project-key",
        default=DEFAULT_PROJECT_KEY,
        help="Project key on the local SonarQube instance (default: %(default)s).",
    )
    parser.add_argument(
        "--scanner",
        choices=("auto", "local", "docker"),
        default="auto",
        help="Scanner launcher (default: %(default)s).",
    )
    parser.add_argument(
        "--skip-server-check",
        action="store_true",
        help="Skip the local /api/system/status readiness check.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the requested local analysis and return its shell exit status."""
    args = parse_args()
    repo_root = REPO_ROOT
    if args.status:
        return print_last_submission(repo_root)

    try:
        host_url = normalize_host_url(args.host_url)
        docker_url = docker_host_url(host_url, args.docker_host_url)
        mode = scanner_mode(args.scanner)
    except (RuntimeError, ValueError) as exc:
        print(f"SonarQube setup error: {exc}", file=sys.stderr)
        return 2

    if not os.environ.get("SONAR_TOKEN"):
        print(
            "SONAR_TOKEN is not set. Create an analysis token in SonarQube "
            "(User > My Account > Security) and export it before running this command.",
            file=sys.stderr,
        )
        return 2

    if not args.skip_server_check:
        try:
            status = get_server_status(host_url)
        except RuntimeError as exc:
            print(f"SonarQube is not ready: {exc}", file=sys.stderr)
            return 2
        if status != "UP":
            print(f"SonarQube is not ready: {host_url} reported status {status!r}.", file=sys.stderr)
            return 2

    if args.with_coverage and run_coverage(repo_root) != 0:
        print("Coverage run failed; SonarQube analysis was not submitted.", file=sys.stderr)
        return 1

    if mode == "local":
        (repo_root / STATE_DIRECTORY / "work").mkdir(parents=True, exist_ok=True)

    environment = os.environ.copy()
    environment["SONAR_HOST_URL"] = docker_url if mode == "docker" else host_url
    command = build_scanner_command(
        repo_root,
        mode=mode,
        project_key=args.project_key,
        include_coverage=args.with_coverage,
    )
    print(f"Submitting local SonarQube analysis with {mode} scanner...")
    result = subprocess.run(command, cwd=repo_root, env=environment)
    if result.returncode != 0:
        print("SonarQube scanner failed; last-analysis.json was left unchanged.", file=sys.stderr)
        return result.returncode or 1

    record_path = write_last_submission(
        repo_root,
        host_url=host_url,
        project_key=args.project_key,
        scanner=mode,
        included_coverage=args.with_coverage,
    )
    record = read_last_submission(repo_root)
    dashboard_url = record.get("dashboard_url") if record else f"{host_url}/dashboard?id={args.project_key}"
    print(f"Analysis submitted. Recorded at {record_path.relative_to(repo_root)}")
    print(f"Dashboard: {dashboard_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
