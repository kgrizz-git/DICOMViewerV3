# Developer setup and troubleshooting

**Last updated:** 2026-08-12

Use this page with [CONTRIBUTING.md](CONTRIBUTING.md) (hooks, CI, releases), [AGENTS.md](../AGENTS.md) (venv, module layout, agents), and [tests/README.md](../tests/README.md).

## Common issues

### Incomplete virtual environment (Windows launcher)

`launch.bat` and `launch.command` install and run through the venv interpreter directly (`…/python.exe -m pip` / `…/bin/python -m pip`) instead of relying on `activate` plus bare `pip`/`python`. On Windows setups with multiple Python installs (for example pyenv), the old pattern could leave an empty `venv` folder that looks valid but has no packages.

- **Symptom:** `launch.bat` → **Run** fails with missing `pydicom`, `PySide6`, `numpy`, or `PIL`, or the venv folder exists but `Scripts\python.exe` cannot import the app stack.
- **Fix:** Choose **Reinstall / update requirements** in the launcher menu, or delete the broken env folder and recreate it (`python -m venv .venv`, then `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`).
- **Prevention:** Always use the venv interpreter for installs (`python -m pip install -r requirements.txt` after activation, or let the launcher handle it).

### Compressed DICOM will not decode

The runtime decoder stack is defined in `requirements.txt`:

| Handler | Package | Transfer syntaxes |
|---------|---------|-------------------|
| GDCM | `python-gdcm==3.2.6` | JPEG Baseline (`.50`), Extended (`.51`), Lossless (`.57`/`.70`) |
| pylibjpeg + openjpeg | `pylibjpeg`, `pylibjpeg-openjpeg` | JPEG 2000 (`.90`/`.91`) |
| pylibjpeg RLE | `pylibjpeg-rle` | RLE Lossless (`.5`) |
| JPEG-LS | `pyjpegls` | JPEG-LS (`.80`/`.81`) |

`pylibjpeg-libjpeg` (GPL) is **not** part of the supported runtime. Do not install it to work around decode failures.

- **Symptom:** A file loads but shows no image, or appears in the failed-files list with a transfer-syntax message.
- **Check installed handlers:** from the project venv, `python -c "from core.decoder_capabilities import available_decoder_backends; print(available_decoder_backends('1.2.840.10008.1.2.4.50'))"` should list `GDCM` when classic JPEG support is present.
- **Regression tests:** `python -m pytest tests/test_synthetic_decoder_fixture.py tests/core/test_decoder_capabilities.py -v`
- **Frozen-build smoke:** after PyInstaller, run the executable against the committed synthetic fixtures (see [BUILDING_EXECUTABLES.md](info/BUILDING_EXECUTABLES.md) § Decoder fixture smoke).
- **Deeper context:** [DICOM_SUPPORT_ANALYSIS.md](info/DICOM_SUPPORT_ANALYSIS.md) §3 and [PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md](info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md).

### "Module not found" when running the app or tests

- Install dependencies: `pip install -r requirements.txt` (from project root, venv activated).
- Run from the **project root**, or use absolute paths to `src/main.py`.
- For tests, ensure `PYTHONPATH` includes `src` (see `tests/run_tests.py`).

### Wrong working directory

- **"No such file or directory"** for `src/main.py`: `cd` to the folder that contains `requirements.txt` and `src/`.

### Python version and native wheels (Windows)

- **Python 3.10+** is required for the full `requirements.txt` stack (including **pylinac**); on Windows **3.11 or 3.12** is recommended so packages like **pyjpegls** install from pre-built wheels.
- If **`pip install` fails building pyjpegls** with *Microsoft Visual C++ 14.0 or greater is required*, either switch the venv to **Python 3.11/3.12**, or install [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) with the C++ workload.

### Parallels / network home paths (Windows guests)

- A project clone on a local drive sometimes avoids venv or pip quirks seen with shared-folder paths.

## Optional contributor tooling

Security scanners and related CLI tools are **not** in `requirements.txt`. For parity with CI docs:

```bash
pip install -r requirements-dev.txt
```

Optional dependency audit tool:

```bash
python -m pip install pip-audit
```

TruffleHog v3 (Windows):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath
```

See [SECURITY_TOOLS_CLI_GUIDE.md](SECURITY_TOOLS_CLI_GUIDE.md).

Quick local run (PowerShell):

```powershell
.\scripts\scan-security.ps1 -All -Report
```

Install repo-managed security hooks (recommended, one-time per clone):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-local-git-hooks.ps1
```

