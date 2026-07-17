#!/usr/bin/env python3
"""Read-only, category-only privacy preflight for local Git state and remotes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_no_phi_artifacts import (
    CONTENT_RULES,
    IP_ADDRESS_TOKEN,
    address_requires_redaction,
    local_identities,
    path_reasons,
)
from scripts.git_hook_commit_message_privacy import check_message
from scripts.gitleaks_privacy_scan import run_scan


@dataclass
class PreflightReport:
    """Counts and fixed categories only; never raw Git metadata."""

    reachable_commits: int = 0
    history_path_categories: Counter[str] = field(default_factory=Counter)
    commit_message_categories: Counter[str] = field(default_factory=Counter)
    author_email_classes: Counter[str] = field(default_factory=Counter)
    ref_categories: Counter[str] = field(default_factory=Counter)
    remote_categories: Counter[str] = field(default_factory=Counter)
    initial_commit_covered: bool = False
    gitleaks_staged_status: str = "not-run"
    gitleaks_history_status: str = "not-run"

    @property
    def risk_count(self) -> int:
        metadata_risks = sum(
            sum(counter.values())
            for counter in (
                self.history_path_categories,
                self.commit_message_categories,
                self.ref_categories,
                self.remote_categories,
            )
        )
        metadata_risks += sum(
            count
            for category, count in self.author_email_classes.items()
            if category != "github-noreply"
        )
        return metadata_risks + sum(
            status in {"blocked", "error"}
            for status in (self.gitleaks_staged_status, self.gitleaks_history_status)
        )

    def json_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["risk_count"] = self.risk_count
        return payload


def _git(root: Path, args: list[str], *, allow_failure: bool = False) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode and not allow_failure:
        raise RuntimeError("Git metadata could not be inspected")
    return completed.stdout


def _email_class(email: str) -> str:
    lowered = email.strip().lower()
    if lowered.endswith("@users.noreply.github.com"):
        return "github-noreply"
    if lowered.endswith((".local", ".lan", ".internal")) or "@localhost" in lowered:
        return "local-or-internal"
    return "other-address"


def _remote_reasons(url: str, identities: frozenset[str]) -> list[str]:
    reasons: list[str] = []
    stripped = url.strip()
    parsed = urlsplit(stripped)
    if parsed.scheme == "file" or stripped.startswith(("/", "./", "../", "\\\\")):
        reasons.append("local remote path")
    if parsed.netloc and "@" in parsed.netloc:
        reasons.append("remote URL userinfo")
    for pattern, category in CONTENT_RULES:
        if category in {"authenticated URL", "DICOM/PACS endpoint", "internal hostname"} and pattern.search(stripped):
            reasons.append(category)
    for match in IP_ADDRESS_TOKEN.finditer(stripped):
        try:
            import ipaddress

            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        if address_requires_redaction(address):
            reasons.append("remote network address")
    if any(
        re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(identity)}(?![A-Za-z0-9_.-])",
            stripped,
            re.I,
        )
        for identity in identities
    ):
        reasons.append("local identity in remote")
    return list(dict.fromkeys(reasons))


def _scan_status(code: int) -> str:
    if code == 0:
        return "clean"
    return "blocked" if code == 1 else "error"


def audit_repository(root: Path, *, run_gitleaks: bool = True) -> PreflightReport:
    """Audit local Git state without changing refs, the index, remotes, or files."""
    root = root.resolve()
    report = PreflightReport()
    identities = local_identities()
    commits = [
        item
        for item in _git(root, ["rev-list", "HEAD"], allow_failure=True).splitlines()
        if item
    ]
    report.reachable_commits = len(commits)
    for commit in commits:
        message = _git(root, ["show", "-s", "--format=%B", commit])
        for _, category in check_message(message, identities):
            report.commit_message_categories[category] += 1
        email = _git(root, ["show", "-s", "--format=%ae", commit]).strip()
        report.author_email_classes[_email_class(email)] += 1

    history_paths = _git(
        root,
        ["log", "--format=", "--name-only", "HEAD"],
        allow_failure=True,
    )
    for path in set(history_paths.splitlines()):
        if not path:
            continue
        for category in path_reasons(path, identities):
            report.history_path_categories[category] += 1

    refs = _git(root, ["for-each-ref", "--format=%(refname)"])
    for ref_name in refs.splitlines():
        for category in path_reasons(ref_name, identities):
            report.ref_categories[category] += 1
        for _, category in check_message(ref_name, identities):
            report.ref_categories[category] += 1

    for remote in _git(root, ["remote"]).splitlines():
        urls = _git(root, ["remote", "get-url", "--all", remote], allow_failure=True)
        for url in urls.splitlines():
            for category in _remote_reasons(url, identities):
                report.remote_categories[category] += 1

    root_commits = _git(
        root,
        ["rev-list", "--max-parents=0", "HEAD"],
        allow_failure=True,
    )
    report.initial_commit_covered = bool(commits and root_commits.strip())
    if run_gitleaks:
        staged_code, _ = run_scan(root, "staged")
        history_code, _ = run_scan(root, "history")
        report.gitleaks_staged_status = _scan_status(staged_code)
        report.gitleaks_history_status = _scan_status(history_code)
    return report


def _print_text(report: PreflightReport) -> None:
    print("Privacy remote preflight (values redacted)")
    print(f"reachable_commits={report.reachable_commits}")
    print(f"initial_commit_covered={str(report.initial_commit_covered).lower()}")
    for label, counter in (
        ("history_paths", report.history_path_categories),
        ("commit_messages", report.commit_message_categories),
        ("author_emails", report.author_email_classes),
        ("refs", report.ref_categories),
        ("remotes", report.remote_categories),
    ):
        print(f"{label}=" + json.dumps(dict(sorted(counter.items())), sort_keys=True))
    print(f"gitleaks_staged={report.gitleaks_staged_status}")
    print(f"gitleaks_history={report.gitleaks_history_status}")
    print(f"risk_count={report.risk_count}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-gitleaks", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        report = audit_repository(args.root, run_gitleaks=not args.skip_gitleaks)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print_redacted(
            f"Privacy remote preflight ERROR ({type(exc).__name__}); no values displayed",
            file=sys.stderr,
        )
        return 2
    if args.json:
        print(json.dumps(report.json_payload(), sort_keys=True))
    else:
        _print_text(report)
    return 1 if report.risk_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
