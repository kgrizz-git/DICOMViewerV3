# Contributing to DICOM Viewer V3

This guide is for **human contributors**: workflows, hooks, CI expectations, and release hygiene. **AI agents and Cursor** should continue to follow **[`AGENTS.md`](../AGENTS.md)** for venv commands, the `src/` module map, signal-wiring rules, and product-oriented display notes.

## Development setup

- **[`DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md)** — environment, hooks, troubleshooting.
- **[`tests/README.md`](../tests/README.md)** — running the test suite.
- **[`README.md`](../README.md)** — clone, install, run from source.

Activate a virtual environment before installing or running (see **`AGENTS.md`**).

## Refactor backups and Git hooks

- See **`.cursor/rules`** and project user rules. **Before major refactors only**, copy files to **`backups/`** with an ISO-like date in the name; do not proceed until the backup exists or the user has waived it. See **`scripts/git-hook-prune-backups.py`** for how **`backups/`** is pruned.
- **Local Git hooks** (details in **`DEVELOPER_SETUP.md`**): the repo-managed
  pre-commit path blocks the staged artifact gate and
  `scripts/git_hook_privacy_checks.py --staged`; findings report only path,
  line, and rule category. The `commit-msg` hook blocks sensitive metadata
  without echoing matched values. Pre-push runs the full-tree privacy and
  security lanes for `main`. Optional scanner wrappers remain local and are
  documented in the PHI/PII guardrails; `SKIP` is not a successful scan.
  The static privacy hook is a blocking syntactic guard, not a complete Python
  data-flow proof; fail-closed runtime output/storage boundaries are the
  authoritative protection.

## Security tooling and optional dev dependencies

- **`pip install -r requirements-dev.txt`** — adds local Python security scanners (semgrep, detect-secrets).
- **TruffleHog v3:** install separately via `powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath` so local scans align with CI’s TruffleHog v3 action/binary line.
- **Debug flags:** do not merge with **`DEBUG_*`** set to **`True`** in `src/utils/debug_flags.py` (CI fails on that).
- **Isolated privacy tools:** create a separate environment from
  `requirements-phi-tools.txt`, then use `scripts/privacy_tool_review.py`.
  Hounddog is advisory/no-account/no-SCM; PhiScan scans staged data-like blobs;
  media and DICOM review are manual admission aids and never certify removal of
  PHI.

## Versioning and changelog

- Application version lives in **`src/version.py`** (`__version__`). Follow **[`info/SEMANTIC_VERSIONING_GUIDE.md`](info/SEMANTIC_VERSIONING_GUIDE.md)** and **[`RELEASING.md`](RELEASING.md)** when cutting releases (changelog, tags, **Current version** line in **`CHANGELOG.md`**).
- Use **`CHANGELOG.md`** for user-visible product and release history. Use **[`MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md)** for developer-maintenance history such as CI, harness, static-analysis, dependency-verification, and repo-hygiene changes. Keep **[`TO_DO.md`](TO_DO.md)** limited to active backlog items; remove fully completed rows once the outcome is captured in the changelog, maintenance log, or a plan/info/bug-investigation note.

## Pylinac pin and QA documentation

- **`requirements.txt`** pins an exact **`pylinac`** version. When **bumping** the pin, follow **`dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md`** (install, **`python -m pytest tests/ -v`**, optional manual ACR QA), and update **`info/PYLINAC_INTEGRATION_OVERVIEW.md`** (**Verified pylinac package version**) plus any user-facing version callouts (`README.md`, `user-docs/USER_GUIDE_QA_PYLINAC.md`, etc.).
- Default Stage‑1 runs use **`src/qa/pylinac_extent_subclasses.py`** (**`ACRCTForViewer`** / **`ACRMRILargeForViewer`**) so origin indices may be **0 … N−1** (stock pylinac is stricter); JSON **`pylinac_analysis_profile`** records **`relaxed_image_extent`**. Users may enable **Vanilla pylinac** in the ACR CT/MRI options dialogs (persisted in **`qa_pylinac_config`**) to run stock **`ACRCT`** / **`ACRMRILarge`** instead.

