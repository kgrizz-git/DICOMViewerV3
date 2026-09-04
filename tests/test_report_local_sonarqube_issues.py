from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "report_local_sonarqube_issues.py"
    spec = importlib.util.spec_from_file_location("report_local_sonarqube_issues", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def _issue(*, component: str = "dicom-viewer-v3:src/example.py", line: int = 12) -> dict[str, Any]:
    return {
        "severity": "BLOCKER",
        "type": "BUG",
        "rule": "python:S930",
        "component": component,
        "line": line,
    }


def _page(issues: list[dict[str, Any]], *, total: int, page: int) -> dict[str, Any]:
    return {"paging": {"total": total, "pageIndex": page}, "issues": issues}


def _sample_report(module: ModuleType):
    return module.SonarReport(
        project_key="dicom-viewer-v3",
        analysis=module.AnalysisMetadata(date="2026-07-18", revision="abc123"),
        issues=(
            module.SonarIssue(
                severity="BLOCKER",
                issue_type="BUG",
                rule="python:S930",
                path="src/example.py",
                line=12,
            ),
        ),
    )


def test_fetch_issues_uses_component_filter_and_keeps_token_out_of_url(monkeypatch):
    module = _load_module()
    calls = []

    def fake_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return _Response(_page([_issue()], total=1, page=1))

    monkeypatch.setattr(module.requests, "get", fake_get)

    issues = module.fetch_issues(
        "http://localhost:9000", "test-token", "dicom-viewer-v3", {"severities": "BLOCKER"}
    )

    assert len(issues) == 1
    parsed = parse_qs(urlparse(calls[0][0]).query)
    assert parsed["componentKeys"] == ["dicom-viewer-v3"]
    assert parsed["severities"] == ["BLOCKER"]
    assert parsed["statuses"] == ["OPEN,CONFIRMED,REOPENED"]
    assert "projectKeys" not in parsed
    assert "test-token" not in calls[0][0]
    assert calls[0][1]["Authorization"]


def test_fetch_issues_collects_all_pages(monkeypatch):
    module = _load_module()

    def fake_get(url, headers, timeout):
        assert timeout == 10.0
        page = int(parse_qs(urlparse(url).query)["p"][0])
        if page == 1:
            return _Response(_page([_issue(line=12)], total=2, page=1))
        return _Response(_page([_issue(line=24)], total=2, page=2))

    monkeypatch.setattr(module.requests, "get", fake_get)

    issues = module.fetch_issues(
        "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
    )

    assert [issue.line for issue in issues] == [12, 24]


def test_fetch_issues_rejects_foreign_component(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *_args, **_kwargs: _Response(
            _page([_issue(component="other-project:src/example.py")], total=1, page=1)
        ),
    )

    with pytest.raises(module.SonarReportError, match="different component"):
        module.fetch_issues(
            "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
        )


def test_fetch_issues_rejects_malformed_and_incomplete_responses(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module.requests, "get", lambda *_args, **_kwargs: _Response({"issues": []}))

    with pytest.raises(module.SonarReportError, match="incomplete issue-search payload"):
        module.fetch_issues(
            "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
        )

    monkeypatch.setattr(module.requests, "get", lambda *_args, **_kwargs: _Response(_page([], total=1, page=1)))
    with pytest.raises(module.SonarReportError, match="pagination was incomplete"):
        module.fetch_issues(
            "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
        )


def test_collect_reported_findings_queries_all_priority_severities(monkeypatch):
    module = _load_module()
    seen_queries = []

    def fake_fetch_issues(_host, _token, _project, query):
        seen_queries.append(query)
        return ()

    monkeypatch.setattr(module, "fetch_issues", fake_fetch_issues)
    monkeypatch.setattr(
        module,
        "fetch_latest_analysis",
        lambda *_args: module.AnalysisMetadata(date="2026-07-18", revision="abc123"),
    )

    report = module.collect_reported_findings("http://localhost:9000", "token", "dicom-viewer-v3")

    assert report.issues == ()
    assert seen_queries == [
        {"severities": "BLOCKER"},
        {"severities": "CRITICAL"},
        {"severities": "MAJOR"},
    ]


def test_markdown_report_is_token_free_and_output_stays_in_tmp(tmp_path):
    module = _load_module()
    report = _sample_report(module)

    markdown = module.render_markdown_report(report)
    assert "test-token" not in markdown
    output_path = module.resolve_output_path(tmp_path, Path("tmp/report.md"))
    module.write_markdown_report(output_path, report)
    assert output_path.read_text(encoding="utf-8") == markdown

    with pytest.raises(module.SonarReportError, match="must stay below"):
        module.resolve_output_path(tmp_path, Path("report.md"))


def test_json_archive_writes_timestamped_and_latest_under_tmp(tmp_path):
    module = _load_module()
    report = _sample_report(module)
    dump_dir = module.resolve_dump_directory(tmp_path, Path("tmp/sonarqube-findings"))
    stamped = datetime(2026, 9, 3, 23, 5, 0, tzinfo=UTC)

    timestamped_path, latest_path = module.archive_findings_json(
        dump_dir,
        report,
        dumped_at_utc=stamped,
        git_head="deadbeef",
    )

    assert timestamped_path.name == "20260903T230500Z_dicom-viewer-v3_abc123.json"
    assert latest_path.name == "latest.json"
    payload = json.loads(timestamped_path.read_text(encoding="utf-8"))
    assert payload == json.loads(latest_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["by_severity"] == {"BLOCKER": 1}
    assert payload["issues"][0]["path"] == "src/example.py"
    assert "message" not in payload["issues"][0]
    payload_text = timestamped_path.read_text(encoding="utf-8")
    assert "file-token" not in payload_text
    assert "SONAR_TOKEN" not in payload_text
    assert "test-token" not in payload_text

    with pytest.raises(module.SonarReportError, match="--dump-dir must stay below"):
        module.resolve_dump_directory(tmp_path, Path("sonarqube-findings"))
    with pytest.raises(module.SonarReportError, match="--dump-dir must stay below"):
        module.resolve_dump_directory(tmp_path, Path("tmp/../escape"))
    custom = module.resolve_dump_directory(tmp_path, (tmp_path / "tmp" / "custom").resolve())
    assert custom == (tmp_path / "tmp" / "custom").resolve()


def test_current_git_head_returns_none_when_git_missing(monkeypatch, tmp_path):
    module = _load_module()

    def boom(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(module.subprocess, "run", boom)
    assert module.current_git_head(tmp_path) is None


def test_main_loads_token_from_dotenv_and_dumps_json(monkeypatch, tmp_path, capsys):
    module = _load_module()
    (tmp_path / ".env").write_text("SONAR_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["report_local_sonarqube_issues.py"])
    seen_tokens: list[str] = []
    report = module.SonarReport(
        project_key="dicom-viewer-v3",
        analysis=module.AnalysisMetadata(date="2026-07-18", revision="abc123"),
        issues=(),
    )
    monkeypatch.setattr(module, "get_server_status", lambda _host: "UP")
    monkeypatch.setattr(
        module,
        "collect_reported_findings",
        lambda _host, token, _project: seen_tokens.append(token) or report,
    )
    monkeypatch.setattr(module, "current_git_head", lambda _root: "abc123")

    assert module.main() == 0
    assert seen_tokens == ["file-token"]
    dump_dir = tmp_path / "tmp" / "sonarqube-findings"
    latest = dump_dir / "latest.json"
    assert latest.is_file()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 0
    assert "JSON archive:" in capsys.readouterr().out


def test_main_no_dump_skips_archive(monkeypatch, tmp_path, capsys):
    module = _load_module()
    (tmp_path / ".env").write_text("SONAR_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["report_local_sonarqube_issues.py", "--no-dump"])
    report = module.SonarReport(
        project_key="dicom-viewer-v3",
        analysis=module.AnalysisMetadata(date="2026-07-18", revision="abc123"),
        issues=(),
    )
    monkeypatch.setattr(module, "get_server_status", lambda _host: "UP")
    monkeypatch.setattr(module, "collect_reported_findings", lambda *_args: report)

    assert module.main() == 0
    assert not (tmp_path / "tmp" / "sonarqube-findings").exists()
    assert "JSON archive skipped" in capsys.readouterr().out


def test_main_custom_dump_dir_and_markdown_output(monkeypatch, tmp_path, capsys):
    module = _load_module()
    (tmp_path / ".env").write_text("SONAR_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "report_local_sonarqube_issues.py",
            "--dump-dir",
            "tmp/custom-findings",
            "--output",
            "tmp/priority.md",
        ],
    )
    report = _sample_report(module)
    monkeypatch.setattr(module, "get_server_status", lambda _host: "UP")
    monkeypatch.setattr(module, "collect_reported_findings", lambda *_args: report)
    monkeypatch.setattr(module, "current_git_head", lambda _root: "abc123")

    assert module.main() == 0
    assert (tmp_path / "tmp" / "custom-findings" / "latest.json").is_file()
    assert (tmp_path / "tmp" / "priority.md").is_file()
    output = capsys.readouterr().out
    assert "JSON archive:" in output
    assert "Markdown report written" in output


def test_write_text_atomically_closes_fd_when_chmod_fails(monkeypatch, tmp_path):
    module = _load_module()
    closed: list[int] = []
    real_close = module.os.close

    def tracking_close(fd: int) -> None:
        closed.append(fd)
        real_close(fd)

    def boom_chmod(_path, _mode):
        raise OSError("chmod denied")

    monkeypatch.setattr(module.os, "chmod", boom_chmod)
    monkeypatch.setattr(module.os, "close", tracking_close)
    target = tmp_path / "out.json"
    with pytest.raises(module.SonarReportError, match="could not write"):
        module.write_text_atomically(target, "{}\n", purpose="test dump")
    assert closed
    assert not target.exists()
    assert not list(tmp_path.glob(".out.json.*.tmp"))


def test_main_rejects_bad_output_before_writing_dump(monkeypatch, tmp_path):
    module = _load_module()
    (tmp_path / ".env").write_text("SONAR_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "report_local_sonarqube_issues.py",
            "--output",
            "outside.md",
        ],
    )
    report = _sample_report(module)
    archive_calls: list[object] = []
    monkeypatch.setattr(module, "get_server_status", lambda _host: "UP")
    monkeypatch.setattr(module, "collect_reported_findings", lambda *_args: report)
    monkeypatch.setattr(module, "current_git_head", lambda _root: "abc123")
    monkeypatch.setattr(
        module,
        "archive_findings_json",
        lambda *_args, **_kwargs: archive_calls.append(True) or (tmp_path, tmp_path),
    )

    assert module.main() == 2
    assert archive_calls == []
    assert not (tmp_path / "tmp" / "sonarqube-findings").exists()
