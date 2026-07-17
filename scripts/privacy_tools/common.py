"""Shared execution and report protections for local privacy tools."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

MAX_REPORT_BYTES = 25 * 1024 * 1024
_NETWORK_CREDENTIALS = {
    "HOUNDDOG_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "PHI_SCAN_SMTP_PASSWORD",
    "PHI_SCAN_SMTP_USER",
}


class ToolStatus(StrEnum):
    """Stable status contract shared by every advisory wrapper."""

    CLEAN = "CLEAN"
    FINDINGS = "FINDINGS"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class PrivacyToolResult:
    """A redacted result containing structure and counts, never matched values."""

    tool: str
    status: ToolStatus
    finding_count: int = 0
    categories: Mapping[str, int] = field(default_factory=dict)
    version: str | None = None
    reason: str | None = None
    scanned_count: int = 0

    def summary(self) -> str:
        category_text = (
            ",".join(
                f"{name}:{count}" for name, count in sorted(self.categories.items())
            )
            or "none"
        )
        parts = [
            self.tool,
            self.status.value,
            f"scanned={self.scanned_count}",
            f"findings={self.finding_count}",
            f"categories={category_text}",
        ]
        if self.version:
            parts.append(f"version={self.version}")
        if self.reason:
            parts.append(f"reason={self.reason}")
        return " ".join(parts)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def resolve_executable(name_or_path: str) -> str | None:
    """Resolve an executable without running a shell."""
    candidate = Path(name_or_path)
    if candidate.parent != Path(".") and candidate.is_file():
        return str(candidate)
    return shutil.which(name_or_path)


def local_only_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an environment with scanner/cloud credentials removed."""
    environment = dict(os.environ)
    for name in _NETWORK_CREDENTIALS:
        environment.pop(name, None)
    environment.update(extra or {})
    return environment


def run_command(
    command: Sequence[str],
    *,
    timeout: float,
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run a bounded command without a shell and capture potentially sensitive output."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(environment or local_only_environment()),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", "", timed_out=True)
    except OSError:
        return CommandResult(127, "", "")
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


@contextmanager
def protected_workspace(prefix: str = "dvv-privacy-") -> Generator[Path]:
    """Create a mode-0700 temporary workspace and remove it on every exit path."""
    directory = Path(tempfile.mkdtemp(prefix=prefix))
    directory.chmod(stat.S_IRWXU)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def prepare_private_report(path: Path) -> None:
    """Pre-create a mode-0600 report target before handing it to a tool."""
    path.touch(mode=stat.S_IRUSR | stat.S_IWUSR, exist_ok=False)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_private_json(path: Path) -> object:
    """Load a bounded, regular, owner-private JSON report."""
    file_stat = path.lstat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError("report_not_regular")
    if file_stat.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError("report_not_private")
    if file_stat.st_size > MAX_REPORT_BYTES:
        raise ValueError("report_too_large")
    with path.open("r", encoding="utf-8") as report_file:
        return json.load(report_file)


def category_counts(items: object, *keys: str) -> dict[str, int]:
    """Count only named categories from list-of-object scanner results."""
    counts: dict[str, int] = {}
    if not isinstance(items, list):
        return counts
    for item in items:
        if not isinstance(item, dict):
            continue
        category = next(
            (item.get(key) for key in keys if isinstance(item.get(key), str)), None
        )
        safe_category = str(category or "unspecified").strip().lower().replace(" ", "-")
        if not safe_category.replace("-", "").replace("_", "").isalnum():
            safe_category = "unspecified"
        counts[safe_category] = counts.get(safe_category, 0) + 1
    return counts