macOS/Linux equivalent:

```bash
bash ./scripts/setup-hooks.sh
```

This sets `core.hooksPath` to `.githooks/`, so Git runs the `pre-commit`, `commit-msg`, and `pre-push` hooks directly from the
version-controlled directory. No file copying — edits to `.githooks/` take effect
immediately without re-running the installer.

**Line-count / complexity gate:** `pre-commit` runs
`scripts/git_hook_line_complexity.py --staged` before the PHI / privacy /
Gitleaks gates (so a ratcheted grandfather JSON is scanned in the same commit)
and before ruff. Thresholds: warn above
**600** lines, block above **750** lines, and block lizard cyclomatic complexity
(**CCN**) above **20**. Paths already over threshold are listed in
`scripts/line_complexity_grandfather.json` with their measured size/CCN: staying
at or below that baseline warns only; **growing past the recorded baseline
blocks** (regression). When a staged change **improves** a grandfathered
file/function, the hook **ratchets the cap down** (or removes the entry if it
falls under the block threshold) and `git add`s the JSON into the same commit
so the ceiling cannot climb back up later. Refresh the full baseline with
`python scripts/git_hook_line_complexity.py --all --generate-grandfather`
(requires `lizard` from `requirements-dev.txt`). Use `--all` (worktree) for
visibility; `--staged` reads the Git index (correct for the hook).

### Optional direnv setup

The tracked `.envrc` loads an ignored `.env` file and activates an existing
`.venv` or `venv`. It intentionally performs no package installation or network
access. It watches `requirements.txt` and `requirements-dev.txt` and prints a
short reminder when the active venv has not been explicitly synchronized.

```bash
cp .env.example .env
# Edit only .env and add the local SONAR_TOKEN.
direnv allow
python scripts/sync_dev_environment.py
```

The sync command is the explicit network/install step. It installs
`requirements-dev.txt` and writes a content-hash stamp inside the ignored venv.
After either requirements file changes, direnv reloads and reminds contributors
to run the command again. A requirements change does **not** require another
`direnv allow`; approval is required only when `.envrc` itself changes.

The `.env`, `.direnv/`, Sonar scanner work/cache directories, and local analysis
records are ignored and blocked from staging even with `git add -f`. Run
`direnv deny` to revoke approval for this checkout. Contributors without direnv
can continue exporting variables and activating the venv manually.

## Optional local SonarQube Community Build analysis

This repository supports opt-in analysis against a local SonarQube Community
Build instance. Other external analysis uploads are disabled by policy. The
approved SonarQube Cloud scan is the `sonarqube` job in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml); it uses the
repository `SONAR_TOKEN` secret and root
[`sonar-project.properties`](../sonar-project.properties) to analyze `src/`
after pushes to `main`/`develop`; SonarQube Cloud Automatic Analysis must remain
disabled. That approved scan **also imports the pytest coverage report**: the
`tests` job writes `coverage.xml` (`src/` paths and line numbers only — no PHI)
and hands it to the `sonarqube` job as an internal GitHub Actions artifact,
which the scan reads via `sonar.python.coverage.reportPaths`. PR analysis,
analysis on branches other than `main` and `develop`, and local-data uploads
remain prohibited, and coverage is never sent to Codecov/Coveralls or any
service other than the approved scan.
The local scan is intentionally **not** a Git hook: it can take time, and
`--with-coverage` runs the full pytest suite first.

1. Start the local SonarQube Community Build **server** (Docker) and confirm its
   UI is reachable at `http://localhost:9000` (or set `SONAR_HOST_URL` to another
   loopback URL such as `http://127.0.0.1:9000`). Remote hosts are rejected so
   the local analysis token cannot be sent off-machine. Use one shared server for
   all local projects: generic container name (`sonarqube`), durable **named**
   data volumes, and `--restart unless-stopped`. Prefer restoring an existing
   data volume (so admin password and tokens keep working) over creating a fresh
   empty database. Full container-vs-volume explanation, restore steps, and
   backup notes: [`tools/sonarqube/README.md`](../tools/sonarqube/README.md).
2. In its UI, create a user or project analysis token at **User → My Account →
   Security** (skip this if you restored a volume that already has a working
   token). Do not put the token in a tracked file. Copy `.env.example` to
   ignored `.env` and populate `SONAR_TOKEN`. Both the runner and reporter load
   simple `KEY=VALUE` entries from that file automatically; an explicitly
   exported variable takes precedence. With direnv, also run `direnv allow`.
