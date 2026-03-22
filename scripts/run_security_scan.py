#!/usr/bin/env python3
"""Security Scanner - Run all security tools at once"""
import subprocess, sys, json, argparse, re, logging
from pathlib import Path
from typing import Dict, List, Tuple

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
        "./venv/Scripts/semgrep.exe",
        "./venv/bin/semgrep",
    )
    if not semgrep_path:
        print_fail("Semgrep executable not found in venv")
        return {"status": "fail", "reason": "missing_semgrep"}
    cmd = [semgrep_path, "--config=p/security-audit", "--config=p/owasp-top-ten", "src/"]
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

def check_detect_secrets(verbose=False):
    print_header("Running Detect-Secrets")
    detect_secrets_path = get_tool_path(
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
    except:
        print_warn("Could not parse detect-secrets output")
        return {"status": "unknown"}

def check_trufflehog(verbose=False):
    print_header("Running TruffleHog (Secrets)")
    trufflehog_path = get_tool_path(
        "./tools/security/trufflehog/trufflehog.exe",
        "./tools/security/trufflehog/trufflehog",
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
        print_ok("No verified or unverified secrets found by TruffleHog")
        return {"status": "pass"}

    if findings:
        print_warn(f"TruffleHog reported {len(findings)} potential secret findings")
        if verbose:
            print(json.dumps(findings[:5], indent=2))
        return {"status": "review", "findings": len(findings)}

    if returncode != 0:
        if err_output:
            print_fail(err_output.splitlines()[-1])
            return {"status": "fail", "reason": err_output.splitlines()[-1]}
        print_fail(f"TruffleHog exited with code {returncode}")
        return {"status": "fail", "reason": f"exit_code_{returncode}"}

    print_ok("No verified or unverified secrets found by TruffleHog")
    return {"status": "pass"}

def main():
    parser = argparse.ArgumentParser(description="Run security scanning tools")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--semgrep", action="store_true", help="Run only Semgrep")
    parser.add_argument("--secrets", action="store_true", help="Run only secrets detection")
    parser.add_argument("--trufflehog", action="store_true", help="Run only TruffleHog")
    parser.add_argument("--debug-flags", action="store_true", help="Check debug flags only")
    parser.add_argument("--quick", action="store_true", help="Quick checks (Semgrep + debug)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--report", action="store_true", help="JSON report")
    args = parser.parse_args()
    
    print_header("Security Scanner")
    results, failed = {}, []
    
    # Determine what to run
    run_all = args.all or not any([args.semgrep, args.secrets, args.trufflehog, args.debug_flags, args.quick])
    
    if args.quick:
        run_debug_flags = True
        run_semgrep = True
        run_detect_secrets_check = False
        run_trufflehog_check = False
    else:
        run_debug_flags = args.debug_flags or run_all
        run_semgrep = args.semgrep or run_all
        run_detect_secrets_check = args.secrets or run_all
        run_trufflehog_check = args.trufflehog or args.secrets or run_all
    
    if run_debug_flags:
        r = check_debug_flags()
        results["debug_flags"] = r
        if r.get("status") == "fail":
            failed.append("debug_flags")
    
    if run_semgrep:
        r = check_semgrep(args.verbose)
        results["semgrep"] = r
        if r.get("status") == "fail":
            failed.append("semgrep")
    
    if run_detect_secrets_check:
        r = check_detect_secrets(args.verbose)
        results["detect_secrets"] = r
        if r.get("status") == "fail":
            failed.append("detect_secrets")

    if run_trufflehog_check:
        r = check_trufflehog(args.verbose)
        results["trufflehog"] = r
        if r.get("status") == "fail":
            failed.append("trufflehog")
    
    # Summary
    print_header("Summary")
    if args.report:
        print(json.dumps(results, indent=2))
    else:
        passed = sum(1 for r in results.values() if r.get("status") == "pass")
        print(f"Checks: {len(results)}, Passed: {passed}, Failed: {len(failed)}")
        if failed:
            print_fail(f"Failed: {', '.join(failed)}")
        else:
            print_ok("All checks passed!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warn("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print_fail(f"Error: {e}")
        sys.exit(1)
