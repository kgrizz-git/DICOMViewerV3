"""Tests for scripts/compile_requirements.py (no real uv or network)."""

from __future__ import annotations

import importlib.util
import re
import shutil
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
    assert cr.LOCK_STEMS == ("requirements", "requirements-dev", "requirements-build")
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


def test_compile_all_runs_three_commands_in_order(tmp_path: Path) -> None:
    with mock.patch.object(cr.subprocess, "run", return_value=_completed()) as run:
        assert cr.compile_all(tmp_path) == 0
    commands = [call.args[0] for call in run.call_args_list]
    assert [c[3] for c in commands] == [
        "requirements.in",
        "requirements-dev.in",
        "requirements-build.in",
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
def test_launchers_read_zensical_pin_from_lock(name: str) -> None:
    text = _launcher_text(name)
    assert "zensical==" in text
    assert "requirements-dev.txt" in text
    assert "requirements-dev.in" not in text


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
    assert setup.index("(3, 12)") < setup.index("-m venv")
    install = text[text.index(":INSTALL_REQUIREMENTS\n") :]
    assert install.index("call :CHECK_VENV_PYTHON") < install.index("-m pip install")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_launch_command_zensical_extraction_matches_lock() -> None:
    text = _launcher_text("launch.command")
    line = next(ln for ln in text.splitlines() if "grep -E '^zensical=='" in ln)
    expr = line.split('pin="$(', 1)[1].rsplit(')"', 1)[0]
    expr = expr.replace('"$SCRIPT_DIR/requirements-dev.txt"', "requirements-dev.txt")
    out = subprocess.run(
        ["bash", "-c", expr], cwd=_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert re.fullmatch(r"zensical==\d+(\.\d+)*", out)
    lock = (_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert f"\n{out} \\\n" in lock