3. Activate this project’s venv and run:

   ```bash
   python scripts/run_local_sonarqube.py
   ```

   PowerShell equivalent:

   ```powershell
   python scripts/run_local_sonarqube.py
   ```

The runner uses an installed `sonar-scanner` when available; otherwise it runs
the official scanner image through Docker. It checks `/api/system/status`, submits
the analysis using [`tools/sonarqube/sonar-project.properties`](../tools/sonarqube/sonar-project.properties),
and records the last successful scanner submission in the ignored
`.sonar-local/last-analysis.json` file. Check that record without contacting the
server with:

```bash
python scripts/run_local_sonarqube.py --status
```

Every local push, including a branch pushed to open or update a pull request,
runs an advisory update check at most once every seven days. It compares the
Docker-hosted local `sonarqube:community` server image with the matching public
Docker Hub manifest and compares an installed native `sonar-scanner` with
SonarSource's public latest-release metadata. It records only identifiers,
versions, and the check time under ignored `.sonar-local/`. It never pulls,
installs, or restarts anything, and it never sends repository content or the
SonarQube token. Run it manually with:

```bash
python scripts/check_local_sonarqube_updates.py
```

To include test coverage, use `python scripts/run_local_sonarqube.py
--with-coverage`; this deliberately runs the full suite first. When the Docker
scanner cannot reach a service published on host `localhost`, the script maps it
to `host.docker.internal`. `SONAR_DOCKER_HOST_URL` may only name that Docker host
gateway; named Docker network services are deliberately unsupported because the
local-only policy must not permit an arbitrary token destination.

After a successful analysis, report priority findings that belong to this
repository's exact component key. The reporter uses the same ignored `.env`
file automatically:

```bash
python scripts/report_local_sonarqube_issues.py --fail-on-findings \
  --expected-revision "$(git rev-parse HEAD)" \
  --output tmp/sonarqube-priority-findings.md
```

The reporter queries `componentKeys=dicom-viewer-v3` for three scoped tiers:

| Tier | SonarQube filter | Typical use |
|------|------------------|-------------|
| **BLOCKER** | All BLOCKER issues | Must-fix before release |
| **CRITICAL** | All CRITICAL issues (any type) | High-severity bugs, smells, and vulnerabilities |
| **MAJOR** | All MAJOR issues (any type) | Code-smell backlog triage (`TO_DO.md` tracks deferred MAJOR cleanup) |

It verifies every returned component has the `dicom-viewer-v3` prefix and
rejects a mixed-project response. `--fail-on-findings` exits **1** when any
scoped issue is present (all three tiers). The optional Markdown report is
restricted to ignored `tmp/`; neither the token nor SonarQube issue messages are
written to it. On PowerShell, pass the `git rev-parse HEAD` result as the
`--expected-revision` value, or omit that optional assertion when only reading
the report.

For a release or remediation branch, pair the reporter with a fresh analysis of
the same revision:

```bash
python scripts/run_local_sonarqube.py --with-coverage
python scripts/report_local_sonarqube_issues.py \
  --expected-revision "$(git rev-parse HEAD)" \
  --output tmp/sonarqube-priority-findings.md
```

Recommended cadence: run `python scripts/run_local_sonarqube.py
--with-coverage` at least every 14 days, before a release, and after a large
dependency or security-sensitive change. A push that updates `main` checks the
ignored scan record only after the blocking privacy, PHI, secret, type, test, and
full local scanner gates pass. The record is stale when it is older than 14 days
or more than five commits behind `HEAD`; scans recorded before revision tracking
was added are stale until rerun. Missing or stale analysis prints a reminder but
does not block contributors who do not have the local service or token. Check
freshness without contacting SonarQube:

```bash
python scripts/run_local_sonarqube.py --check-freshness-days 14
```

### Approximating coverage on new code locally

SonarQube computes **coverage on new code** on the server: it intersects the
uploaded per-line coverage with the lines a git diff marks as new for the
project's New Code period (`previous_version` on SonarQube Cloud). Neither the
scanner nor SonarLint reports that number locally, and the Cloud value only
appears after a `main`/`develop` push. To sanity-check a branch first, generate
a coverage report and run the advisory approximation:

