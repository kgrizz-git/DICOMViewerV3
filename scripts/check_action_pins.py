#!/usr/bin/env python3
"""Check that GitHub Action pins in ``.github/workflows`` are real commits.

Every remote ``uses:`` must be ``owner/repo@<40 hex>`` (a path such as
``github/codeql-action/init`` is still the ``github/codeql-action`` repository).
Local ``./`` actions are ignored. When the same line comments a version, such
as ``# v4.2.2`` or ``(v8.3.0)``, that tag must still contain the pinned commit.
A release tag may move forward; the pin stays valid when it is that tag or an
ancestor of it.

The GitHub API is required. ``GH_TOKEN`` or ``GITHUB_TOKEN`` must be set.
A missing token, a rate limit, or any other API error fails the process.
A missing commit is a finding, not a skipped pin.

Inputs:
    Workflow YAML under ``.github/workflows`` (or ``--workflows``).
    A GitHub token in the environment.

Outputs:
    Exit 0 when every pin exists and every commented tag matches.
    Exit 1 with one ``path:line:`` message per problem.

Requirements:
    Python 3.10+. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

API_ROOT = "https://api.github.com"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
USES_RE = re.compile(
    r"""uses:\s*['\"]?(?P<spec>[^'\"\s#]+)""",
)
VERSION_RE = re.compile(r"\bv\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.]+)?\b")
Fetch = Callable[[str, str], tuple[int, dict[str, object] | None]]


class PinCheckError(Exception):
    """The GitHub API could not be used, so the check must not pass."""


@dataclass(frozen=True)
class ActionUse:
    """One ``uses:`` line that refers to a remote action."""

    path: Path
    line: int
    repo: str
    sha: str | None
    raw_ref: str
    versions: tuple[str, ...]

    def label(self) -> str:
        """Return ``path:line`` for error messages."""
        return f"{self.path}:{self.line}"


def _repo_and_ref(spec: str) -> tuple[str, str] | None:
    """Split ``owner/repo[/path]@ref`` into ``(owner/repo, ref)``."""
    if spec.startswith("./") or spec.startswith("docker://"):
        return None
    if "@" not in spec:
        return None
    action, ref = spec.rsplit("@", 1)
    parts = action.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return f"{parts[0]}/{parts[1]}", ref


def _versions(comment: str) -> tuple[str, ...]:
    """Return version tags mentioned in a trailing comment, in order."""
    return tuple(dict.fromkeys(VERSION_RE.findall(comment)))


def iter_action_uses(workflows: Path) -> list[ActionUse]:
    """Collect remote action uses from workflow YAML files."""
    uses: list[ActionUse] = []
    files = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.search(line)
            if match is None:
                continue
            parsed = _repo_and_ref(match.group("spec"))
            if parsed is None:
                continue
            repo, ref = parsed
            sha = ref if SHA_RE.fullmatch(ref) else None
            uses.append(
                ActionUse(
                    path=path,
                    line=line_number,
                    repo=repo,
                    sha=sha,
                    raw_ref=ref,
                    versions=_versions(line.split("#", 1)[1] if "#" in line else ""),
                )
            )
    return uses


def _api_url(repo: str, *parts: str) -> str:
    """Build an API URL for ``repo`` without following URLs from responses."""
    suffix = "/".join(parts)
    return f"{API_ROOT}/repos/{repo}/{suffix}"


def _commit_for_tag(repo: str, tag: str, fetch: Fetch, token: str, cache: dict[str, str]) -> str:
    """Return the commit SHA a tag points at, peeling one annotated tag."""
    key = f"{repo}#{tag}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    status, body = fetch(_api_url(repo, "git", "ref", f"tags/{tag}"), token)
    if status == 404:
        raise KeyError(tag)
    if status != 200 or body is None:
        raise PinCheckError(f"GitHub API status {status} for {repo} tag {tag}")
    obj = body.get("object")
    if not isinstance(obj, dict):
        raise PinCheckError(f"GitHub tag response for {repo}@{tag} has no object")
    obj_type = str(obj.get("type", ""))
    obj_sha = str(obj.get("sha", ""))
    if obj_type == "tag":
        status, peeled = fetch(_api_url(repo, "git", "tags", obj_sha), token)
        if status != 200 or peeled is None:
            raise PinCheckError(f"GitHub API status {status} peeling {repo} tag {tag}")
        inner = peeled.get("object")
        if not isinstance(inner, dict) or str(inner.get("type", "")) != "commit":
            raise PinCheckError(f"Annotated tag {repo}@{tag} does not point at a commit")
        obj_sha = str(inner.get("sha", ""))
    elif obj_type != "commit":
        raise PinCheckError(f"Tag {repo}@{tag} has unexpected object type {obj_type}")
    cache[key] = obj_sha
    return obj_sha