## Third-party license inventory

Maintain a rolling checklist of bundled Python packages, vendored binaries (e.g. FFmpeg), and **`resources/fonts/`** in **[`info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md)** when pins, PyInstaller `datas`, or fonts change.

**Cine export:** **`requirements.txt`** pins **`imageio`** + **`imageio-ffmpeg`** (vendored FFmpeg; LGPL/GPL-style stack). Frozen/redistributed builds must meet FFmpeg license obligations; see **`AGENTS.md`** for the short product note and this inventory doc for packaging.

## CI and GitHub Actions

- Workflows live under **`.github/workflows/`**. Use current **major tags** for first-party actions (`actions/checkout@v6`, `actions/upload-artifact@v7`, `github/codeql-action/*@v4`) so Dependabot can propose updates. Pin **third-party** actions to release tags when reproducibility matters (e.g. `trufflesecurity/trufflehog@v3.x.x` plus matching `version:` for the scanner image).
- **Storage / billing:** artifact and cache usage accrues in **GB-hours**; see **`info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`**. The **Build Executables** workflow uploads **`dist/`** (and the Linux AppImage) only — **not** PyInstaller’s **`build/`** folder. **`actions-cache-prune.yml`** (weekly + manual) prunes stale Actions caches on non-protected refs while keeping the default branch, **`develop`**, and optional extra refs.
- **macOS PySide6 submodule excludes** are **off** by default; set **`PYINSTALLER_MACOS_SLIM=1`** locally or enable the optional **workflow_dispatch** slim job — see **`info/BUILDING_EXECUTABLES.md`** / **`info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**. **`tests/test_pyinstaller_exclude_audit.py`** guards excluded module names against **`src/`** and **`tests/`** imports.
- **`actions/upload-artifact` v6+** and related actions may require **self-hosted runners ≥ 2.327.1** (Node 24); GitHub-hosted **`ubuntu-latest`** satisfies this.
- If **`.github/dependabot.yml`** lists **`labels:`**, those labels must exist on the repo (e.g. `dependencies`, `github-actions`) or Dependabot will warn on PRs.
- **External analysis uploads are disabled by repository policy.** Coverage is
  printed in the CI job log but is not sent to Codecov/Coveralls. SonarQube
  Cloud, DeepSource, Sentry, and similar repository integrations should remain
  uninstalled or disabled. Use the opt-in local SonarQube runner and local
  security tools when deeper analysis is needed.
- **Local SonarQube Community Build** is an opt-in developer tool, not a hook or CI gate. [`scripts/run_local_sonarqube.py`](../scripts/run_local_sonarqube.py) supplies the isolated [`tools/sonarqube/sonar-project.properties`](../tools/sonarqube/sonar-project.properties) file explicitly, can use Docker for the scanner, and writes the last successful submission timestamp to ignored `.sonar-local/last-analysis.json`. See [DEVELOPER_SETUP.md](DEVELOPER_SETUP.md) for token, server, coverage, and Docker-network guidance. After analysis, [`scripts/report_local_sonarqube_issues.py`](../scripts/report_local_sonarqube_issues.py) reports BLOCKER, CRITICAL BUG/VULNERABILITY, and MAJOR findings scoped to the `dicom-viewer-v3` component key.
  Run it with coverage at least every 30 days, before releases, and after large
  dependency or security-sensitive changes. Main-push hooks provide a
  non-blocking stale/missing reminder after all blocking local gates pass.

## User documentation links

After editing files under **`user-docs/`** (or **`dev-docs/README.md`**), run:

```bash
python scripts/check_user_docs_links.py
```

or:

```bash
python -m pytest tests/test_user_docs_links.py -q
```

CI runs **`.github/workflows/user-docs-links.yml`** on **`main`** / **`develop`**.

## Module layout and optional delegation

- **`AGENTS.md`** at the repo root documents the project map, verification
  commands, privacy rules, and in-app display options for tooling context.
- One agent is the default. Delegation is optional for genuinely independent
  work or one material high-risk review; there is no automatic
  planner/coder/tester/reviewer chain.
