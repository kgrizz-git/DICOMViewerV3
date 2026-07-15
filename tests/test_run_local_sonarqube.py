from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_local_sonarqube.py"
    spec = importlib.util.spec_from_file_location("run_local_sonarqube", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_docker_host_url_rewrites_only_localhost():
    module = _load_module()

    assert module.docker_host_url("http://localhost:9000") == "http://host.docker.internal:9000"
    assert module.docker_host_url("http://127.0.0.1:9000") == "http://host.docker.internal:9000"
    assert module.docker_host_url("https://sonarqube.example.test") == "https://sonarqube.example.test"
    assert (
        module.docker_host_url("http://localhost:9000", "http://sonarqube:9000")
        == "http://sonarqube:9000"
    )


def test_docker_command_keeps_token_out_of_arguments(tmp_path):
    module = _load_module()
    command = module.build_scanner_command(
        tmp_path,
        mode="docker",
        project_key="test-project",
        include_coverage=True,
    )

    assert command[:3] == ["docker", "run", "--rm"]
    assert "SONAR_TOKEN" in command
    assert not any("secret-token" in part for part in command)
    assert "-Dproject.settings=tools/sonarqube/sonar-project.properties" in command
    assert "-Dsonar.working.directory=/tmp/sonar-work" in command
    assert "-Dsonar.python.coverage.reportPaths=.sonar-local/coverage.xml" in command
    assert any("dst=/usr/src,readonly" in part for part in command)


def test_last_submission_round_trip(tmp_path):
    module = _load_module()

    path = module.write_last_submission(
        tmp_path,
        host_url="http://localhost:9000",
        project_key="dicom-viewer-v3",
        scanner="docker",
        included_coverage=False,
    )

    assert path == tmp_path / ".sonar-local" / "last-analysis.json"
    record = module.read_last_submission(tmp_path)
    assert record is not None
    assert record["project_key"] == "dicom-viewer-v3"
    assert record["scanner"] == "docker"
    assert record["dashboard_url"] == "http://localhost:9000/dashboard?id=dicom-viewer-v3"


def test_main_requires_token_before_contacting_server(monkeypatch, tmp_path, capsys):
    module = _load_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_local_sonarqube.py", "--scanner", "local"])
    monkeypatch.setattr(
        module,
        "get_server_status",
        lambda *_args: (_ for _ in ()).throw(AssertionError("server should not be contacted")),
    )

    assert module.main() == 2
    assert "SONAR_TOKEN is not set" in capsys.readouterr().err


def test_main_records_only_a_successful_submission(monkeypatch, tmp_path):
    module = _load_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("SONAR_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", ["run_local_sonarqube.py", "--scanner", "local", "--skip-server-check"])
    calls: list[tuple[list[str], dict]] = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main() == 0
    assert calls[0][0][0] == "sonar-scanner"
    assert calls[0][1]["env"]["SONAR_TOKEN"] == "test-token"
    assert "test-token" not in calls[0][0]
    record = module.read_last_submission(tmp_path)
    assert record is not None
    assert record["scanner"] == "local"


def test_main_preserves_last_submission_when_scanner_fails(monkeypatch, tmp_path):
    module = _load_module()
    module.write_last_submission(
        tmp_path,
        host_url="http://localhost:9000",
        project_key="previous-project",
        scanner="docker",
        included_coverage=True,
    )
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("SONAR_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", ["run_local_sonarqube.py", "--scanner", "local", "--skip-server-check"])
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 7),
    )

    assert module.main() == 7
    record = module.read_last_submission(tmp_path)
    assert record is not None
    assert record["project_key"] == "previous-project"
