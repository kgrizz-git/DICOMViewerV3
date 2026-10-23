"""Tests for scripts/compile_requirements.py (no real uv or network)."""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path
from unittest import mock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "compile_requirements", _ROOT / "scripts" / "compile_requirements.py"
)
assert _spec is not None
assert _spec.loader is not None
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)


def _completed(code: int = 0, out: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=out, stderr="")


def test_lock_file_set_and_order() -> None:
    assert cr.LOCK_STEMS == (
        "requirements",
        "requirements-dev",
        "requirements-build",
        "requirements-docs",
    )
    assert cr.LOCK_STEMS[0] == "requirements"  # the app lock constrains the others
    assert cr.input_name("requirements-dev") == "requirements-dev.in"
    assert cr.output_name("requirements-dev") == "requirements-dev.txt"


def test_app_command_is_universal_hashed_and_unconstrained() -> None:
    cmd = cr.compile_command("requirements")
    assert cmd[:4] == ["uv", "pip", "compile", "requirements.in"]
    assert "--universal" in cmd
    assert "--generate-hashes" in cmd
    assert "--strip-extras" in cmd
    assert cmd[cmd.index("--python-version") + 1] == "3.12"
    assert "-c" not in cmd
    assert cmd[-2:] == ["-o", "requirements.txt"]


@pytest.mark.parametrize("stem", ["requirements-dev", "requirements-build"])
def test_dependent_commands_use_app_lock_as_constraint(stem: str) -> None:
    cmd = cr.compile_command(stem)
    assert cmd[cmd.index("-c") + 1] == "requirements.txt"
    assert cmd[3] == f"{stem}.in"
    assert cmd[-1] == f"{stem}.txt"


def test_docs_command_is_constrained_by_app_and_dev_locks() -> None:
    cmd = cr.compile_command("requirements-docs")
    constraints = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-c"]
    assert constraints == ["requirements.txt", "requirements-dev.txt"]
    assert cmd[3] == "requirements-docs.in"
    assert cmd[-1] == "requirements-docs.txt"


def test_command_uses_given_uv_executable() -> None:
    assert cr.compile_command("requirements", uv="/x/uv")[0] == "/x/uv"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("uv 0.13.4 (46b84fd0b 2026-10-03 aarch64-apple-darwin)\n", "0.13.4"),
        ("uv 0.12.10", "0.12.10"),
        ("pip 25.0", None),
        ("", None),
    ],
)
def test_parse_uv_version(text: str, expected: str | None) -> None:
    assert cr.parse_uv_version(text) == expected


def test_uv_version_ok_requires_exact_pin() -> None:
    assert cr.uv_version_ok(f"uv {cr.UV_VERSION} (x)")
    assert not cr.uv_version_ok("uv 0.12.10 (x)")
    assert not cr.uv_version_ok("garbage")


def test_installed_uv_version_handles_missing_binary() -> None:
    with mock.patch.object(cr.subprocess, "run", side_effect=FileNotFoundError):
        assert cr.installed_uv_version("uv") is None


def test_installed_uv_version_parses_output() -> None:
    with mock.patch.object(
        cr.subprocess, "run", return_value=_completed(0, "uv 0.13.4 (x)")
    ):
        assert cr.installed_uv_version("uv") == "0.13.4"


def test_compile_all_runs_every_command_in_order(tmp_path: Path) -> None:
    with mock.patch.object(cr.subprocess, "run", return_value=_completed()) as run:
        assert cr.compile_all(tmp_path) == 0
    commands = [call.args[0] for call in run.call_args_list]
    assert [c[3] for c in commands] == [
        "requirements.in",
        "requirements-dev.in",
        "requirements-build.in",
        "requirements-docs.in",
    ]
    assert all(call.kwargs["cwd"] == tmp_path for call in run.call_args_list)


def test_compile_all_stops_at_first_failure(tmp_path: Path) -> None:
    with mock.patch.object(cr.subprocess, "run", return_value=_completed(3)) as run:
        assert cr.compile_all(tmp_path) == 3
    assert run.call_count == 1


def test_compile_all_propagates_negative_exit_code(tmp_path: Path) -> None:
    with mock.patch.object(cr.subprocess, "run", return_value=_completed(-9)):
        assert cr.compile_all(tmp_path) == -9