```bash
PYTHONPATH=src pytest tests --cov=src --cov-report=xml:coverage.xml
python scripts/new_code_coverage.py --base main
```

It reports the ratio of covered to coverable `src/` lines that changed versus
the base ref, lists the uncovered new lines, and accepts `--fail-under PCT` for
scripted checks. It reads only `coverage.xml` and git history — it never
contacts SonarQube. The base ref is a stand-in for the New Code period, so the
number approximates, but does not replace, the server's `new_coverage`.

The root [`sonar-project.properties`](../sonar-project.properties) is reserved
for the approved GitHub Actions `main`/`develop` Cloud scan. Do not point the
local runner at it, add another Cloud workflow, or enable Automatic Analysis.
The separate local settings file is passed only by this runner.

**Privacy / logging gate:** `scripts/git-hook-security-gate.py` invokes **`scripts/git_hook_privacy_checks.py`** on every **pre-commit** and **pre-push** invocation (before branch-gated scans). It reads the **staged** index for **`src/*.py`**: forbids real **`traceback.print_exc(`** calls (matches inside **`tokenize`** **STRING**/**COMMENT** tokens—e.g. docstrings—are skipped); on **git-added** lines only, applies heuristics for patient tag names in logs, path-like literals in **`logger.*`** calls, raw-exception patterns in **`QMessageBox`**-style calls, and **`logger.*`** with non-literal messages without **`sanitize_message`** / **`sanitize_exception`**. Set **`DICOMVIEWER_PRIVACY_HOOK=warn`** to print findings without blocking. From repo root: `.venv\Scripts\python.exe scripts\git_hook_privacy_checks.py`.

**Static typing gate:** the `pre-push` hook runs `scripts/check_basedpyright_errors.py`, matching the GitHub **Pyright** workflow: **0 basedpyright errors** are required across `src/` and `scripts/`, while the existing warning baseline is reported but does not block pushes.

**Full test suite / coverage:** not run on `pre-push` (too slow for every push).
CI’s `pytest` job runs the full suite with `--cov-fail-under=65` and uploads
`coverage.xml` for the approved Sonar path. Locally, when you want the same
check: `PYTHONPATH=src python -m pytest tests --cov=src --cov-fail-under=65`. Pre-commit
still runs the fast agent smoke harness.

**Parallel execution:** `pytest.ini` sets `-n auto` (pytest-xdist), so local
runs match CI and sharding-order bugs surface before a PR rather than after.
The full suite is ~40s on an 18-core host, ~3m30s on CI’s 4 cores, and ~8m40s
serial. For quick single-test iteration, `-n 0` disables parallelism and runs
in-process: `PYTHONPATH=src python -m pytest -n 0 tests/path/test_x.py`.
Tests must not assume execution order or a shared process — in particular,
never construct a `QCoreApplication` in a test; depend on the session `qapp`
fixture, or every later widget test in that worker will abort. See
[`plans/supporting/TEST_SUITE_PARALLELIZATION_PLAN.md`](plans/supporting/TEST_SUITE_PARALLELIZATION_PLAN.md).

**Gitleaks:** `pre-commit` scans the **staged index**. `pre-push` and CI privacy
gate both run **full reachable history** via `scripts/check_gitleaks_history.py`
(~1s on this repo). Narrowed push-only scanning remains available with
`--from-pre-push-stdin` / `--since-main` for ad-hoc use. CI also runs TruffleHog
range/tree scans.

The `pre-commit` hook also prunes **`backups/`** when the current branch is
**`main`** or **`WIP`**. **Intent age** is **not** plain filesystem mtime for
**tracked** files (checkouts refresh mtime). **Tracked:** a file is removed if
**more than 10 commits** have occurred since the **latest commit that touched
that path**, **or** if **more than 10 commits** landed on the branch in the last
**3** days **and** that touch’s committer time is **strictly older than 3 days**
(quiet branches use the commit-depth rule only). **Untracked:** newest embedded
**`YYYYMMDD`** and **mtime** (the **older** of the two) must be **strictly older
than 3 days**. See `scripts/git-hook-prune-backups.py` (`--days`, `--max-commits`,
optional `--velocity-commits`). **Shallow clones** may skew Git counts and times.
The hook then runs **`git add -u -- backups`** so tracked deletions are staged
for the same commit. Other branches are unchanged. Failures are non-fatal.
Preview: `python scripts/git-hook-prune-backups.py --days 3 --max-commits 10 --dry-run`
(repo root, venv on).
