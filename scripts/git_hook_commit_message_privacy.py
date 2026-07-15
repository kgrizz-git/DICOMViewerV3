#!/usr/bin/env python3
"""Block PHI/PII and local-environment details in Git commit messages.

The hook reads the message file supplied by Git's ``commit-msg`` hook.  It never
echoes a matched value: commit messages are durable repository metadata and may
become public even when the working tree is later cleaned.
"""

from __future__ import annotations

import argparse
import getpass
import ipaddress
import os
import re
import socket
import sys
from pathlib import Path

LOCAL_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[A-Za-z]:\\(?:Users|Documents and Settings)\\", re.I),
    re.compile(r"/(?:Users|home)/[^/\s]+/"),
    re.compile(r"/(?:private/)?var/folders/", re.I),
    re.compile(r"\\\\[^\\\s]+\\[^\\\s]+"),
)
ENDPOINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:dicom|pacs)://[^\s/]+", re.I),
    re.compile(r"\b[a-z0-9][a-z0-9.-]*\.(?:corp|internal|lan|local)\b", re.I),
    re.compile(r"\b(?:called|calling)[ _-]?ae(?:title)?\s*[:=]\s*\S+", re.I),
)
IDENTIFIER_PATTERN = re.compile(
    r"\b(?:mrn|patient[_ -]?id|accession(?:number)?|study[_ -]?id)\s*[:=#-]\s*[A-Za-z0-9-]{4,}",
    re.I,
)
IP_ADDRESS_TOKEN = re.compile(
    r"(?<![0-9A-Fa-f:.])(?:[0-9]{1,3}(?:\.[0-9]{1,3}){3}|[0-9A-Fa-f]{0,4}:[0-9A-Fa-f:.]+)(?![0-9A-Fa-f:.])"
)
PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)
GENERIC_IDENTITIES = frozenset({"localhost", "runner", "user", "username"})


def local_identities() -> frozenset[str]:
    """Return local account and host tokens without persisting them anywhere."""
    values = {
        getpass.getuser(),
        os.environ.get("USER", ""),
        os.environ.get("USERNAME", ""),
        socket.gethostname(),
        socket.getfqdn(),
    }
    return frozenset(
        value.lower()
        for value in values
        if len(value) >= 4 and value.lower() not in GENERIC_IDENTITIES
    )


def _has_private_network_address(line: str) -> bool:
    for match in IP_ADDRESS_TOKEN.finditer(line):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if any(address in network for network in PRIVATE_NETWORKS):
            return True
    return False


def _has_local_identity(line: str, identities: frozenset[str]) -> bool:
    return any(
        re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(identity)}(?![A-Za-z0-9_.-])", line, re.I
        )
        for identity in identities
    )


def check_message(
    message: str, identities: frozenset[str] | None = None
) -> list[tuple[int, str]]:
    """Return line numbers and redacted rule categories for a commit message."""
    local_terms = local_identities() if identities is None else identities
    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(message.splitlines(), start=1):
        if any(pattern.search(line) for pattern in LOCAL_PATH_PATTERNS):
            violations.append((lineno, "machine-specific path"))
        if _has_private_network_address(line):
            violations.append((lineno, "private-network address"))
        if any(pattern.search(line) for pattern in ENDPOINT_PATTERNS):
            violations.append((lineno, "internal PACS/DICOM endpoint"))
        if IDENTIFIER_PATTERN.search(line):
            violations.append((lineno, "patient or study identifier"))
        if _has_local_identity(line, local_terms):
            violations.append((lineno, "local account or hostname"))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message_file", type=Path, help="commit message file supplied by Git"
    )
    args = parser.parse_args(argv)
    try:
        message = args.message_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[commit-msg privacy] could not read message file ({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    violations = check_message(message)
    if not violations:
        return 0

    print(
        "[commit-msg privacy] BLOCKED: remove sensitive details from the commit message:",
        file=sys.stderr,
    )
    for lineno, rule in violations:
        print(f"  line {lineno}: {rule}", file=sys.stderr)
    print(
        "Do not paste the matched value into issues, chat, or documentation.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
