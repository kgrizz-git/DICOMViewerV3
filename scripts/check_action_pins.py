#!/usr/bin/env python3
"""Check that GitHub Action pins in ``.github/workflows`` are real commits.

Workflow files are parsed as YAML. Every ``uses`` value must be
``owner/repo@<40 hex>`` (a path such as ``github/codeql-action/init`` is still
the ``github/codeql-action`` repository). Quoted keys, flow mappings, folded
scalars, aliases, and quoted escapes are read as YAML, so a ``run`` script that
mentions ``uses:`` is not an action. Local ``./`` actions and ``docker://``
actions are ignored. A value that is not ``owner/repo@ref`` is a finding.
The pinned commit must be the default branch tip or an ancestor of it, so a
commit that exists only in a fork does not pass. A version comment on the
value's ending line must still contain the pinned commit.
The comment must be only the tag (``# v4.2.2``) or the tag must be in
parentheses (``(v8.3.0)``). Other words, such as ``Node v20``, are not tags.
A release tag may move forward; the pin stays valid when it is that tag or an
ancestor of it.

The GitHub API is required. ``GH_TOKEN`` or ``GITHUB_TOKEN`` must be set.
A missing token, a rate limit, a redirect, an unreadable workflow, or any
other API error fails the process. A missing ``--workflows`` directory fails
the process. A missing commit is a finding, not a skipped pin.

Inputs:
    Workflow YAML under ``.github/workflows`` (or ``--workflows``).
    PyYAML (``requirements-dev.txt``).
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

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode

API_ROOT = "https://api.github.com"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]+")
_VERSION_TOKEN = r"v\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.]+)?"
WHOLE_COMMENT_VERSION_RE = re.compile(rf"^{_VERSION_TOKEN}$")
PAREN_VERSION_RE = re.compile(rf"\(({_VERSION_TOKEN})\)")
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
    """Return pin tags from a trailing comment.

    A tag counts when the comment is only that tag (``v4.2.2``) or the tag is
    in parentheses (``(v8.3.0)``). Other words, such as ``Node v20``, are not
    tags.
    """
    text = comment.strip()
    found: list[str] = []
    whole = WHOLE_COMMENT_VERSION_RE.fullmatch(text)
    if whole is not None:
        found.append(whole.group(0))
    found.extend(PAREN_VERSION_RE.findall(text))
    return tuple(dict.fromkeys(found))


class _WorkflowLoader(yaml.SafeLoader):
    """Safe YAML loader that records every ``uses`` value while parsing."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.found: list[tuple[Node, Node, object]] = []
        self.seen: set[tuple[int, int]] = set()


def _construct_yaml_map(loader: _WorkflowLoader, node: MappingNode):
    """Build a mapping and remember each ``uses`` value once.

    PyYAML fills mappings in two steps so an anchor can point at the mapping
    before its keys exist. Recording happens before that fill, and ``seen``
    ignores the second walk of the same node.
    """
    data: dict[object, object] = {}
    yield data
    for key_node, value_node in node.value:
        if not isinstance(key_node, ScalarNode) or key_node.value != "uses":
            continue
        ident = (key_node.start_mark.line, key_node.start_mark.column)
        if ident in loader.seen:
            continue
        loader.seen.add(ident)
        loader.found.append((key_node, value_node, loader.construct_object(value_node, deep=True)))
    data.update(yaml.constructor.SafeConstructor.construct_mapping(loader, node))


_WorkflowLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_yaml_map,
)


def _comment_after(lines: list[str], key_node: Node, value_node: Node) -> str:
    """Return version-comment text for this ``uses`` key.

    The comment is the last ``#`` on the key's line. An alias reuses an earlier
    node, so the value's own end is not on that line; a folded value can also
    carry a comment where the value ends. A block scalar (``|`` or ``>``) is
    skipped: its end mark points at the next line, which belongs to the
    following step, and its only comment slot is the header on the key's line.
    """
    parts: list[str] = []
    key_line = key_node.start_mark.line
    if 0 <= key_line < len(lines) and "#" in lines[key_line]:
        parts.append(lines[key_line].split("#")[-1])
    if isinstance(value_node, ScalarNode) and value_node.style in {"|", ">"}:
        return " ".join(parts)
    end = value_node.end_mark
    if end.line != key_line and 0 <= end.line < len(lines) and "#" in lines[end.line][end.column :]:
        parts.append(lines[end.line][end.column :].split("#", 1)[1])
    return " ".join(parts)


def _use_from_value(path: Path, lines: list[str], key_node: Node, value_node: Node, value: object) -> ActionUse | None:
    """Turn one parsed ``uses`` value into a remote action, or skip local ones."""
    line = key_node.start_mark.line + 1
    versions = _versions(_comment_after(lines, key_node, value_node))
    if not isinstance(value, str) or not value.strip():
        return ActionUse(path, line, "", None, "unsupported value", versions)
    spec = value.strip()
    if spec.startswith("./") or spec.startswith("docker://"):
        return None
    parsed = _repo_and_ref(spec)
    if parsed is None:
        return ActionUse(path, line, "", None, spec, versions)
    repo, ref = parsed
    sha = ref if SHA_RE.fullmatch(ref) else None
    return ActionUse(path, line, repo, sha, ref, versions)