def _commit_exists(repo: str, sha: str, fetch: Fetch, token: str, cache: dict[str, bool]) -> bool:
    """Return whether ``sha`` is a commit in ``repo``. Other API errors raise."""
    key = f"{repo}@{sha.lower()}"
    if key in cache:
        return cache[key]
    status, _body = fetch(_api_url(repo, "commits", sha), token)
    if status == 200:
        cache[key] = True
        return True
    if status in {404, 422}:
        cache[key] = False
        return False
    raise PinCheckError(f"GitHub API status {status} for {repo} commit {sha}")


def _tag_contains_pin(repo: str, pin: str, tagged: str, fetch: Fetch, token: str) -> str:
    """Return the compare status of ``pin``...``tagged``.

    ``ahead`` means the tag is a later commit on the pin's history. ``identical``
    means the tag still points at the pin. A moved release tag stays valid.
    """
    status, body = fetch(_api_url(repo, "compare", f"{pin}...{tagged}"), token)
    if status != 200 or body is None:
        raise PinCheckError(f"GitHub API status {status} comparing {repo} {pin}...{tagged}")
    return str(body.get("status", ""))


def check_action_uses(uses: list[ActionUse], fetch: Fetch, token: str) -> list[str]:
    """Return human-readable problems. Raise ``PinCheckError`` when the API fails."""
    problems: list[str] = []
    commits: dict[str, bool] = {}
    tags: dict[str, str] = {}
    for use in uses:
        if use.sha is None:
            problems.append(f"{use.label()}: {use.repo}@{use.raw_ref} is not a 40-character commit pin")
            continue
        if not _commit_exists(use.repo, use.sha, fetch, token, commits):
            problems.append(f"{use.label()}: {use.repo}@{use.sha} is not a commit")
            continue
        for version in use.versions:
            try:
                tagged = _commit_for_tag(use.repo, version, fetch, token, tags)
            except KeyError:
                problems.append(f"{use.label()}: {use.repo} has no tag {version}")
                continue
            if tagged.lower() == use.sha.lower():
                continue
            relation = _tag_contains_pin(use.repo, use.sha, tagged, fetch, token)
            if relation not in {"ahead", "identical"}:
                problems.append(
                    f"{use.label()}: {use.repo} tag {version} ({tagged}) does not contain {use.sha}"
                )
    return problems


def github_fetch(url: str, token: str) -> tuple[int, dict[str, object] | None]:
    """GET one GitHub API URL. Network and HTTP transport errors fail closed."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "dicom-viewer-action-pin-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise PinCheckError(f"GitHub API request failed for {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PinCheckError(f"GitHub API response for {url} was not an object")
    return status, payload


def token_from_environment() -> str:
    """Return the GitHub token, or raise when neither variable is set."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token.strip():
        raise PinCheckError("GH_TOKEN or GITHUB_TOKEN is required; refusing to skip the pin check")
    return token


def parse_args() -> argparse.Namespace:
    """Parse the workflow directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflows",
        type=Path,
        default=Path(".github/workflows"),
        help="Directory of workflow YAML files (default: .github/workflows).",
    )
    return parser.parse_args()


def main() -> int:
    """Run the pin check and print every problem."""
    args = parse_args()
    try:
        token = token_from_environment()
        problems = check_action_uses(iter_action_uses(args.workflows), github_fetch, token)
    except PinCheckError as failure:
        print(f"error: {failure}", file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"{len(problems)} action pin problem(s)", file=sys.stderr)
        return 1
    print(f"Action pins exist ({len(iter_action_uses(args.workflows))} remote use(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
