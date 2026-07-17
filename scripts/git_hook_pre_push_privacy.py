#!/usr/bin/env python3
"""Block privacy-sensitive Git metadata before push without echoing values.

Git supplies one stdin line per ref update:
``local-ref local-oid remote-ref remote-oid``. A zero remote object ID denotes
an initial push, so every commit reachable from the local object is inspected.
The validator is read-only and reports only fixed rule categories and counts.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.check_no_phi_artifacts import local_identities, path_reasons
from scripts.git_hook_commit_message_privacy import check_message

OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$", re.I)
SENSITIVE_REF = re.compile(
    r"(?:^|[/_.-])(?:mrn|patientid|patientname|accession(?:number)?|"
    r"studyid|accountnumber)[_.:=#-]+[A-Za-z0-9^-]{4,}",
    re.I,
)


@dataclass(frozen=True)
class RefUpdate:
    local_ref: str
    local_oid: str
    remote_ref: str
    remote_oid: str


def _git(root: Path, args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def _is_zero_oid(value: str) -> bool:
    return bool(value) and set(value) == {"0"} and len(value) in {40, 64}


def parse_updates(stdin_text: str) -> tuple[list[RefUpdate], Counter[str]]:
    """Parse pre-push stdin, returning only fixed categories for malformed input."""
    updates: list[RefUpdate] = []
    violations: Counter[str] = Counter()
    for line in stdin_text.splitlines():
        fields = line.split()
        if len(fields) != 4:
            violations["malformed ref update"] += 1
            continue
        local_ref, local_oid, remote_ref, remote_oid = fields
        if not OBJECT_ID.fullmatch(local_oid) or not OBJECT_ID.fullmatch(remote_oid):
            violations["invalid object ID"] += 1
            continue
        updates.append(RefUpdate(local_ref, local_oid, remote_ref, remote_oid))
    return updates, violations


def _ref_categories(root: Path, ref_name: str, identities: frozenset[str]) -> list[str]:
    categories: list[str] = []
    if _git(root, ["check-ref-format", ref_name]).returncode != 0:
        categories.append("invalid ref name")
    if SENSITIVE_REF.search(ref_name):
        categories.append("patient or study identifier in ref")
    categories.extend(path_reasons(ref_name, identities))
    categories.extend(category for _, category in check_message(ref_name, identities))
    return list(dict.fromkeys(categories))


def _commit_oids(root: Path, update: RefUpdate) -> tuple[list[str], str | None]:
    if _is_zero_oid(update.local_oid):
        return [], None  # deletion
    revision = (
        update.local_oid
        if _is_zero_oid(update.remote_oid)
        else f"{update.remote_oid}..{update.local_oid}"
    )
    completed = _git(root, ["rev-list", revision])
    if completed.returncode != 0:
        return [], "commit range could not be inspected"
    return [line for line in completed.stdout.splitlines() if line], None


def _author_email_allowed(email: str) -> bool:
    lowered = email.strip().lower()
    return lowered.endswith("@users.noreply.github.com") or lowered == "noreply@github.com"


def _remote_has_userinfo(remote_url: str) -> bool:
    parsed = urlsplit(remote_url.strip())
    return bool(parsed.netloc and parsed.username is not None)


def validate_push(
    root: Path,
    stdin_text: str,
    *,
    remote_url: str = "",
) -> Counter[str]:
    """Return category counts for a proposed push; never mutate repository state."""
    root = root.resolve()
    updates, violations = parse_updates(stdin_text)
    identities = local_identities()
    if remote_url and _remote_has_userinfo(remote_url):
        violations["remote URL userinfo"] += 1

    inspected_commits: set[str] = set()
    for update in updates:
        for ref_name in (update.local_ref, update.remote_ref):
            for category in _ref_categories(root, ref_name, identities):
                violations[category] += 1
        commits, error = _commit_oids(root, update)
        if error:
            violations[error] += 1
            continue
        for commit_oid in commits:
            if commit_oid in inspected_commits:
                continue
            inspected_commits.add(commit_oid)
            completed = _git(root, ["show", "-s", "--format=%ae", commit_oid])
            if completed.returncode != 0:
                violations["author metadata could not be inspected"] += 1
            elif not _author_email_allowed(completed.stdout):
                violations["author email policy"] += 1
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--remote-name", default="", help=argparse.SUPPRESS)
    parser.add_argument("--remote-url", default="")
    args = parser.parse_args(argv)
    try:
        stdin_text = sys.stdin.read()
        violations = validate_push(
            args.root,
            stdin_text,
            remote_url=args.remote_url,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print_redacted(
            f"[pre-push privacy] ERROR ({type(exc).__name__}); no values displayed",
            file=sys.stderr,
        )
        return 2
    if not violations:
        print("[pre-push privacy] CLEAN: proposed Git metadata passed")
        return 0
    print("[pre-push privacy] BLOCKED: Git metadata policy violation(s):", file=sys.stderr)
    for category, count in sorted(violations.items()):
        print(f"  {category}: {count}", file=sys.stderr)
    print("Matched metadata values are intentionally omitted.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
