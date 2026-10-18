"""Tests for scripts/check_action_pins.py. The GitHub API is replaced by a fake."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_action_pins import (
    PinCheckError,
    check_action_uses,
    iter_action_uses,
    token_from_environment,
)

SHA = "a" * 40
OTHER = "b" * 40


def _write(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


def test_parser_keeps_remote_pins_and_skips_local_actions(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write(
        workflows,
        "ci.yml",
        "\n".join(
            [
                "jobs:",
                "  build:",
                "    uses: ./.github/workflows/privacy-gates.yml",
                "    steps:",
                f"      - uses: actions/checkout@{SHA} # v7",
                f"      - uses: github/codeql-action/init@{OTHER} # v4.38.2",
                f"      # - uses: actions/checkout@{SHA} # v4",
                f"      - uses: actions/setup-node@{SHA} # Node v20",
                f"      - uses: SonarSource/sonarqube-scan-action@{SHA} # note (v8.3.0) only",
                "      - uses: actions/cache@v4",
                "      - uses: docker://alpine:3",
            ]
        )
        + "\n",
    )
    uses = iter_action_uses(workflows)
    assert [(item.repo, item.sha, item.versions) for item in uses] == [
        ("actions/checkout", SHA, ("v7",)),
        ("github/codeql-action", OTHER, ("v4.38.2",)),
        ("actions/setup-node", SHA, ()),
        ("SonarSource/sonarqube-scan-action", SHA, ("v8.3.0",)),
        ("actions/cache", None, ()),
    ]


def test_run_text_is_ignored_and_yaml_key_forms_are_kept(tmp_path: Path) -> None:
    """A run command that mentions uses: is not a pin. Quoted and flow keys are."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write(
        workflows,
        "ci.yml",
        "\n".join(
            [
                "jobs:",
                "  build:",
                "    steps:",
                f"      - run: 'echo \"uses: actions/checkout@{SHA}\"'",
                f"      - uses : actions/checkout@{SHA} # v7",
                f'      - "uses": actions/setup-python@{OTHER}',
                f"      - 'uses': actions/upload-artifact@{SHA}",
                f"      - {{uses: actions/cache@{SHA}}}",
                f"      - {{name: Checkout, uses: actions/download-artifact@{OTHER}}}",
            ]
        )
        + "\n",
    )
    uses = iter_action_uses(workflows)
    assert [(item.repo, item.sha, item.versions) for item in uses] == [
        ("actions/checkout", SHA, ("v7",)),
        ("actions/setup-python", OTHER, ()),
        ("actions/upload-artifact", SHA, ()),
        ("actions/cache", SHA, ()),
        ("actions/download-artifact", OTHER, ()),
    ]


def test_hidden_yaml_uses_are_checked_and_run_text_is_not(tmp_path: Path) -> None:
    """Forms a line search skips are still pins. A run script is not."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write(
        workflows,
        "ci.yml",
        "\n".join(
            [
                "pins:",
                "  bad: &bad evil/x@v1",
                "jobs:",
                "  build:",
                "    steps:",
                "      - run: |",
                "          uses: actions/cache@v4",
                "      - uses: >-",
                f"          actions/checkout@{SHA}",
                f"      - {{with: {{k: 1}}, uses: actions/cache@{SHA}, name: x}}",
                "      - - uses: actions/setup-python@" + OTHER,
                "        - uses: actions/upload-artifact@" + SHA,
                f'      - {{name: "C#", uses: actions/download-artifact@{SHA}}} # v8',
                f'      - uses: "actions/checkout\\x40{SHA}"',
                "      - uses: *bad",
                "      - uses: !!str evil/y@v1",
                "      - uses: actions/checkout",
            ]
        )
        + "\n",
    )
    uses = iter_action_uses(workflows)
    assert [(item.repo, item.raw_ref, item.sha, item.versions) for item in uses] == [
        ("actions/checkout", SHA, SHA, ()),
        ("actions/cache", SHA, SHA, ()),
        ("actions/setup-python", OTHER, OTHER, ()),
        ("actions/upload-artifact", SHA, SHA, ()),
        ("actions/download-artifact", SHA, SHA, ("v8",)),
        ("actions/checkout", SHA, SHA, ()),
        ("evil/x", "v1", None, ()),
        ("evil/y", "v1", None, ()),
        ("", "actions/checkout", None, ()),
    ]


def test_block_scalar_uses_does_not_take_the_next_step_comment(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ci.yml",
        f"""jobs:
  a:
    steps:
      - uses: >
          actions/checkout@{SHA}
      - uses: actions/cache@{OTHER} # v4.2.2
      - uses: |  # v7
          actions/setup-python@{SHA}
