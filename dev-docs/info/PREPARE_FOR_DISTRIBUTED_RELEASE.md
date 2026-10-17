# Prepare for distributed release — rename + Mac App Store

**Last updated:** 2026-10-17
**Status:** Draft — planning doc; no code changes yet.

This note captures the process for two distribution-readiness tracks that are not
yet covered by [`RELEASING.md`](../RELEASING.md) or
[`COMMERCIAL_RELEASE_READINESS.md`](../COMMERCIAL_RELEASE_READINESS.md):

1. **Renaming the repo/app** (or spinning off a hard fork).
2. **Shipping via the Mac App Store.**

## 1. Rename / hard fork process

The product name is currently inconsistent ("DICOM Viewer V3" / "DICOMViewerV3"
/ repo `DICOMViewerV3`). Naming is a Tier 1 commercial item (see
`COMMERCIAL_RELEASE_READINESS.md` §Naming). Before renaming:

- Decide final name; check trademark availability (🧑‍⚖️ counsel).
- Update all string surfaces: window title, About dialog, installer metadata,
  README, docs, `src/version.py`-adjacent constants, `USER_DOCS_GITHUB_PREFIX`
  in `src/utils/doc_urls.py`, bundle identifiers.
- Update repository name + default branch references, CI workflow names, and
  any hardcoded repo URLs in docs.
- For a **hard fork**: create new repo, copy history or squash, re-point
  remotes, update license/copyright, re-run full test suite, regenerate
  `THIRD_PARTY_LICENSES.md`.
- Add a migration note in CHANGELOG.md and a redirect in README for old name.

### Concrete rename checklist

- [ ] Pick final product name + trademark check (🧑‍⚖️).
- [ ] `src/version.py` app name constants (if any) and `USER_DOCS_GITHUB_PREFIX`.
- [ ] Window title / About dialog strings (`src/gui/`, `src/core/`).
- [ ] Installer metadata (`.spec`, CI `build.yml`, `BUILDING_EXECUTABLES.md`).
- [ ] `README.md`, `ARCHITECTURE.md`, `AGENTS.md`, `CHANGELOG.md`.
- [ ] Repo name + default branch refs in docs/CI.
- [ ] Bundle identifiers (macOS `CFBundleIdentifier`, Windows app name).
- [ ] Run full test suite + link checker after rename.

## 2. Mac App Store distribution

Current signing doc (`info/CODE_SIGNING_AND_NOTARIZATION.md`) targets
**Developer ID** distribution **outside** the App Store. App Store distribution
requires a different path:

- Use **"Mac App Distribution"** certificate (not Developer ID).
- Enable **App Sandbox** entitlements; audit all file/network/process access.
- PySide6/Qt and VTK must be compatible with sandbox; verify file dialogs,
  export paths, subprocesses (e.g. ffmpeg) work under sandbox.
- Remove/replace any non-sandbox-safe code (shell-outs, unrestricted FS).
- Bundle `THIRD_PARTY_LICENSES.md`; satisfy App Store review guidelines.
- Prepare App Store Connect listing, screenshots, privacy policy, age rating.
- Test on clean macOS via TestFlight before submission.

### Concrete App Store checklist

- [ ] Enroll in Apple Developer Program (if not already).
- [ ] Create "Mac App Distribution" certificate + provisioning profile.
- [ ] Add App Sandbox entitlements to the `.app` bundle; define file-access
      exceptions (user-selected files via open/save panels).
- [ ] Audit subprocess usage (ffmpeg/imageio) for sandbox compatibility; replace
      with in-process or app-group alternatives if needed.
- [ ] Verify VTK render window and Qt file dialogs under sandbox.
- [ ] Add App Store Connect app record, metadata, screenshots, privacy policy URL.
- [ ] Set age rating (medical/health context → likely 12+ or higher).
- [ ] TestFlight internal/external testing on clean macOS.
- [ ] Submit for review; respond to review feedback.
- [ ] Keep Developer ID build as the direct-download channel (parallel).

## 3. Stale-doc updates

- `CODE_SIGNING_AND_NOTARIZATION.md`: clarify App Store is a separate track
  (this doc) and that Developer ID remains the default for direct distribution.
- `COMMERCIAL_RELEASE_READINESS.md`: add Tier 1 item for App Store distribution
  (currently absent); add rename as a tracked item (already present as #11).
- `RELEASING.md`: no App Store steps today; link to this doc when App Store
  becomes a release channel.

## References

- `dev-docs/COMMERCIAL_RELEASE_READINESS.md`
- `dev-docs/RELEASING.md`
- `dev-docs/info/CODE_SIGNING_AND_NOTARIZATION.md`
- `dev-docs/info/BUILDING_EXECUTABLES.md`
- `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` (product naming exploration)
