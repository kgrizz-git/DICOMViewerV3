"""Contract tests for local-only privacy tool wrappers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.privacy_tools import common, dicom, hounddog, media, phiscan
from scripts.privacy_tools.common import CommandResult, ToolStatus


def _write_report_from_command(command: list[str], payload: object) -> None:
    flag = "--output" if command[0] == "dicom-tool" else "--report-path"
    report_path = Path(command[command.index(flag) + 1])
    report_path.write_text(json.dumps(payload), encoding="utf-8")
    report_path.chmod(0o600)


def test_missing_tool_is_skip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dicom, "resolve_executable", lambda _name: None)

    result = dicom.run_dicom_review(tmp_path / "fixture.dcm")

    assert result.status is ToolStatus.SKIP
    assert result.reason == "tool-missing"


@pytest.mark.parametrize(
    ("payload", "returncode", "expected"),
    [
        ({"tag_findings": [], "pixel_findings": []}, 0, ToolStatus.CLEAN),
        (
            {"tag_findings": [{"value": "MATCHED-CANARY"}], "pixel_findings": [{}]},
            1,
            ToolStatus.FINDINGS,
        ),
    ],
)
def test_dicom_clean_and_findings_are_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: object,
    returncode: int,
    expected: ToolStatus,
) -> None:
    monkeypatch.setattr(dicom, "resolve_executable", lambda _name: "dicom-tool")

    def fake_run(command: list[str], **_kwargs: object) -> CommandResult:
        _write_report_from_command(command, payload)
        return CommandResult(returncode, "MATCHED-CANARY", "MATCHED-CANARY")

    monkeypatch.setattr(dicom, "run_command", fake_run)
    result = dicom.run_dicom_review(tmp_path / "fixture.dcm")

    assert result.status is expected
    assert "MATCHED-CANARY" not in result.summary()
    assert "MATCHED-CANARY" not in repr(result)


def test_malformed_report_is_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(dicom, "resolve_executable", lambda _name: "dicom-tool")

    def fake_run(command: list[str], **_kwargs: object) -> CommandResult:
        report_path = Path(command[command.index("--output") + 1])
        report_path.write_text("not-json MATCHED-CANARY", encoding="utf-8")
        report_path.chmod(0o600)
        return CommandResult(0, "", "")

    monkeypatch.setattr(dicom, "run_command", fake_run)

    result = dicom.run_dicom_review(tmp_path / "fixture.dcm")

    assert result.status is ToolStatus.ERROR
    assert result.reason == "report-invalid"
    assert "MATCHED-CANARY" not in result.summary()


def test_timeout_is_error_without_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(dicom, "resolve_executable", lambda _name: "dicom-tool")
    monkeypatch.setattr(
        dicom,
        "run_command",
        lambda *_args, **_kwargs: CommandResult(
            124, "MATCHED-CANARY", "", timed_out=True
        ),
    )

    result = dicom.run_dicom_review(tmp_path / "fixture.dcm")

    assert result.status is ToolStatus.ERROR
    assert result.reason == "timeout"
    assert "MATCHED-CANARY" not in result.summary()


def test_private_report_rejects_group_permissions(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text("{}", encoding="utf-8")
    report.chmod(0o640)

    with pytest.raises(PermissionError, match="report_not_private"):
        common.load_private_json(report)


def test_protected_workspace_cleans_up_on_error() -> None:
    workspace: Path | None = None
    with (
        pytest.raises(RuntimeError),
        common.protected_workspace("dvv-cleanup-test-") as created,
    ):
        workspace = created
        (created / "raw.txt").write_text("MATCHED-CANARY", encoding="utf-8")
        raise RuntimeError

    assert workspace is not None
    assert not workspace.exists()


def test_hounddog_enforces_local_no_git_and_redacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {"data_elements": ["medical-record-number"], "data_sinks": ["logs"]}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(hounddog, "resolve_executable", lambda _name: "hounddog-tool")
    observed: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> CommandResult:
        observed.append(command)
        if "--version" in command:
            return CommandResult(0, "3.3.0", "")
        report = Path(command[command.index("--output-path") + 1])
        report.write_text(
            json.dumps({"dataflows": [{"content": "MATCHED-CANARY"}]}), encoding="utf-8"
        )
        report.chmod(0o600)
        return CommandResult(0, "MATCHED-CANARY", "")

    monkeypatch.setattr(hounddog, "run_command", fake_run)
    result = hounddog.run_hounddog(tmp_path, config_path=config)

    assert result.status is ToolStatus.FINDINGS
    assert "--no-git" in observed[-1]
    assert "--include-data-element" in observed[-1]
    assert "--include-data-sink" in observed[-1]
    assert "MATCHED-CANARY" not in result.summary()


def test_phiscan_uses_staged_materialization_and_private_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(phiscan, "resolve_executable", lambda _name: "phi-tool")

    def fake_stage(_root: Path, target: Path) -> int:
        item = target / "item-0000.json"
        item.write_text("MATCHED-CANARY", encoding="utf-8")
        item.chmod(0o600)
        return 1

    def fake_run(command: list[str], **_kwargs: object) -> CommandResult:
        report = Path(command[command.index("--report-path") + 1])
        report.write_text(
            json.dumps(
                {"findings": [{"entity_type": "MRN", "value": "MATCHED-CANARY"}]}
            ),
            encoding="utf-8",
        )
        report.chmod(0o600)
        assert "--quiet" in command
        assert "--no-cache" in command
        return CommandResult(1, "MATCHED-CANARY", "")

    monkeypatch.setattr(phiscan, "staged_data_blobs", fake_stage)
    monkeypatch.setattr(phiscan, "run_command", fake_run)

    result = phiscan.run_phiscan(tmp_path)

    assert result.status is ToolStatus.FINDINGS
    assert result.scanned_count == 1
    assert "MATCHED-CANARY" not in result.summary()


def test_media_metadata_and_ocr_output_are_counted_not_recorded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(media, "resolve_executable", lambda name: name)

    def fake_run(command: list[str], **_kwargs: object) -> CommandResult:
        if command[0] == "exiftool":
            return CommandResult(0, '[{"Artist":"MATCHED-CANARY"}]', "")
        return CommandResult(
            0, "header\n1\t1\t1\t1\t1\t1\t1\t1\t90\tMATCHED-CANARY", ""
        )

    monkeypatch.setattr(media, "run_command", fake_run)
    result = media.run_media_review(tmp_path / "image.png")

    assert result.status is ToolStatus.FINDINGS
    assert result.categories["embedded-metadata"] == 1
    assert result.categories["ocr-text"] == 1
    assert "MATCHED-CANARY" not in result.summary()