def _uses_in_file(path: Path) -> list[ActionUse]:
    """Parse one workflow and return its remote ``uses`` values in source order."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    loader = _WorkflowLoader(text)
    try:
        while loader.check_data():
            loader.get_data()
    except yaml.YAMLError as failure:
        raise PinCheckError(f"{path}: workflow YAML could not be parsed: {failure}") from failure
    finally:
        loader.dispose()
    loader.found.sort(key=lambda item: (item[0].start_mark.line, item[0].start_mark.column))
    uses: list[ActionUse] = []
    for key_node, value_node, value in loader.found:
        use = _use_from_value(path, lines, key_node, value_node, value)
        if use is not None:
            uses.append(use)
    return uses


def iter_action_uses(workflows: Path) -> list[ActionUse]:
    """Collect remote action uses from workflow YAML files."""
    files = sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml"))
    uses: list[ActionUse] = []
    for path in files:
        uses.extend(_uses_in_file(path))
    return uses


def _repo_url(repo: str) -> str:
    """Return the repository URL, with no trailing slash."""
    return f"{API_ROOT}/repos/{repo}"


def _api_url(repo: str, *parts: str) -> str:
    """Build an API URL for ``repo`` from local path parts."""
    return f"{_repo_url(repo)}/{'/'.join(parts)}"


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
    ``unrelated`` means the two commits share no history.
    """
    status, body = fetch(_api_url(repo, "compare", f"{pin}...{tagged}"), token)
    if status == 404 and body is None:
        # GitHub answers 404 when the two commits share no history.
        return "unrelated"
    if status != 200 or body is None:
        raise PinCheckError(f"GitHub API status {status} comparing {repo} {pin}...{tagged}")
    return str(body.get("status", ""))


def _default_branch(repo: str, fetch: Fetch, token: str, cache: dict[str, str]) -> str:
    """Return ``repo``'s default branch. The result is cached for this run."""
    cached = cache.get(repo)
    if cached is not None:
        return cached
    status, body = fetch(_repo_url(repo), token)
    if status != 200 or body is None:
        raise PinCheckError(f"GitHub API status {status} for {repo}")
    branch = body.get("default_branch")
    if not isinstance(branch, str) or _BRANCH_RE.fullmatch(branch) is None:
        raise PinCheckError(f"GitHub repository {repo} has no usable default branch")
    cache[repo] = branch
    return branch


def _version_problems(
    use: ActionUse, sha: str, fetch: Fetch, token: str, tags: dict[str, str]
) -> tuple[list[str], bool]:
    """Check ``use``'s version comments against upstream tags.

    Return the problems and whether some upstream tag contains the pin. A fork
    commit is never in an upstream tag's history, so a containing tag proves the
    pin is upstream code even when releases live off the default branch.
    """
    problems: list[str] = []
    in_tag = False
    for version in use.versions:
        try:
            tagged = _commit_for_tag(use.repo, version, fetch, token, tags)
        except KeyError:
            problems.append(f"{use.label()}: {use.repo} has no tag {version}")
            continue
        if tagged.lower() == sha.lower():
            in_tag = True
            continue
        relation = _tag_contains_pin(use.repo, sha, tagged, fetch, token)
        if relation in {"ahead", "identical"}:
            in_tag = True
            continue
        problems.append(
            f"{use.label()}: {use.repo} tag {version} ({tagged}) does not contain {sha}"
        )
    return problems, in_tag


def check_action_uses(uses: list[ActionUse], fetch: Fetch, token: str) -> list[str]:
    """Return human-readable problems. Raise ``PinCheckError`` when the API fails."""
    problems: list[str] = []
    commits: dict[str, bool] = {}
    branches: dict[str, str] = {}
    tags: dict[str, str] = {}
    for use in uses:
        if use.sha is None:
            shown = f"{use.repo}@{use.raw_ref}" if use.repo else use.raw_ref
            problems.append(f"{use.label()}: {shown} is not a 40-character commit pin")
            continue
        if not _commit_exists(use.repo, use.sha, fetch, token, commits):
            problems.append(f"{use.label()}: {use.repo}@{use.sha} is not a commit")
            continue
        version_problems, in_tag = _version_problems(use, use.sha, fetch, token, tags)
        problems.extend(version_problems)
        if in_tag:
            continue
        branch = _default_branch(use.repo, fetch, token, branches)
        relation = _tag_contains_pin(use.repo, use.sha, branch, fetch, token)
        if relation not in {"ahead", "identical"}:
            problems.append(
                f"{use.label()}: {use.repo}@{use.sha} is not on the default branch {branch}"
            )
    return problems


def _refuse_redirect(newurl: str) -> None:
    """Fail closed instead of following a redirect."""
    raise PinCheckError(f"Refusing a GitHub API redirect to {newurl}")


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """Reject redirects so a response cannot send the token to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Fail closed instead of following ``newurl``."""
        _refuse_redirect(str(newurl))
        return None


def github_fetch(url: str, token: str) -> tuple[int, dict[str, object] | None]:
    """GET one GitHub API URL. Network and HTTP transport errors fail closed.

    Only ``https://api.github.com/`` URLs are requested. Redirects are refused.
    ``urlopen`` is not used: Semgrep treats every non-literal ``urlopen`` as a
    dynamic URL, including one this module just built. ``build_opener`` uses the
    default HTTPS handler, which verifies certificates.
    """
    prefix = f"{API_ROOT}/"
    if not url.startswith(prefix):
        raise PinCheckError("Refusing a URL outside the GitHub API")
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
    opener = urllib.request.build_opener(_RefuseRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            raw = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as http_failure:
        return int(http_failure.code), None
    except (urllib.error.URLError, TimeoutError, OSError) as failure:
        raise PinCheckError(f"GitHub API request failed for {url}: {failure}") from failure
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as failure:
        raise PinCheckError(f"GitHub API response for {url} was not JSON") from failure
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
    if not args.workflows.is_dir():
        print(f"error: workflow directory not found: {args.workflows}", file=sys.stderr)
        return 1
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
