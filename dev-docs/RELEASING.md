# Release checklist (semantic versioning)

Use this checklist when cutting a new release so version, changelog, and Git tags stay in sync. The app version is defined in **`src/version.py`** (`__version__`); **`CHANGELOG.md`** repeats it in the **Current version** line at the top for readability—keep those two in sync whenever you bump the version.

## When to bump version

- **PATCH** (x.y.**Z**): Bug fixes only, no new features, no breaking changes.
- **MINOR** (x.**Y**.z): New features or improvements, backward compatible.
- **MAJOR** (**X**.y.z): Breaking changes or removed functionality.

See [dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md](info/SEMANTIC_VERSIONING_GUIDE.md) for full rules and examples.

## Release steps

1. **Decide the next version** (e.g. `3.0.1`, `3.1.0`, `4.0.0`) using the SemVer guide.

2. **Update the single source of truth**
   - Edit `src/version.py` and set `__version__ = "X.Y.Z"` to the new version.

3. **Update CHANGELOG.md**
   - Update the **Current version** line at the top (next to the intro) so it matches `src/version.py`.
   - Move items from the `[Unreleased]` section into a new `[X.Y.Z] - YYYY-MM-DD` section.
   - Keep an empty `[Unreleased]` section at the top for the next release.
   - Update the compare links at the bottom (add the new tag link and point Unreleased to the new tag).

4. **Commit**
   - Commit with a message like: `Release vX.Y.Z` or `Bump version to X.Y.Z`.

5. **Tag the release**
   - Create an annotated tag with the **v** prefix (e.g. `v3.0.1`):
     ```bash
     git tag -a vX.Y.Z -m "Release vX.Y.Z"
     ```

6. **Push branch and tags**
   - Push your branch, then push the tag:
     ```bash
     git push origin <branch>
     git push origin vX.Y.Z
     ```

7. **GitHub Actions**
   - Pushing a version tag (`v*`) triggers [.github/workflows/build.yml](../.github/workflows/build.yml), which builds executables for Windows, macOS, and Linux and creates a GitHub Release with the built artifacts.

## Quick reference

| What              | Where to update      |
|-------------------|----------------------|
| Version number    | `src/version.py` (and **Current version** at top of `CHANGELOG.md`) |
| Release notes     | `CHANGELOG.md`       |
| Git tag           | `vX.Y.Z` (must match `__version__`) |

Never change the contents of a version after it has been released or the tag pushed. If you need to fix something, release a new version (e.g. patch) instead.

## In-app user documentation URLs

**Help → Documentation** and the links inside **Help → Quick Start Guide** are built from **`USER_DOCS_GITHUB_PREFIX`** in [`src/utils/doc_urls.py`](../src/utils/doc_urls.py). That constant must end at the `user-docs` path segment (no trailing filename).

| Scenario | Suggested prefix |
|----------|------------------|
| **Living docs** (default open-source flow) | `.../blob/main/user-docs` so Help always tracks the latest Markdown on `main`. |
| **Release-matched docs** for a frozen binary | Point at the **same tag** as the executable (e.g. `.../blob/v0.2.10/user-docs`) so menu text cannot describe features absent from that build. Revert or branch the constant when cutting releases if you ship custom builds. |
| **Forks / alternate hosting** | Set the prefix to your repo, branch, or published docs root; keep paths under `user-docs/` consistent so `user_doc_url("…")` still resolves. |

When **keyboard shortcuts**, **menus**, or **Help HTML** (`resources/help/quick_start_guide.html`) change in a user-visible way, update **`user-docs/USER_GUIDE.md`** (and related topic files) in the **same** change set when possible so the GitHub hub and Quick Start stay aligned.

## Documentation maintenance cadence

After each **minor** or **major** release—or after a large UI or Help change—run a new copy of [`templates-generalized/doc-assessment-template.md`](templates-generalized/doc-assessment-template.md) into `doc-assessments/` and work through the checklist so drift is caught before the next release.

**Relative links in user docs:** CI runs [`.github/workflows/user-docs-links.yml`](../.github/workflows/user-docs-links.yml) (`python scripts/check_user_docs_links.py`). Locally: `python scripts/check_user_docs_links.py` or `python -m pytest tests/test_user_docs_links.py -q`.
