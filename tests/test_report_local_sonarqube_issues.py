from __future__ import annotations

import importlib.util
import json
import sys
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

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


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


def test_fetch_issues_uses_component_filter_and_keeps_token_out_of_url(monkeypatch):
    module = _load_module()
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(_page([_issue()], total=1, page=1))

    monkeypatch.setattr(module, "urlopen", fake_urlopen)

    issues = module.fetch_issues(
        "http://localhost:9000", "test-token", "dicom-viewer-v3", {"severities": "BLOCKER"}
    )

    assert len(issues) == 1
    parsed = parse_qs(urlparse(requests[0][0].full_url).query)
    assert parsed["componentKeys"] == ["dicom-viewer-v3"]
    assert parsed["severities"] == ["BLOCKER"]
    assert "projectKeys" not in parsed
    assert "test-token" not in requests[0][0].full_url
    assert requests[0][0].get_header("Authorization") is not None


def test_fetch_issues_collects_all_pages(monkeypatch):
    module = _load_module()

    def fake_urlopen(request, timeout):
        assert timeout == 10.0
        page = int(parse_qs(urlparse(request.full_url).query)["p"][0])
        if page == 1:
            return _Response(_page([_issue(line=12)], total=2, page=1))
        return _Response(_page([_issue(line=24)], total=2, page=2))

    monkeypatch.setattr(module, "urlopen", fake_urlopen)

    issues = module.fetch_issues(
        "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
    )

    assert [issue.line for issue in issues] == [12, 24]


def test_fetch_issues_rejects_foreign_component(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "urlopen",
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
    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: _Response({"issues": []}))

    with pytest.raises(module.SonarReportError, match="incomplete issue-search payload"):
        module.fetch_issues(
            "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
        )

    monkeypatch.setattr(module, "urlopen", lambda *_args, **_kwargs: _Response(_page([], total=1, page=1)))
    with pytest.raises(module.SonarReportError, match="pagination was incomplete"):
        module.fetch_issues(
            "http://localhost:9000", "token", "dicom-viewer-v3", {"severities": "BLOCKER"}
        )


def test_collect_reported_findings_queries_all_policy_classes(monkeypatch):
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
        {"severities": "CRITICAL", "types": "BUG,VULNERABILITY"},
        {"severities": "MAJOR"},
    ]


def test_markdown_report_is_token_free_and_output_stays_in_tmp(tmp_path):
    module = _load_module()
    report = module.SonarReport(
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

    markdown = module.render_markdown_report(report)
    assert "test-token" not in markdown
    output_path = module.resolve_output_path(tmp_path, Path("tmp/report.md"))
    module.write_markdown_report(output_path, report)
    assert output_path.read_text(encoding="utf-8") == markdown

    with pytest.raises(module.SonarReportError, match="must stay below"):
        module.resolve_output_path(tmp_path, Path("report.md"))
