"""Protected fail-closed reports for internal diagnostics and scanner summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.privacy.redaction import redact_diagnostic_value
from utils.privacy.safe_storage import atomic_write_private_text


def write_redacted_json_report(
    path: Path,
    payload: Any,
    *,
    source_root: Path,
) -> Path:
    """Write a redacted internal JSON report outside the source checkout."""

    reduced = redact_diagnostic_value(payload)
    text = json.dumps(reduced, indent=2, sort_keys=True) + "\n"
    return atomic_write_private_text(path, text, source_root=source_root)