def test_upgrade_removes_old_locks_only_when_requested(tmp_path: Path) -> None:
    for stem in cr.LOCK_STEMS:
        (tmp_path / f"{stem}.txt").write_text("old\n", encoding="utf-8")
    with mock.patch.object(cr.subprocess, "run", return_value=_completed()):
        cr.compile_all(tmp_path)
    assert all((tmp_path / f"{s}.txt").exists() for s in cr.LOCK_STEMS)
    with mock.patch.object(cr.subprocess, "run", return_value=_completed()):
        cr.compile_all(tmp_path, upgrade=True)
    assert not any((tmp_path / f"{s}.txt").exists() for s in cr.LOCK_STEMS)


def test_main_rejects_wrong_uv_version(capsys: pytest.CaptureFixture[str]) -> None:
    with mock.patch.object(cr, "installed_uv_version", return_value="0.1.0"):
        assert cr.main([]) == 1
    assert cr.UV_VERSION in capsys.readouterr().err


def test_main_rejects_missing_uv() -> None:
    with mock.patch.object(cr, "installed_uv_version", return_value=None):
        assert cr.main([]) == 1


def test_main_passes_upgrade_flag() -> None:
    with (
        mock.patch.object(cr, "installed_uv_version", return_value=cr.UV_VERSION),
        mock.patch.object(cr, "compile_all", return_value=0) as compile_all,
    ):
        assert cr.main(["--upgrade"]) == 0
    assert compile_all.call_args.kwargs["upgrade"] is True


# --- repository consistency -------------------------------------------------


def test_uv_pin_matches_ci_and_dev_requirements() -> None:
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pins = set(re.findall(r"uv==(\d+\.\d+\.\d+)", ci))
    assert pins == {cr.UV_VERSION}
    dev = (_ROOT / "requirements-dev.in").read_text(encoding="utf-8")
    assert re.search(rf"^uv=={re.escape(cr.UV_VERSION)}\b", dev, re.MULTILINE)


def test_every_lock_has_input_and_uv_header_with_expected_command() -> None:
    for stem in cr.LOCK_STEMS:
        assert (_ROOT / f"{stem}.in").is_file()
        lines = (_ROOT / f"{stem}.txt").read_text(encoding="utf-8").splitlines()
        assert (
            lines[0] == "# This file was autogenerated by uv via the following command:"
        )
        assert lines[1] == "#    " + " ".join(cr.compile_command(stem))


def test_dev_input_includes_app_input() -> None:
    dev = (_ROOT / "requirements-dev.in").read_text(encoding="utf-8")
    assert re.search(r"^-r requirements\.in$", dev, re.MULTILINE)


