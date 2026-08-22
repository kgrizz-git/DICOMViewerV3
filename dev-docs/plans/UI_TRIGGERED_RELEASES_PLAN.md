# UI-Triggered Releases Workflow Plan

**Status:** Revised pending review — incorporates the 2026-08-21 critical assessment (scratch copy: `tmp/assessment_ui_triggered_releases_plan_2026-08-21_1846.md`, gitignored; the durable record of its evidence lands in `MAINTENANCE_LOG.md` + the baseline table via Step 0 below) and a 2026-08-21 correctness review: rotation commands verified against installed `gh` (no `--delist` flag exists), `build.yml` edits made atomic before the smoke, tag-push-visible deltas documented, concurrency guard added, tag-reuse recovery documented.
**Last updated:** 2026-08-21

## Objective

Allow a manual `workflow_dispatch` of **Build Executables** (`.github/workflows/build.yml`) to publish a GitHub Release using a user-supplied version tag, and skip the Actions artifact upload **on those runs only**, conserving Actions storage on the path that matters.

Scope decisions from the review (do not drift from these):

- **Tag-push behavior is unchanged** for artifacts: tag releases keep the 30-day `actions/upload-artifact` fallback (`GITHUB_ACTIONS_STORAGE_AND_BILLING.md`). The storage saving comes from *manual release* runs, which currently upload ~1 GB-class zips that sit 30 days and are then redundant with the release. We deliberately do **not** skip uploads on tag pushes — if a release step fails there (token, network, one of three legs), the artifact is the only debug/distribution fallback.
- **Two deliberate tag-push-visible changes are in scope** (both listed in Step 4's changelog content): (a) Windows release assets become a single `DICOMViewerV3-*-Windows.zip` instead of the loose `dist/DICOMViewerV3*` tree — on manual publishes *and* tag pushes; (b) release `prerelease` is derived rather than hardcoded `false`, so a future tag like `vX.Y.Z-rc1` publishes as a pre-release (today every tag release is marked stable). "Tag-push behavior is unchanged" above refers to *Actions artifact uploads only*, not release payloads/metadata.
- **Release-asset rotation is part of this plan** (Release Rotation section): release assets are *permanent* and count against **repository** storage, not Actions storage. Conserving Actions storage (Free tier 500 MB limit) by publishing more releases without a rotation policy means endless unbounded repository growth. While repo-size limits are advisory (~10 GB), Release Rotation is necessary hygiene.
- The macOS-slim cleanup (Slim Cleanup section) ships with the same PR but is independent work; it is gated on Step 0 (archive the size evidence + maintainer sign-off on the cleanup option).

## Assumptions (checked)

1. **The release machinery had never executed.** Zero tags exist in the repo and no release is recorded in `MAINTENANCE_LOG.md`; the `softprops/action-gh-release` steps at `build.yml:314-348` are unverified. The rollout therefore starts with a throwaway publish smoke (Pre-rollout Smoke), not an assumed-good mechanism.
2. **GitHub Release assets do not count against Actions storage** (true), **but** do count against repository storage (repo-size guidance is ~10 GB advisory). Handled by Release Rotation.
3. **The slim "saves 0 MB" finding is measured, not asserted** — see Evidence. It holds for the current dependency graph only; the ongoing guard after cleanup is the filled-in baseline `du` table, not the deleted test.
4. On manual dispatch, `github.ref` is the branch ref: without changes, version parsing falls back to `latest` (files `DICOMViewerV3-latest-…`). This plan routes file naming through the user-supplied tag.

## Evidence: the slim flag saves 0 MB (measured 2026-08-21)

Same-commit local A/B on macOS (arm64), `tmp/build_test.sh` (scratch): standard build (`PYINSTALLER_MACOS_SLIM` unset) vs slim (`=1`).

- `du -sk`: **1,178,268 KB for both** `DICOMViewerV3_standard.app` and `DICOMViewerV3_slim.app` — byte-identical, 0 MB saved. The PyInstaller analysis logs are identical apart from hook ordering.
- Environment: PyInstaller 6.22.2, pyinstaller-hooks-contrib 2026.6, PySide6 6.11.2, Python 3.12.10 (`pyinstaller>=6.21.0` open pin — record exact versions in Step 0).
- Why zero: the app imports only QtCore/QtGui/QtWidgets/QtOpenGL + the matplotlib qtagg path; modern PyInstaller traces the import graph, so the `MACOS_PYSIDE6_MODULE_EXCLUDES` modules (WebEngine, 3D, Quick, Multimedia, …) were never collected in either build. The "200–500 MB" figures in `completed/pyinstaller-bundle-size-macos-2026-04-09.md` and the baseline doc are upper bounds *if analysis would pull them in* — a conditional the measurement has now falsified for this graph.
- **Conditionality:** the result is a property of the *current* dependency graph, not of PyInstaller forever. A future `pylinac`/PySide6 bump that starts importing an excluded module reverses it.

## Proposed changes to `build.yml`

### 1. Dispatch inputs

Replace the existing `build_macos_slim` input (deleted by Slim Cleanup) with:

```yaml
on:
  workflow_dispatch:
    inputs:
      publish_to_release:
        description: 'Create/publish a GitHub Release from this run (requires release_tag_name)'
        required: false
        type: boolean
        default: false
      release_tag_name:
        description: 'Version tag for the release, strict form vX.Y.Z or vX.Y.Z-pre (e.g. v1.2.3-rc1). Validated before any build step.'
        required: false
        type: string
        default: ''
```

- `prerelease` is **derived, not an input**: a forgotten checkbox is how betas ship as stable.
- `permissions: contents: write` is already set on the `build` job (`build.yml:22-23`) — sufficient for tag + release creation.

### 2. Prepare Release Job (Eliminates Matrix Race Condition)

GitHub Actions matrix jobs run concurrently. If all three OS legs attempt to create the Git tag and GitHub Release at the same time, the GitHub API can return `409 already_exists` for the slower legs, causing flaky failures.

To eliminate this race condition, add a new `prepare_release` job *before* the `build` job. This job runs only once, validates the inputs, and checks the tag synchronously so the matrix jobs don't race on creation.

Insert this immediately before the `build:` job definition (`build.yml:19`):

```yaml
  prepare_release:
    name: Prepare Release
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Checkout code
        if: github.event_name == 'workflow_dispatch' && inputs.publish_to_release == true
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7

      - name: Validate release inputs
        if: github.event_name == 'workflow_dispatch' && inputs.publish_to_release == true
        shell: bash
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          INPUT_TAG: ${{ inputs.release_tag_name }}
        run: |
          set -euo pipefail
          TAG="$INPUT_TAG"
          echo "Requested tag: '$TAG'"
          if [ -z "$TAG" ]; then
            echo "Error: release_tag_name is required when publish_to_release is checked." >&2
            exit 1
          fi
          if ! printf '%s' "$TAG" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z][0-9A-Za-z.-]*)?$'; then
            echo "Error: tag must match vX.Y.Z or vX.Y.Z-pre (got '$TAG')." >&2
            exit 1
          fi
          
          # Check tag existence
          REMOTE_TAG_SHA=$(git ls-remote --tags origin "refs/tags/$TAG" | awk '{print $1}')
          if [ -n "$REMOTE_TAG_SHA" ]; then
            if [ "$REMOTE_TAG_SHA" != "$GITHUB_SHA" ]; then
              echo "Error: tag '$TAG' already exists on origin pointing to a different commit ($REMOTE_TAG_SHA vs $GITHUB_SHA) — refusing. Choose a new version." >&2
              exit 1
            else
              echo "Note: tag '$TAG' already exists on origin pointing to current commit ($GITHUB_SHA). Allowing idempotent re-run."
            fi
          fi
          
          # Create release shell synchronously to prevent matrix jobs from racing
          if ! gh release view "$TAG" >/dev/null 2>&1; then
            echo "Creating release $TAG..."
            PRERELEASE_FLAG=""
            if [[ "$TAG" == *-* ]]; then
              PRERELEASE_FLAG="--prerelease"
            fi
            gh release create "$TAG" --target "$GITHUB_SHA" --title "Release $TAG" --generate-notes $PRERELEASE_FLAG
          else
            echo "Release $TAG already exists."
          fi
```

Then, update the `build` job to declare `needs: prepare_release`:

```yaml
  build:
    name: Build on ${{ matrix.os }}  # display name kept as-is
    needs: prepare_release
    runs-on: ${{ matrix.os }}
```

Rationale: Placing this in a dedicated preceding job removes the concurrent 409 API race on validation/creation. If `publish_to_release` is false (or on a tag push), the `prepare_release` steps gracefully skip, its job status evaluates to `success`, and `build` proceeds normally without requiring complex `if: always()` logic. The strict regex keeps `sed 's/^v//'` in Section 3 deterministic.

Recovery beyond same-SHA re-runs: if a leg fails and you push a fix, the new SHA differs from the tagged commit and validation refuses ("Choose a new version"). Escape hatch: `gh release delete <tag> --cleanup-tag --yes` (removes release *and* tag together), then re-dispatch with the same tag name. Expect this loop during rollout; record the command in `BUILDING_EXECUTABLES.md` troubleshooting.

Cost note: `prepare_release` provisions an ubuntu runner on every build (plain manual builds and tag pushes included) even when its steps skip instantly — avoiding that requires `always()`-style `needs` logic, which this design deliberately avoids; accepted. A workflow-level concurrency guard (Section 7) closes the remaining simultaneous-dispatch race on `gh release create`.

### 3. Version parsing in packaging steps

First, add a new step for Windows after `Verify executable exists` to package the directory into a zip (otherwise `action-gh-release` uploads loose individual files instead of a neat archive):

```yaml
      - name: Create ZIP (Windows)
        if: matrix.os == 'windows-latest'
        shell: bash
        env:
          GH_REF: ${{ github.ref }}
          RELEASE_TAG: ${{ inputs.release_tag_name }}
          PUBLISH: ${{ inputs.publish_to_release }}
        run: |
          if [ "$PUBLISH" = "true" ] && [ -n "$RELEASE_TAG" ]; then
            VERSION=$(echo "$RELEASE_TAG" | sed 's/^v//')
          elif [[ "$GH_REF" == refs/tags/* ]]; then
            VERSION=$(echo "$GH_REF" | sed 's/refs\/tags\/v//')
          else
            VERSION="latest"
          fi
          ZIP_NAME="DICOMViewerV3-${VERSION}-Windows.zip"
          python -m zipfile -c "${ZIP_NAME}" dist/DICOMViewerV3
          ls -lh "${ZIP_NAME}"
```

Update **exactly these four existing `build`-job steps** (the slim job's copies disappear with Slim Cleanup — do not edit steps that no longer exist):

- `Build AppImage` (`build.yml:150-163`)
- `Verify AppImage exists` (`build.yml:165-179`)
- `Create DMG (macOS)` (`build.yml:204-220`)
- `Verify DMG contents (macOS)` (`build.yml:222-249`)

Pattern (adds two env vars; each step's `GH_REF` env is kept):

```yaml
        env:
          GH_REF: ${{ github.ref }}
          RELEASE_TAG: ${{ inputs.release_tag_name }}
          PUBLISH: ${{ inputs.publish_to_release }}
        run: |
          if [ "$PUBLISH" = "true" ] && [ -n "$RELEASE_TAG" ]; then
            VERSION=$(echo "$RELEASE_TAG" | sed 's/^v//')
          elif [[ "$GH_REF" == refs/tags/* ]]; then
            VERSION=$(echo "$GH_REF" | sed 's/refs\/tags\/v//')
          else
            VERSION="latest"
          fi
```

The step already repeats this block verbatim per leg (shell-local `VERSION`), so all four need the same change. Gating on `PUBLISH` (not bare `-n "$RELEASE_TAG"`) means a plain manual build with a stray tag typed in still names its files `…-latest-…`, as it does today.

Pre-existing quirk preserved: the tag-push `sed` assumes a leading `v` (`refs\/tags\/v`); a pushed tag without it leaves slashes in `VERSION`. Out of scope — the trigger only matches `v*` tags.

### 4. Artifact upload — skip on manual-release runs only

Per the Objective scope decision, the `if:` on each of the three upload steps (`build.yml:285` Windows, `:296` macOS, `:306` Linux) becomes:

```yaml
        if: matrix.os == 'windows-latest' && inputs.publish_to_release != true
```

(adjust `matrix.os` per step; `retention-days: 30` and artifact `name`s unchanged). Tag pushes and non-publishing manual runs upload exactly as today. On a non-dispatch event the `inputs` context is empty, so `inputs.publish_to_release != true` evaluates to true, leaving tag runs untouched.

### 5. Release trigger conditions

On each of the three `softprops/action-gh-release` steps (`build.yml:314-348`), update the `if:` condition:

```yaml
        if: (startsWith(github.ref, 'refs/tags/') || inputs.publish_to_release == true) && matrix.os == 'windows-latest'
```
*(Note: adjust `matrix.os` to match the specific job leg for each step).*

**For Windows specifically**, you must also explicitly update the `files:` array to point to the newly created ZIP instead of the loose directory (this applies to both manual publishes and tag pushes):
```yaml
        with:
          files: |
            DICOMViewerV3-*-Windows.zip
```

### 6. Release step `with:` block

```yaml
        with:
          # (Note: preserve the existing 'files:' array per OS leg)
          tag_name: ${{ inputs.release_tag_name || github.ref_name }}
          name: Release ${{ inputs.release_tag_name || github.ref_name }}
          # Any semver pre-release suffix ("vX.Y.Z-…") publishes as a pre-release; the
          # strict validation regex guarantees "-" can only appear as the pre-release delimiter.
          # Branch names can contain "-", so the manual-publish branch keys off the input, not ref_name.
          prerelease: ${{ ((inputs.publish_to_release == true) && contains(inputs.release_tag_name, '-')) || (startsWith(github.ref, 'refs/tags/') && contains(github.ref_name, '-')) }}
          overwrite: true
          draft: false
          generate_release_notes: true
```

- **`overwrite: true` (important):** the three steps share one release. Today (default `overwrite: false`) a re-run re-uploading same-named assets fails with `already_exists`, so a partially published release can only be recovered by manually deleting the release **and** the tag. With `overwrite: true`, re-runs succeed (though note PyInstaller output is not *byte-identical* across re-runs, same-name replacement is practically safe). 
  *(Note on tag creation / empty releases: The new `prepare_release` job runs synchronously beforehand, creating the release shell. Because it creates an empty release before the matrix runs, if a matrix job fails, an empty release is left behind — publicly visible immediately, since `prepare_release` creates it non-draft. This is intentional: you should recover by clicking "Re-run failed jobs", which will idempotently populate the existing release; if you abandon the attempt instead, remove it with the escape-hatch command in Section 2. Additionally, while `prepare_release` removes the tag-creation race, the matrix jobs still race to upsert release metadata (name, prerelease, notes) via `softprops`. This is a pre-existing condition on tag pushes and softprops handles concurrent metadata upserts gracefully, so this remaining race is an accepted trade-off).*
- **`name:` note for the changelog:** an explicit `name` makes softprops re-assert "Release vX.Y.Z" as the release title on every run. Existing published releases are untouched (none exist yet — see Assumption 1), but record it in the CHANGELOG entry so the naming is intentional, not accidental.
- `GITHUB_TOKEN` env lines stay as-is.

### 7. Workflow concurrency guard

Add at workflow top level (next to `on:`):

```yaml
concurrency:
  group: build-${{ github.ref }}
  cancel-in-progress: false
```

Without it, two simultaneous dispatches with the same tag both pass validation, then race `gh release create` — the loser gets HTTP 409 under `set -euo pipefail` and fails the whole run via `needs`. Per-ref serialization makes the second run queue, and the idempotent validation path (Section 2) lets it succeed once the first finishes. Internal-only change: no output differences; tag pushes and plain builds are unaffected in practice since identical refs rarely run concurrently.

## Release Rotation (new practice — required by the repo-storage flip side)

Release assets persist forever and count against *repository* storage (repo-size guidance is ~10 GB advisory). Each release carries roughly a 1.1 GB-class macOS DMG plus the Windows zip and AppImage; keeping three releases is therefore ~**6 GB** of repository storage — bounded, but only if rotation actually executes. Add to `BUILDING_EXECUTABLES.md` (GitHub Actions section):

- Keep the **latest three releases** with assets; for each superseded release, delete its assets (keeps the release entry, notes, and tag; frees repo storage). There is **no `--delist` flag** on `gh release edit` (verified against installed gh); delete assets via the REST endpoint:

  ```bash
  OWNER_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
  gh api "repos/$OWNER_REPO/releases/tags/<tag>" --jq '.assets[].id' |
    xargs -I{} gh api -X DELETE "repos/$OWNER_REPO/releases/assets/{}"
  ```

  If fully retiring a release instead, `gh release delete <tag> --cleanup-tag --yes` removes assets, the release, and the git tag in one command (the tag deletion also unblocks name reuse under the SHA-validation guard in Section 2).
- **Rotation executes as part of every release cut**: add the rotation step to the release procedure in `dev-docs/RELEASING.md` (the BUILDING_EXECUTABLES section alone is reference prose nobody runs).
- Pre-release tags created for smoke/CI use (pre-rollout smoke below) are deleted, not rotated.

## Slim Cleanup

The flag machinery is proven redundant (Evidence). Cleanup ships in the same PR. One open **maintainer sign-off in Step 0** between:

- **D1 — full deletion (this plan's default, per original design):** remove flag, list, test, job, docs. Trade-off accepted: if a future dependency bump starts importing an excluded Qt module, the macOS bundle silently re-bloats. **Note:** Post-D1, there is no automated CI tripwire for this bloat; detection relies entirely on a human manually reading the `du` logs against the baseline table.
- **A1 — keep the list, apply it unconditionally on Darwin:** drop only the env flag + slim job + CI/docs ceremony. The excludes then cost 0 bytes (measured) but act as a size tripwire (a WebEngine-pulling dependency is blocked automatically instead of adding ~200 MB). Trade-off: the original "safest"/default-off design exists because third-party *lazy* imports of excluded modules would crash a frozen app — A1 re-exposes that crash class on every macOS build.

Both options remove the flag, the slim job, and the flag-specific docs. Under A1 the one-line spec gate becomes `+ (IS_DARWIN ? list(MACOS_PYSIDE6_MODULE_EXCLUDES) : [])` and `tests/test_pyinstaller_exclude_audit.py` keeps all three tests unchanged.

**Scope (D1 unless Step 0 picks A1):**

- `DICOMViewerV3.spec`: the `PYINSTALLER_MACOS_SLIM` env parse (`:28-33`), the conditional append in `excludes` (`:210-212`), the import removal (`:41`), and the header comment (`:13`) + the `# macOS: optional size trim` comment (`:28`).
- `scripts/pyinstaller_exclude_lists.py`: the `MACOS_PYSIDE6_MODULE_EXCLUDES` tuple (`:39-69`) **plus** the module header docstring lines that describe the macOS trims (`:1-8`) — the plan must not leave a docstring advertising a deleted tuple. (A1 keeps the tuple and only rewords the "when DICOMViewerV3.spec sets…" comment.)
- `tests/test_pyinstaller_exclude_audit.py`: delete `test_macos_excluded_pyside6_not_imported` (`:96-109`) and its import; update the module comment (`:1-9`) which lists "macOS PySide6 trims." File and the matplotlib/PIL tests stay.
- `.github/workflows/build.yml`: delete the `build_macos_slim` dispatch input (`:12-16`); delete the entire `build_macos_slim` job (`:350-457`); remove `pyinstaller_macos_slim` from **all three** matrix include rows (`:32, :36, :40`), the `env:` mapping (`:77`), and the `echo` (`:79`) in `Build executable` — not one row, all three.
- Docs (complete scrub list — the original four-file list missed these):
  - `dev-docs/CONTRIBUTING.md:63` is a combined slim + audit-test sentence — rewrite it, don't just delete the slim clause (the audit test itself remains under D1).
  - `dev-docs/info/BUILDING_EXECUTABLES.md`: the `PYINSTALLER_MACOS_SLIM` section (`:94-116`), Step-5 checkbox text (`:461-462`), and the spec-summary exclusions wording (`:63`, `:77`).
  - `dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`: the flag table (`:5-21`), the order-of-magnitude section (`:23-39`) → replace with the measured 0 MB result, the "Authoritative method" line (`:41`), "CI estimates" bullets (`:83-92`), and fill the baseline table (Step 0).
  - `dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`: add one line to the build.yml row — manual-release runs skip the artifact upload (retention otherwise unchanged).
  - `dev-docs/plans/supporting/EXECUTABLE_SIZE_REDUCTION_PLAN.md`: open items `:26, :51, :64` reference slim/cross-platform excludes — mark each retired/superseded (a "brief note" leaves stale open checklists). Under A1, item `:64` becomes done.
  - `dev-docs/RELEASING.md`: add the Release Rotation step to the release-cut checklist (belongs to the rotation practice, listed here so the Step-2 scrub owns the edit).
  - `CHANGELOG.md` and `dev-docs/plans/completed/pyinstaller-bundle-size-macos-2026-04-09.md` stay untouched (accurate history) — the completed plan gains only a one-line pointer noting the flag was later retired (and why), per the tracking-split convention.
  - `AGENTS.md` needs no change (no slim references — verified).

After cleanup, `python -m pytest tests/test_pyinstaller_exclude_audit.py -v` must pass, and the full suite per AGENTS.md verification.

## Pre-rollout Smoke (first-ever exercise of the release path)

Before the real release: on a throwaway branch, run the dispatched workflow with `publish_to_release` checked and `release_tag_name: v0.0.0-ci-smoke`.

1. All three legs must produce the expected filenames (`v0.0.0-ci-smoke` versions) and attach to **one** release, tagged at the dispatched commit, flagged pre-release (derived), non-draft.
2. Artifact upload must be **skipped** on this run (Objective behavior).
3. Re-run the same dispatch to confirm `overwrite: true` idempotence (no `already_exists` failure).
4. Clean up: `gh release delete v0.0.0-ci-smoke --cleanup-tag --yes` (release + tag in one command). Record the run URLs in `MAINTENANCE_LOG.md` alongside the Step 0 evidence.

(No frozen-app smoke: `scripts/agent_smoke_harness.py` is source-tree-only — it hard-codes `python src/main.py` — and under D1 there is no slim `.app` to smoke. The relevant smoke for a packaging change is the release itself plus the baseline `du` check in the run logs.)

## Steps, in order

0. **(Maintainer sign-off & Verification)** Run `gh release list` and `git tag` to verify zero tags/releases exist (Assumption 1). Record the Evidence numbers + exact dependency versions into `MAINTENANCE_LOG.md`, fill the baseline table in `PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`, add the pointer line in the completed plan, and choose D1 vs A1. *Everything below is blocked until this lands (the D1-vs-A1 choice gates Step 1's spec/job deletions).*
1. **All `.github/workflows/build.yml` edits in one atomic pass** (all `build.yml` line refs in this doc describe today's file; one pass makes shifting numbers irrelevant): dispatch inputs + `prepare_release` + concurrency guard (Sections 1–2, 7); version parsing + Windows zip + upload-skip conditions (Sections 3–4); release triggers + `with:` blocks (Sections 5–6); **and** the Slim Cleanup deletions inside `build.yml` (dispatch input, slim job, matrix rows, env, echo). Doing the slim deletions in the same pass avoids a dead slim job referencing a deleted dispatch input mid-sequence, and makes the smoke exercise the finished workflow.
2. **Slim Cleanup outside `build.yml`** (D1 or A1 per Step 0): `DICOMViewerV3.spec`, `scripts/pyinstaller_exclude_lists.py`, `tests/test_pyinstaller_exclude_audit.py`, the docs scrub list, the completed-plan pointer line, and the `CHANGELOG.md` entry (content per Step 4).
3. **Pre-rollout smoke** (above) from the throwaway branch — `workflow_dispatch` runs the workflow definition from the selected branch, so this exercises the edited `build.yml` before merging. If the smoke reveals release-machinery breakage (Assumption 1's risk), fix it as a first-class part of this change.
4. Version: patch bump of `src/version.py` + `CHANGELOG.md` **Current version** sync, per `dev-docs/RELEASING.md` — precedent `CHANGELOG:458` classifies distribution/CI-packaging-only changes as patch. Content: manual-dispatch release publishing; artifact upload skipped on manual-release runs; **Windows release payloads become a single zip (tag pushes included)**; **derived prerelease marking on tag pushes (`vX.Y.Z-…` tags)**; release rotation practice; macOS slim flag retired (0 MB measured) or made unconditional (if A1).
5. Verification per AGENTS.md (pre-merge gate): `python -m pytest tests/ -v` (long timeout), `python scripts/check_repo_harness.py`, `python scripts/check_architecture_boundaries.py`, agent smoke, plus `python scripts/check_user_docs_links.py` (insurance: the scrub removes doc sections other files reference).
6. **Post-merge release cut:** dispatch from merged `main` (per RELEASING.md) so the binaries embed the bumped `src/version.py`; confirm all three legs' assets attach to one non-draft release.

**Rollback:** the whole change is one commit/PR over `build.yml` + packaging files + docs. While Assumption 1 still holds (no real release published yet), reverting restores today's behavior exactly. Once any real release/tag exists, revert removes only the *machinery* — published tags, releases, and assets persist and are disposed of via the Release Rotation deletion commands, not the revert.
