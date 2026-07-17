"""Protected per-user paths and atomic internal text storage."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

RETENTION_METADATA_FILENAME = ".privacy-retention.json"


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Non-sensitive retention metadata for one protected storage category."""

    max_age_days: int | None = 30
    max_files: int | None = 10
    delete_on_exit: bool = False

    def __post_init__(self) -> None:
        if self.max_age_days is not None and self.max_age_days < 0:
            raise ValueError("max_age_days must be non-negative or None")
        if self.max_files is not None and self.max_files < 0:
            raise ValueError("max_files must be non-negative or None")

    def as_dict(self) -> dict[str, int | bool | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DeletionResult:
    """Truthful aggregate result for a bounded internal-storage deletion."""

    removed: int = 0
    failed: int = 0

    @property
    def success(self) -> bool:
        return self.failed == 0


def _is_windows() -> bool:
    return os.name == "nt"


def _is_macos() -> bool:
    return sys.platform == "darwin"


def get_private_app_dir(
    category: str,
    *,
    app_name: str = "DICOMViewerV3",
    create: bool = True,
) -> Path:
    """Return a platform per-user directory for sensitive internal state."""

    clean_category = category.strip().replace("..", "").strip("/\\")
    if not clean_category:
        raise ValueError("category must name an internal storage area")
    if _is_windows():
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home())
    elif _is_macos():
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    path = base / app_name / clean_category
    if create:
        ensure_private_directory(path)
    return path


def ensure_private_directory(path: Path) -> Path:
    """Create a private directory and restrict POSIX permissions to the user."""

    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not _is_windows():
        path.chmod(0o700)
    return path


def assert_safe_internal_path(path: Path, *, source_root: Path | None = None) -> Path:
    """Reject internal-write targets inside an explicitly supplied source checkout."""

    resolved = path.expanduser().resolve(strict=False)
    if source_root is not None:
        root = source_root.expanduser().resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError:
            pass
        else:
            raise ValueError("sensitive internal output must not be written in the source checkout")
    return resolved


def atomic_write_private_text(
    path: Path,
    text: str,
    *,
    source_root: Path | None = None,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write a user-private internal text file."""

    resolved = assert_safe_internal_path(path, source_root=source_root)
    ensure_private_directory(resolved.parent)
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{resolved.name}.", dir=resolved.parent)
    tmp_path = Path(tmp_name)
    try:
        if not _is_windows():
            tmp_path.chmod(0o600)
        with os.fdopen(descriptor, "w", encoding=encoding) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, resolved)
        if not _is_windows():
            resolved.chmod(0o600)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        tmp_path.unlink(missing_ok=True)
        raise
    return resolved


def write_retention_metadata(
    directory: Path,
    policy: RetentionPolicy,
    *,
    source_root: Path | None = None,
) -> Path:
    """Persist a retention policy without recording file or patient details."""

    payload = json.dumps(policy.as_dict(), indent=2, sort_keys=True) + "\n"
    return atomic_write_private_text(
        directory / RETENTION_METADATA_FILENAME,
        payload,
        source_root=source_root,
    )


def secure_unlink(path: Path) -> bool:
    """Remove an internal file and report whether a file was actually removed."""

    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        # Callers decide whether deletion failure should be surfaced to the UI.
        raise
    return True


def is_user_private(path: Path) -> bool:
    """Return whether POSIX mode excludes group/other access."""

    if _is_windows():
        return True
    return stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
