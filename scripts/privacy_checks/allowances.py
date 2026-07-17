"""Reviewed, rule-specific inline exception handling."""

from __future__ import annotations

import re

_REVIEWED_ALLOW = re.compile(
    r"privacy-check:\s*allow\[(?P<rule>[a-z0-9-]+)\]"
    r"\s+review=(?P<review>[A-Za-z0-9][A-Za-z0-9._/-]+)",
    re.IGNORECASE,
)


def reviewed_allowance(source_lines: list[str], line: int, rule: str) -> bool:
    """Return whether a line carries a reviewed exception for one exact rule."""

    if line < 1 or line > len(source_lines):
        return False
    match = _REVIEWED_ALLOW.search(source_lines[line - 1])
    return bool(match and match.group("rule").lower() == rule.lower())