def test_locks_are_hashed_and_universal() -> None:
    app = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "--hash=sha256:" in app
    # Markers for other platforms prove one lock serves win32, darwin and linux.
    assert re.search(r"^colorama==\S+ ; sys_platform == 'win32'", app, re.MULTILINE)
    build = (_ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "pefile==" in build
    assert "macholib==" in build


_LAUNCHERS = ("launch.bat", "launch.command")


def _launcher_text(name: str) -> str:
    return (_ROOT / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", _LAUNCHERS)
def test_launchers_install_app_lock_with_require_hashes(name: str) -> None:
    lines = [
        line
        for line in _launcher_text(name).splitlines()
        if "pip install" in line and "requirements.txt" in line
    ]
    assert lines
    for line in lines:
        assert "--require-hashes" in line


@pytest.mark.parametrize("name", _LAUNCHERS)
def test_launchers_install_docs_builder_from_hashed_lock(name: str) -> None:
    text = _launcher_text(name)
    assert "--require-hashes -r" in text
    assert "requirements-docs.txt" in text
    assert "zensical==" not in text
    assert "requirements-dev.in" not in text


@pytest.mark.parametrize("workflow", ["ci.yml", "build.yml"], ids=["ci", "build"])
def test_workflows_install_docs_tooling_from_hashed_lock(workflow: str) -> None:
    text = (_ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    assert "pip install --require-hashes -r requirements-docs.txt" in text
    assert "grep -E '^zensical==" not in text
    assert "grep -iE '^pyyaml==" not in text


def test_docs_input_holds_zensical_and_pyyaml_floors_matching_dev() -> None:
    docs = (_ROOT / "requirements-docs.in").read_text(encoding="utf-8")
    dev = (_ROOT / "requirements-dev.in").read_text(encoding="utf-8")
    for line in ("zensical>=0.0.68,<0.1", "PyYAML>=6.0.3"):
        assert re.search(rf"^{re.escape(line)}$", docs, re.MULTILINE)
        assert re.search(rf"^{re.escape(line)}$", dev, re.MULTILINE)


@pytest.mark.parametrize("name", _LAUNCHERS)
def test_launchers_gate_python_312(name: str) -> None:
    text = _launcher_text(name)
    assert "(3, 12)" in text
    assert "(3, 10)" not in text


def test_launch_command_gates_before_venv_and_pip() -> None:
    text = _launcher_text("launch.command")
    setup = text[text.index("setup_and_run() {") :]
    assert setup.index("require_python_312 python3") < setup.index("-m venv")
    install = text[text.index("install_requirements() {") :]
    assert install.index("require_python_312") < install.index("-m pip install")


def test_launch_bat_gates_before_venv_and_pip() -> None:
    text = _launcher_text("launch.bat")
    setup = text[text.index(":SETUP\n") :]
    assert setup.index("call :CHECK_SYSTEM_PYTHON") < setup.index("-m venv")
    install = text[text.index("\n:INSTALL_REQUIREMENTS\n") :]
    assert install.index("call :CHECK_VENV_PYTHON") < install.index("-m pip install")


def test_launch_command_gates_existing_venv_run_path() -> None:
    text = _launcher_text("launch.command")
    run = text[text.index("run_with_check() {") : text.index("delete_venv() {")]
    assert 'require_python_312 "$VENV_PY" existing' in run
    assert run.index('require_python_312 "$VENV_PY" existing') < run.index(
        "import pydicom, PySide6, numpy, PIL"
    )


def test_launch_bat_gates_existing_venv_run_path() -> None:
    text = _launcher_text("launch.bat")
    run = text[text.index("\n:RUN_PY_OK\n") : text.index("\n:RUN_ACTIVATED\n")]
    assert "call :CHECK_VENV_PYTHON" in run
    assert run.index("call :CHECK_VENV_PYTHON") < run.index(
        "import pydicom, PySide6, numpy, PIL"
    )


def test_docs_lock_pins_agree_with_dev_lock() -> None:
    pin = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+) ", re.MULTILINE)
    dev = {
        n.lower(): v
        for n, v in pin.findall(
            (_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        )
    }
    docs = {
        n.lower(): v
        for n, v in pin.findall(
            (_ROOT / "requirements-docs.txt").read_text(encoding="utf-8")
        )
    }
    assert "zensical" in docs
    assert "pyyaml" in docs
    assert {k: v for k, v in docs.items() if dev.get(k) != v} == {}


def test_launch_command_gates_system_python_path() -> None:
    text = _launcher_text("launch.command")
    run_sys = text[text.index("run_sys() {") : text.index("setup_and_run() {")]
    assert "require_python_312 python3" in run_sys
    assert run_sys.index("require_python_312 python3") < run_sys.index(
        'python3 "$SCRIPT_DIR/run.py"'
    )
    assert "3.12" in run_sys


def test_launch_bat_gates_system_python_path() -> None:
    text = _launcher_text("launch.bat")
    run_sys = text[text.index("\n:RUN_SYS\n") : text.index("\n:DELETE\n")]
    assert "call :CHECK_SYSTEM_PYTHON" in run_sys
    assert run_sys.index("call :CHECK_SYSTEM_PYTHON") < run_sys.index(
        'python "%ROOT%run.py"'
    )
    assert "3.12" in run_sys


def test_launch_bat_separates_missing_python_from_too_old() -> None:
    text = _launcher_text("launch.bat")
    check = text[
        text.index("\n:CHECK_SYSTEM_PYTHON\n") : text.index("\n:CHECK_VENV_PYTHON\n")
    ]
    assert "where python" in check
    assert "Python was not found on PATH" in check
    assert check.index("where python") < check.index("(3, 12)")
    assert check.index("Python was not found on PATH") < check.index(
        "needs Python 3.12"
    )


def _run_require_python_312(py: str, path: str) -> subprocess.CompletedProcess[str]:
    text = _launcher_text("launch.command")
    start = text.index("require_python_312() {")
    end = text.index("install_requirements() {")
    script = text[start:end] + f'\nrequire_python_312 "{py}"\n'
    return subprocess.run(
        ["/bin/bash", "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": path},
        check=False,
    )


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="bash not available")
def test_require_python_312_passes_for_current_interpreter() -> None:
    import sys

    result = _run_require_python_312(sys.executable, "/usr/bin:/bin")
    assert result.returncode == 0


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="bash not available")
def test_require_python_312_fails_for_old_interpreter(tmp_path: Path) -> None:
    fake = tmp_path / "pyold"
    fake.write_text(
        '#!/bin/sh\n[ "$1" = "-c" ] && case "$2" in *version_info*) exit 1;; esac\n'
        "echo 3.11.0\n"
    )
    fake.chmod(0o755)
    result = _run_require_python_312(str(fake), "/usr/bin:/bin")
    assert result.returncode == 1
    assert "needs Python 3.12 or newer" in result.stdout
    assert "was not found" not in result.stdout


@pytest.mark.skipif(not Path("/bin/bash").exists(), reason="bash not available")
def test_require_python_312_reports_missing_python3(tmp_path: Path) -> None:
    result = _run_require_python_312("python3", str(tmp_path))
    assert result.returncode == 1
    assert "Python was not found on PATH" in result.stdout
    assert "needs Python 3.12 or newer" not in result.stdout


_SELFTEST_VAR = "DICOMVIEWER_LAUNCHER_SELFTEST"


def _ci_launcher_job() -> str:
    text = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    start = text.index("  launcher-windows:")
    end = text.index("\n  # Dependabot alerts are never raised", start)
    return text[start:end]


def test_launch_bat_selftest_hook_dispatches_to_both_gates() -> None:
    text = _launcher_text("launch.bat")
    assert f"if defined {_SELFTEST_VAR} goto :SELFTEST" in text
    assert "call :CHECK_SYSTEM_PYTHON\nexit /b %errorlevel%" in text.replace(
        "\r\n", "\n"
    )
    assert "call :CHECK_VENV_PYTHON\nexit /b %errorlevel%" in text.replace("\r\n", "\n")
    # The hook must run before the interactive menu.
    assert text.index("goto :SELFTEST") < text.index(":MENU")


def test_launch_bat_selftest_hook_is_inert_unless_env_var_set() -> None:
    lines = _launcher_text("launch.bat").splitlines()
    uses = [ln for ln in lines if _SELFTEST_VAR in ln and not ln.startswith("rem ")]
    assert uses, "hook lines not found"
    allowed = (
        f"if defined {_SELFTEST_VAR} goto",
        f"if not defined {_SELFTEST_VAR} pause",
        f'if /i "%{_SELFTEST_VAR}%"==',
        f"echo ERROR: {_SELFTEST_VAR} must be",
    )
    for ln in uses:
        assert ln.strip().startswith(allowed), ln


def test_launch_bat_pause_skipped_only_by_selftest_in_gate_routines() -> None:
    text = _launcher_text("launch.bat").replace("\r\n", "\n")
    start = text.index("\n:CHECK_SYSTEM_PYTHON\n")
    end = text.index("\n:RUN\n", start)
    gates = text[start:end]
    assert "\n    pause\n" not in gates
    assert gates.count(f"if not defined {_SELFTEST_VAR} pause") == 3


def test_launch_bat_selftest_keeps_no_delayed_expansion() -> None:
    text = _launcher_text("launch.bat")
    assert "setlocal enabledelayedexpansion" not in text.lower()


def test_ci_launcher_windows_job_shape() -> None:
    job = _ci_launcher_job()
    assert "name: Launcher (Windows cmd)" in job
    assert "needs: [privacy-gates]" in job
    assert "runs-on: windows-latest" in job
    assert "continue-on-error: true" in job
    assert "timeout-minutes:" in job
    assert "contents: read" in job


@pytest.mark.parametrize(
    "marker",
    [
        "Scenario (a)",
        "Scenario (b)",
        "Scenario (c)",
        "Scenario (d)",
        "Scenario (e)",
        f"{_SELFTEST_VAR}=system",
        f"{_SELFTEST_VAR}=venv",
        "needs Python 3.12",
        "not found on PATH",
        "--require-hashes -r requirements-docs.txt",
    ],
)
def test_ci_launcher_windows_job_covers_scenario(marker: str) -> None:
    assert marker in _ci_launcher_job()


def test_ci_launcher_windows_job_actions_are_sha_pinned() -> None:
    uses = re.findall(r"uses: (\S+)", _ci_launcher_job())
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", ref), ref
