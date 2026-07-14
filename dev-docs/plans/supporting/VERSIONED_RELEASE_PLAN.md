# Versioned Release Plan

**Status:** Not started  
**Priority:** P0  
**TO_DO ref:** Release / Product — "Make versioned release with executables"

---

## Goal

Establish a repeatable release process that produces versioned, downloadable executables for Windows, macOS, and Linux, published as GitHub Releases with changelogs and attribution.

### Prior work

- **Version source:** `src/version.py` → `__version__ = "0.3.0"`.
- **Changelog:** `CHANGELOG.md` follows Keep a Changelog + SemVer.
- **SemVer guide:** `dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`.
- **Releases guide:** `dev-docs/info/GITHUB_RELEASES_AND_VERSIONING.md` — describes tags, releases, and the intended workflow.
- **Build workflow:** `.github/workflows/build.yml` — builds PyInstaller executables on all 3 platforms on tag push. Produces artifacts but does not create a GitHub Release automatically.
- **Spec file:** `DICOMViewerV3.spec` — PyInstaller config.
- **Release doc:** `dev-docs/RELEASING.md` (if exists) — release procedure notes.

---

## Phase 1 — Pre-release checklist definition

- [ ] Create `dev-docs/RELEASE_CHECKLIST.md` with the following steps:
  1. All planned features/fixes for this release are merged to `main`.
  2. `CHANGELOG.md` [Unreleased] section is finalized — move items to `[x.y.z] — YYYY-MM-DD`.
  3. `src/version.py` `__version__` is bumped to the release version.
  4. `BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` "Last updated" and basis version are current.
  5. `LICENSE` and `THIRD_PARTY_LICENSES.md` exist and are up to date (see [License plan](LICENSE_AND_COMPLIANCE_PLAN.md)).
  6. All tests pass locally and in CI.
  7. Manual smoke test on at least one platform (open folder, view, export, 3D, fusion, pylinac).
  8. Commit version bump + changelog finalization.
  9. Create annotated Git tag: `git tag -a v0.3.0 -m "Release v0.3.0"`.
  10. Push tag: `git push origin v0.3.0`.
  11. CI builds executables; verify artifacts download and run.
  12. Create GitHub Release from tag with release notes (see Phase 3).

---

## Phase 2 — Automate GitHub Release creation in CI

### 2a. Extend `build.yml` to create a Release

- [ ] After all three platform build jobs succeed, add a `release` job that:
  - Downloads all three platform artifacts.
  - Creates a GitHub Release using `gh release create` or `softprops/action-gh-release`.
  - Attaches executables as release assets (`.zip` for Windows, `.dmg` or `.app.zip` for macOS, `.AppImage` for Linux).
  - Uses the tag name as the release title.
  - Extracts the relevant `CHANGELOG.md` section for the release body (use a script or action like `mindsers/changelog-reader-action`).
  - Marks as pre-release if version contains `-alpha`, `-beta`, `-rc`.
- [ ] Only trigger the release job on tag pushes matching `v*`.

### 2b. Version consistency check

- [ ] Add a CI step (all platforms) that verifies `src/version.py` matches the Git tag:
  ```python
  import version
  import os
  tag = os.environ.get("GITHUB_REF_NAME", "")
  assert tag == f"v{version.__version__}", f"Tag {tag} != v{version.__version__}"
  ```
- [ ] Fail the build if they don't match (prevents releasing with wrong version).

---

## Phase 3 — Release notes template

- [ ] Define a release notes template in `dev-docs/RELEASE_NOTES_TEMPLATE.md`:
  ```markdown
  ## What's New in vX.Y.Z

  ### Highlights
  - [1-3 user-facing highlights]

  ### All Changes
  [Extracted from CHANGELOG.md]

  ### Known Issues
  - [Any known issues in this release]

  ### Installation
  - **Windows:** Download `DICOMViewerV3-Windows.zip`, extract, run `DICOMViewerV3.exe`.
  - **macOS:** Download `DICOMViewerV3-macOS.dmg` (or `.app.zip`), open, drag to Applications.
  - **Linux:** Download `DICOMViewerV3-Linux.AppImage`, `chmod +x`, run.

  ### System Requirements
  - Windows 10/11, macOS 12+, Ubuntu 22.04+ (or equivalent)
  - No Python installation required

  ### License
  [License name] — see LICENSE file.
  ```

---

## Phase 4 — Artifact naming and structure

- [ ] Standardize artifact names with version: `DICOMViewerV3-v0.3.0-Windows.zip`, `DICOMViewerV3-v0.3.0-macOS.dmg`, `DICOMViewerV3-v0.3.0-Linux.AppImage`.
- [ ] Update `DICOMViewerV3.spec` or CI scripts to include version in output directory/filename.
- [ ] Include `LICENSE`, `THIRD_PARTY_LICENSES.md`, and `CHANGELOG.md` inside each platform archive.
- [ ] Windows: consider an NSIS/Inno Setup installer as an alternative to a raw zip (defer to follow-up if complexity is too high for first release).
- [ ] macOS: if code-signing is set up (see `dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`), sign and notarize the `.app` before packaging.

---

## Phase 5 — First release execution

- [ ] Complete all items from the pre-release checklist (Phase 1).
- [ ] Decide on the version number for the first formal release:
  - `v0.3.0` (current) — signals pre-1.0 / beta.
  - `v1.0.0` — signals production-ready. **Requires:** license decided, all P0 bugs resolved, manual QA pass.
  - **Recommendation:** Ship `v0.3.0` as a "beta" GitHub Release first, then iterate toward `v1.0.0`.
- [ ] Tag, push, verify CI creates the Release with attached executables.
- [ ] Download and smoke-test each platform's executable from the GitHub Release page.
- [ ] Update `README.md` with a "Download" section linking to the latest release.

---

## Phase 6 — Post-release process

- [ ] After release, start a new `[Unreleased]` section in `CHANGELOG.md`.
- [ ] Bump `src/version.py` to the next dev version (e.g., `0.4.0-dev` or just `0.4.0` immediately).
- [ ] Document the release process in `dev-docs/RELEASING.md` (or update if it exists).

---

## Open questions

1. **First release version:** `v0.3.0` (beta/pre-release) or `v1.0.0` (production)? Recommend `v0.3.0` first.
2. **Code signing:** macOS notarization is documented but may not be set up with credentials. Is this needed for the first release, or can it be unsigned with a "open anyway" instruction?
3. **Windows installer:** Zip-only for now, or invest in an NSIS/Inno Setup installer? Recommend zip for first release.
4. **Update checker:** Should the app check for new versions on startup? Defer to post-first-release.
5. **Dependency on License plan:** The release should include `LICENSE` — this plan depends on [LICENSE_AND_COMPLIANCE_PLAN.md](LICENSE_AND_COMPLIANCE_PLAN.md) Phase 1 at minimum.

---

## Files likely touched

| File | Change |
|------|--------|
| `.github/workflows/build.yml` | Release job, version check, artifact naming |
| `dev-docs/RELEASE_CHECKLIST.md` | **New** |
| `dev-docs/RELEASE_NOTES_TEMPLATE.md` | **New** |
| `dev-docs/RELEASING.md` | Update with final process |
| `src/version.py` | Version bump on each release |
| `CHANGELOG.md` | Finalize [Unreleased] → [x.y.z] |
| `DICOMViewerV3.spec` | Version in artifact name |
| `README.md` | Download section |
