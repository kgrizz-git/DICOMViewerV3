#!/usr/bin/env python3
"""Security Scanner - Run security tools alone or combined.

Supports a **--pre-commit** mode for fast git hooks: debug-flag check plus
Yelp detect-secrets on **staged** files only (size-capped and batched for
Windows command-line limits). Use **--all** for Semgrep, full-tree secrets,
TruffleHog, and pip-audit (as used by pre-push).
"""
import argparse
import json
import logging
import re
import subprocess
import sys
from functools import partial
from pathlib import Path
from shutil import which
from typing import Any

try:
    from scripts.privacy_console import print_redacted
except ModuleNotFoundError:
    from privacy_console import print_redacted

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_ok(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_fail(text):
    print(f"{Colors.RED}[FAIL] {text}{Colors.END}")

def print_warn(text):
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")

def get_tool_path(*candidates):
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    for candidate in candidates:
        resolved = which(Path(candidate).name)
        if resolved:
            return resolved
    return None

def run_cmd(cmd, desc="", verbose=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        print_fail(f"Timeout: {desc}")
        return 1, "", "Timeout"
    except Exception as e:
        print_fail(f"Error: {e}")
        return 1, "", str(e)

def check_debug_flags():
    print_header("Checking Debug Flags")
    try:
        with open("src/utils/debug_flags.py") as f:
            content = f.read()
        bad_flags = re.findall(r'(DEBUG_\w+)\s*:\s*bool\s*=\s*True', content)
        if bad_flags:
            print_fail(f"Debug flags enabled: {', '.join(bad_flags)}")
            return {"status": "fail", "flags": bad_flags}
        else:
            print_ok("All DEBUG flags are False")
            return {"status": "pass"}
    except FileNotFoundError:
        print_warn("Cannot find debug_flags.py")
        return {"status": "unknown"}

def check_semgrep(verbose=False):
    print_header("Running Semgrep (SAST)")
    semgrep_path = get_tool_path(
        "./.venv/Scripts/semgrep.exe",
        "./.venv/bin/semgrep",
        "./venv/Scripts/semgrep.exe",
        "./venv/bin/semgrep",
    )
    if not semgrep_path:
        print_fail("Semgrep executable not found in venv")
        return {"status": "fail", "reason": "missing_semgrep"}
    cmd = [
        semgrep_path,
        "--metrics=off",
        "--config=p/security-audit",
        "--config=p/owasp-top-ten",
        "src/",
    ]
    if not verbose:
        cmd.append("--quiet")
    returncode, stdout, stderr = run_cmd(cmd, "Semgrep", verbose)
    if returncode == 0:
        print_ok("No security issues found")
        return {"status": "pass"}
    else:
        print_warn("Issues found by Semgrep")
        if stdout:
            print(stdout[:500])
        return {"status": "review"}

def git_repo_root() -> Path:
    """Absolute repository root (works regardless of current working directory)."""
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(r.stdout.strip())


def staged_paths_for_secret_scan(
    root: Path,
    *,
    max_file_bytes: int = 2_000_000,
) -> list[str]:
    """Paths of staged files (added/copied/modified) suitable for detect-secrets."""
    proc = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[str] = []
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        path = (root / rel).resolve()
        try:
            if path.is_file() and path.stat().st_size <= max_file_bytes:
                out.append(str(path))
        except OSError:
            continue
    return out


def _scan_secrets_chunk(
    detect_secrets_path: str, chunk: list[str], verbose: bool
) -> tuple[dict[str, Any], bool]:
    """Run detect-secrets on one batch of staged files.

    Returns (findings for this chunk, parse_error) so the caller can merge
    across chunks without nesting the parse/merge logic inside its own loop.
    """
    cmd = [detect_secrets_path, "scan", *chunk]
    returncode, stdout, stderr = run_cmd(cmd, "Detect-secrets (staged)", verbose)
    if returncode != 0:
        print_warn(f"detect-secrets exited {returncode} on staged batch")
        if stderr:
            print(stderr[:500])
    try:
        batch = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        print_warn("Could not parse detect-secrets output for a staged batch")
        return {}, True
    chunk_findings: dict[str, Any] = {}
    for fp, items in batch.get("results", {}).items():
        chunk_findings[fp] = items if isinstance(items, list) else [items]
    return chunk_findings, False


def check_detect_secrets_staged(verbose=False):
    """Fast secret scan for git hooks: only staged files (not the whole tree)."""
    print_header("Running Detect-Secrets (staged files only)")
    detect_secrets_path = get_tool_path(
        "./.venv/Scripts/detect-secrets.exe",
        "./.venv/bin/detect-secrets",
        "./venv/Scripts/detect-secrets.exe",
        "./venv/bin/detect-secrets",
    )
    if not detect_secrets_path:
        print_fail("detect-secrets executable not found in venv")
        return {"status": "fail", "reason": "missing_detect_secrets"}

    root = git_repo_root()
    paths = staged_paths_for_secret_scan(root)
    if not paths:
        print_ok("No staged files to scan")
        return {"status": "pass", "skipped": True}

    merged: dict[str, Any] = {}
    chunk_size = 40
    parse_error = False
    for i in range(0, len(paths), chunk_size):
        chunk = paths[i : i + chunk_size]
        chunk_findings, chunk_parse_error = _scan_secrets_chunk(detect_secrets_path, chunk, verbose)
        for fp, items in chunk_findings.items():
            merged.setdefault(fp, []).extend(items)
        parse_error = parse_error or chunk_parse_error
    if parse_error:
        return {"status": "unknown"}

    if not merged:
        print_ok("No secrets detected in staged files")
        return {"status": "pass"}

    count = sum(len(v) for v in merged.values())
    print_warn(f"Potential secrets: {count} patterns in {len(merged)} staged files")
    return {"status": "review", "staged_files_scanned": len(paths)}


def check_detect_secrets(verbose=False):
    print_header("Running Detect-Secrets")
    detect_secrets_path = get_tool_path(
        "./.venv/Scripts/detect-secrets.exe",
        "./.venv/bin/detect-secrets",
        "./venv/Scripts/detect-secrets.exe",
        "./venv/bin/detect-secrets",
    )
    if not detect_secrets_path:
        print_fail("detect-secrets executable not found in venv")
        return {"status": "fail", "reason": "missing_detect_secrets"}
    cmd = [detect_secrets_path, "scan", "src/"]
    returncode, stdout, stderr = run_cmd(cmd, "Detect-secrets", verbose)
    try:
        results = json.loads(stdout) if stdout else {}
        findings = results.get("results", {})
        if not findings:
            print_ok("No secrets detected")
            return {"status": "pass"}
        else:
            count = sum(len(v) for v in findings.values())
            print_warn(f"Potential secrets: {count} patterns in {len(findings)} files")
            return {"status": "review"}
    except json.JSONDecodeError:
        print_warn("Could not parse detect-secrets output")
        return {"status": "unknown"}

def check_trufflehog(verbose=False):
    print_header("Running TruffleHog (Secrets)")
    trufflehog_path = get_tool_path(
        "C:/tools/trufflehog-v3/trufflehog.exe",
        "./tools/trufflehog-v3/trufflehog.exe",
        "./tools/trufflehog-v3/trufflehog",
        "./tools/security/trufflehog/trufflehog.exe",
        "./tools/security/trufflehog/trufflehog",
        "./.venv/Scripts/trufflehog.exe",
        "./.venv/bin/trufflehog",
        "./venv/Scripts/trufflehog.exe",
        "./venv/bin/trufflehog",
    )
    if not trufflehog_path:
        print_fail("TruffleHog executable not found")
        return {"status": "fail", "reason": "missing_trufflehog"}

    scan_targets = [
        str(path)
        for path in [
            Path("src"),
            Path("tests"),
            Path("scripts"),
            Path("requirements.txt"),
            Path("requirements-build.txt"),
            Path("run.py"),
            Path("pytest.ini"),
            Path(".github"),
        ]
        if path.exists()
    ]

    cmd = [
        trufflehog_path,
        "filesystem",
        *scan_targets,
        "--no-update",
        "--no-verification",
        "--json",
        "--fail-on-scan-errors",
    ]

    returncode, stdout, stderr = run_cmd(cmd, "TruffleHog", verbose)
    output = stdout.strip()
    err_output = stderr.strip()

    findings = []
    if output:
        for line in output.splitlines():
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if returncode == 0 and not findings:
        print_ok("No potential secrets found by offline TruffleHog scan")
        return {"status": "pass"}

    if findings:
        print_warn(f"TruffleHog reported {len(findings)} potential secret findings")
        if verbose:
            # Report detector/location only; findings' Raw/RawV2 fields contain the
            # actual matched secret text and must never be printed to logs/console.
            for f in findings[:5]:
                detector = f.get("DetectorName", "unknown")
                file_path = f.get("SourceMetadata", {}).get("Data", {}).get("Filesystem", {}).get("file", "unknown")
                print_redacted(f"  - {detector} in {file_path}")
        return {"status": "review", "findings": len(findings)}

    if returncode != 0:
        if err_output:
            print_fail(err_output.splitlines()[-1])
            return {"status": "fail", "reason": err_output.splitlines()[-1]}
        print_fail(f"TruffleHog exited with code {returncode}")
        return {"status": "fail", "reason": f"exit_code_{returncode}"}

    print_ok("No potential secrets found by offline TruffleHog scan")
    return {"status": "pass"}

def check_pip_audit(verbose=False):
    print_header("Running pip-audit (Dependency CVEs)")
    cmd = [sys.executable, "-m", "pip_audit", "-r", "requirements.txt", "--format", "json"]
    returncode, stdout, stderr = run_cmd(cmd, "pip-audit", verbose)

    # pip-audit exits non-zero when vulnerabilities are found, but JSON output is still useful.
    output = (stdout or "").strip()
    if not output:
        if returncode == 0:
            print_ok("No dependency vulnerabilities found")
            return {"status": "pass"}
        print_fail("pip-audit produced no output")
        return {"status": "fail", "reason": "no_output"}

    try:
        report = json.loads(output)
    except json.JSONDecodeError:
        print_warn("Could not parse pip-audit JSON output")
        return {"status": "unknown"}

    deps = report.get("dependencies", [])
    vuln_count = sum(len(dep.get("vulns", [])) for dep in deps)

    if vuln_count == 0:
        print_ok("No dependency vulnerabilities found")
        return {"status": "pass"}

    print_warn(f"pip-audit reported {vuln_count} vulnerabilities across requirements")
    if verbose:
        print(json.dumps(report, indent=2)[:2000])
    return {"status": "review", "vulnerabilities": vuln_count}

def _parse_args():
    parser = argparse.ArgumentParser(description="Run security scanning tools")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--semgrep", action="store_true", help="Run only Semgrep")
    parser.add_argument("--secrets", action="store_true", help="Run only secrets detection")
    parser.add_argument("--trufflehog", action="store_true", help="Run only TruffleHog")
    parser.add_argument("--debug-flags", action="store_true", help="Check debug flags only")
    parser.add_argument("--deps", action="store_true", help="Run dependency audit with pip-audit")
    parser.add_argument("--quick", action="store_true", help="Quick checks (Semgrep + debug)")
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        dest="pre_commit",
        help="Hook mode: debug flags + detect-secrets on staged files only (fast)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--report", action="store_true", help="JSON report")
    return parser.parse_args()


def _select_checks_to_run(args) -> dict[str, bool]:
    """Map each check name to whether it should run, given the CLI mode."""
    run_all = args.all or not any(
        [
            args.semgrep,
            args.secrets,
            args.trufflehog,
            args.debug_flags,
            args.deps,
            args.quick,
            args.pre_commit,
        ]
    )

    if args.pre_commit:
        return {
            "debug_flags": True,
            "semgrep": False,
            "detect_secrets": False,
            "detect_secrets_staged": True,
            "trufflehog": False,
            "pip_audit": False,
        }
    if args.quick:
        return {
            "debug_flags": True,
            "semgrep": True,
            "detect_secrets": False,
            "detect_secrets_staged": False,
            "trufflehog": False,
            "pip_audit": False,
        }
    return {
        "debug_flags": args.debug_flags or run_all,
        "semgrep": args.semgrep or run_all,
        "detect_secrets": args.secrets or run_all,
        "detect_secrets_staged": False,
        "trufflehog": args.trufflehog or args.secrets or run_all,
        "pip_audit": args.deps or run_all,
    }


def _run_selected_checks(checks: dict[str, bool], verbose: bool) -> tuple[dict[str, Any], list[str]]:
    checkers = {
        "debug_flags": check_debug_flags,
        "semgrep": partial(check_semgrep, verbose),
        "detect_secrets": partial(check_detect_secrets, verbose),
        "detect_secrets_staged": partial(check_detect_secrets_staged, verbose),
        "trufflehog": partial(check_trufflehog, verbose),
        "pip_audit": partial(check_pip_audit, verbose),
    }
    results: dict[str, Any] = {}
    failed: list[str] = []
    for name, should_run in checks.items():
        if not should_run:
            continue
        checker = checkers[name]
        if not callable(checker):
            raise TypeError(f"Expected a callable for checker '{name}', got {type(checker).__name__}")
        r = checker()
        if not isinstance(r, dict):
            try:
                r = dict(r)
            except Exception as exc:
                raise TypeError(f"Expected result from checker '{name}' to be dict-like, got {type(r).__name__}") from exc
        results[name] = r
        if r.get("status") == "fail":
            failed.append(name)
    return results, failed


def _print_summary(results: dict[str, Any], failed: list[str], as_json: bool) -> None:
    print_header("Summary")
    if as_json:
        print(json.dumps(results, indent=2))
        return
    passed = sum(1 for r in results.values() if r.get("status") == "pass")
    print(f"Checks: {len(results)}, Passed: {passed}, Failed: {len(failed)}")
    if failed:
        print_fail(f"Failed: {', '.join(failed)}")
    else:
        print_ok("All checks passed!")


def main():
    args = _parse_args()
    print_header("Security Scanner")
    checks = _select_checks_to_run(args)
    results, failed = _run_selected_checks(checks, args.verbose)
    _print_summary(results, failed, args.report)
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warn("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print_fail(f"Error: {e}")
        sys.exit(1)