""",
    )
    uses = iter_action_uses(tmp_path)
    assert [(use.repo, use.versions) for use in uses] == [
        ("actions/checkout", ()),
        ("actions/cache", ("v4.2.2",)),
        ("actions/setup-python", ("v7",)),
    ]


def test_invalid_workflow_yaml_fails(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _write(workflows, "ci.yml", "jobs: [\n")
    with pytest.raises(PinCheckError, match="could not be parsed"):
        iter_action_uses(workflows)


def test_fork_commit_is_not_on_the_default_branch() -> None:
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("ci.yml"),
        line=3,
        repo="actions/checkout",
        sha=SHA,
        raw_ref=SHA,
        versions=(),
    )

    def fetch(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 200, {"sha": SHA}
        if url.endswith("/repos/actions/checkout"):
            return 200, {"default_branch": "main"}
        if url.endswith(f"/compare/{SHA}...main"):
            return 200, {"status": "diverged"}
        raise AssertionError(url)

    problems = check_action_uses([pinned], fetch, "token")
    assert "not on the default branch main" in problems[0]


def test_unrelated_fork_commit_is_a_finding_not_an_error() -> None:
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("ci.yml"),
        line=3,
        repo="actions/checkout",
        sha=SHA,
        raw_ref=SHA,
        versions=(),
    )

    def fetch(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 200, {"sha": SHA}
        if url.endswith("/repos/actions/checkout"):
            return 200, {"default_branch": "main"}
        if url.endswith(f"/compare/{SHA}...main"):
            return 404, None
        raise AssertionError(url)

    problems = check_action_uses([pinned], fetch, "token")
    assert problems == [f"ci.yml:3: actions/checkout@{SHA} is not on the default branch main"]


def test_release_tag_off_the_default_branch_passes() -> None:
    """msys2/setup-msys2 tags releases on history unrelated to ``main``."""
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("build.yml"),
        line=190,
        repo="msys2/setup-msys2",
        sha=SHA,
        raw_ref=SHA,
        versions=("v2.28.0",),
    )

    def fetch(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 200, {"sha": SHA}
        if url.endswith("/git/ref/tags/v2.28.0"):
            return 200, {"object": {"type": "commit", "sha": SHA}}
        raise AssertionError(url)

    assert check_action_uses([pinned], fetch, "token") == []


def test_redirects_are_refused() -> None:
    from scripts.check_action_pins import _refuse_redirect

    with pytest.raises(PinCheckError, match="redirect"):
        _refuse_redirect("https://example.com")


def test_missing_workflows_directory_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts.check_action_pins import main

    missing = tmp_path / "missing"
    monkeypatch.setattr("sys.argv", ["check_action_pins.py", "--workflows", str(missing)])
    assert main() == 1
    assert "not found" in capsys.readouterr().err


def test_empty_workflows_directory_has_no_uses(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    assert iter_action_uses(workflows) == []


def test_repository_workflows_are_full_commit_pins() -> None:
    """Every remote action in this checkout is a 40-character pin."""
    uses = iter_action_uses(Path(".github/workflows"))
    assert uses
    assert all(item.sha is not None for item in uses)


def test_missing_commit_and_tag_mismatch_are_findings() -> None:
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("build.yml"),
        line=10,
        repo="actions/cache",
        sha=SHA,
        raw_ref=SHA,
        versions=("v4.2.2",),
    )

    def fetch(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 422, None
        raise AssertionError(url)

    problems = check_action_uses([pinned], fetch, "token")
    assert problems == [f"build.yml:10: actions/cache@{SHA} is not a commit"]

    def fetch_tag(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 200, {"sha": SHA}
        if url.endswith("/repos/actions/cache"):
            return 200, {"default_branch": "main"}
        if url.endswith(f"/compare/{SHA}...main"):
            return 200, {"status": "ahead"}
        if url.endswith("/git/ref/tags/v4.2.2"):
            return 200, {"object": {"type": "commit", "sha": OTHER}}
        if "/compare/" in url:
            return 200, {"status": "diverged"}
        raise AssertionError(url)

    problems = check_action_uses([pinned], fetch_tag, "token")
    assert "does not contain" in problems[0]


def test_annotated_tag_match_passes() -> None:
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("ci.yml"),
        line=4,
        repo="actions/checkout",
        sha=SHA,
        raw_ref=SHA,
        versions=("v7",),
    )
    tag_object = "c" * 40

    def fetch(url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        if url.endswith(f"/commits/{SHA}"):
            return 200, {"sha": SHA}
        if url.endswith("/repos/actions/checkout"):
            return 200, {"default_branch": "main"}
        if url.endswith(f"/compare/{SHA}...main"):
            return 200, {"status": "identical"}
        if url.endswith("/git/ref/tags/v7"):
            return 200, {"object": {"type": "tag", "sha": tag_object}}
        if url.endswith(f"/git/tags/{tag_object}"):
            return 200, {"object": {"type": "commit", "sha": SHA}}
        raise AssertionError(url)

    assert check_action_uses([pinned], fetch, "token") == []


def test_api_error_fails_closed() -> None:
    from scripts.check_action_pins import ActionUse

    pinned = ActionUse(
        path=Path("ci.yml"),
        line=1,
        repo="actions/checkout",
        sha=SHA,
        raw_ref=SHA,
        versions=(),
    )

    def fetch(_url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        return 500, None

    with pytest.raises(PinCheckError, match="status 500"):
        check_action_uses([pinned], fetch, "token")


def test_missing_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(PinCheckError, match="GH_TOKEN"):
        token_from_environment()


def test_unpinned_ref_is_reported_without_network() -> None:
    from scripts.check_action_pins import ActionUse

    unpinned = ActionUse(
        path=Path("ci.yml"),
        line=2,
        repo="actions/cache",
        sha=None,
        raw_ref="v4",
        versions=(),
    )

    def fetch(_url: str, _token: str) -> tuple[int, dict[str, object] | None]:
        raise AssertionError("unpinned refs must not call the API")

    problems = check_action_uses([unpinned], fetch, "token")
    assert "not a 40-character commit pin" in problems[0]


def test_github_fetch_refuses_urls_outside_the_api() -> None:
    from scripts.check_action_pins import PinCheckError, github_fetch

    with pytest.raises(PinCheckError, match="outside the GitHub API"):
        github_fetch("https://example.com/repos/actions/checkout", "token")
