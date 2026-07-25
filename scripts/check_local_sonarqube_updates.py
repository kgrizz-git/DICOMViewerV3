#!/usr/bin/env python3
"""Advisory, metadata-only update check for the local SonarQube server image.

The command compares the locally installed ``sonarqube:community`` image with
the matching platform manifest on Docker Hub. It never pulls an image, starts a
container, or sends repository content. Results are retained only in ignored
``.sonar-local/last-update-check.json`` so a main pre-push checks at most once
per seven days.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(".sonar-local/last-update-check.json")
SERVER_IMAGE = "sonarqube:community"
DEFAULT_INTERVAL_DAYS = 7
SCANNER_RELEASE_URL = "https://api.github.com/repos/SonarSource/sonar-scanner-cli/releases/latest"
DOCKER_TOKEN_URL = "https://auth.docker.io/token"
DOCKER_MANIFEST_URL = "https://registry-1.docker.io/v2/library/sonarqube/manifests/community"


def state_path(repo_root: Path) -> Path:
    """Return the ignored path used for the last successful check."""
    return repo_root / STATE_PATH


def read_state(repo_root: Path) -> dict[str, Any] | None:
    """Read the local update-check state if it is valid JSON object data."""
    try:
        payload = json.loads(state_path(repo_root).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def parse_checked_at(state: dict[str, Any] | None) -> datetime | None:
    """Return a normalized check time from a saved state record."""
    value = state.get("checked_at_utc") if state else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def check_is_due(repo_root: Path, *, interval_days: int, now: datetime) -> bool:
    """Return whether a successful metadata check is missing or old enough."""
    checked_at = parse_checked_at(read_state(repo_root))
    return checked_at is None or now - checked_at >= timedelta(days=interval_days)


def run_docker(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a read-only Docker metadata command without exposing command output."""
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )


def local_image_details() -> tuple[str, str, str] | None:
    """Return local manifest digest, architecture, and OS without a registry request."""
    result = run_docker(
        [
            "docker",
            "image",
            "inspect",
            SERVER_IMAGE,
            "--format",
            "{{index .RepoDigests 0}} {{.Architecture}} {{.Os}}",
        ]
    )
    fields = result.stdout.strip().split() if result.returncode == 0 else []
    if len(fields) != 3 or "@" not in fields[0]:
        return None
    return (fields[0].rsplit("@", maxsplit=1)[1], fields[1], fields[2])


def remote_image_id() -> str | None:
    """Return Docker Hub's top-level tag digest without pulling an image."""
    try:
        token_request = Request(
            f"{DOCKER_TOKEN_URL}?{urlencode({'service': 'registry.docker.io', 'scope': 'repository:library/sonarqube:pull'})}",
            headers={"Accept": "application/json"},
        )
        with urlopen(token_request, timeout=10.0) as response:
            token_payload = json.loads(response.read().decode("utf-8"))
        token = token_payload.get("token") if isinstance(token_payload, dict) else None
        if not isinstance(token, str) or not token:
            return None
        manifest_request = Request(
            DOCKER_MANIFEST_URL,
            headers={
                "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json",
                "Authorization": f"Bearer {token}",
            },
        )
        with urlopen(manifest_request, timeout=10.0) as response:
            digest = response.headers.get("Docker-Content-Digest")
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return digest if isinstance(digest, str) and digest.startswith("sha256:") else None


def native_scanner_version() -> str | None:
    """Return the version of a native scanner when one is installed on PATH."""
    result = run_docker(["sonar-scanner", "--version"])
    match = re.search(r"SonarScanner CLI ([^\s]+)", result.stdout) if result.returncode == 0 else None
    return match.group(1) if match else None


def latest_scanner_version() -> str | None:
    """Read SonarSource's public latest-release metadata without uploading code."""
    request = Request(SCANNER_RELEASE_URL, headers={"Accept": "application/vnd.github+json"})
    try:
        with urlopen(request, timeout=10.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    version = payload.get("tag_name") if isinstance(payload, dict) else None
    return version if isinstance(version, str) and version else None


def version_key(version: str) -> tuple[int, ...] | None:
    """Normalize a dotted numeric release version for a newer-than comparison."""
    parts = version.split(".")
    return tuple(int(part) for part in parts) if all(part.isdigit() for part in parts) else None


def write_state(
    repo_root: Path,
    *,
    local_id: str,
    remote_id: str,
    update_available: bool,
    scanner_version: str | None,
    latest_scanner: str | None,
    scanner_update_available: bool | None,
    now: datetime,
) -> None:
    """Atomically save only the metadata needed to throttle future checks."""
    path = state_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checked_at_utc": now.isoformat(),
                "image": SERVER_IMAGE,
                "local_image_id": local_id,
                "remote_image_id": remote_id,
                "update_available": update_available,
                "scanner_version": scanner_version,
                "latest_scanner_version": latest_scanner,
                "scanner_update_available": scanner_update_available,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def check_for_update(repo_root: Path, *, interval_days: int = DEFAULT_INTERVAL_DAYS, now: datetime | None = None) -> int:
    """Check the server image only when due; failures are intended to be advisory."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if not check_is_due(repo_root, interval_days=interval_days, now=current):
        print("Local SonarQube update check is not due yet.")
        return 0
    local = local_image_details()
    if local is None:
        print("Local SonarQube update check could not inspect the server image.", file=sys.stderr)
        return 2
    local_id, _architecture, _operating_system = local
    remote_id = remote_image_id()
    if remote_id is None:
        print("Local SonarQube update check could not read Docker Hub metadata.", file=sys.stderr)
        return 2
    update_available = local_id != remote_id
    scanner_version = native_scanner_version()
    latest_scanner = latest_scanner_version() if scanner_version else None
    if scanner_version and latest_scanner is None:
        print("Local SonarQube update check could not read scanner release metadata.", file=sys.stderr)
        return 2
    scanner_key = version_key(scanner_version) if scanner_version else None
    latest_scanner_key = version_key(latest_scanner) if latest_scanner else None
    scanner_update_available = (
        latest_scanner_key > scanner_key
        if scanner_key is not None and latest_scanner_key is not None
        else None
    )
    write_state(
        repo_root,
        local_id=local_id,
        remote_id=remote_id,
        update_available=update_available,
        scanner_version=scanner_version,
        latest_scanner=latest_scanner,
        scanner_update_available=scanner_update_available,
        now=current,
    )
    if update_available:
        print("A newer local SonarQube server image is available; no image was pulled.")
    else:
        print("Local SonarQube server image is up to date.")
    if scanner_version is None:
        print("No native sonar-scanner is installed; Docker scanner fallback needs no separate check.")
    elif scanner_update_available:
        print("A newer native sonar-scanner release is available; nothing was installed.")
    elif scanner_update_available is False:
        print("Native sonar-scanner is up to date.")
    else:
        print("Native sonar-scanner version could not be compared safely.")
    return 0


def parse_args() -> argparse.Namespace:
    """Parse the intentionally small update-check command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--interval-days",
        type=int,
        default=DEFAULT_INTERVAL_DAYS,
        help="Minimum days between successful metadata checks (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    """Run the update check."""
    args = parse_args()
    if args.interval_days < 1:
        print("--interval-days must be at least 1", file=sys.stderr)
        return 2
    return check_for_update(REPO_ROOT, interval_days=args.interval_days)


if __name__ == "__main__":
    raise SystemExit(main())
