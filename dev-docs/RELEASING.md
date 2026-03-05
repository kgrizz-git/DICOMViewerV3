# Release checklist (semantic versioning)

Use this checklist when cutting a new release so version, changelog, and Git tags stay in sync. The app version is defined in **one place**: `src/version.py` (`__version__`).

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
| Version number    | `src/version.py`     |
| Release notes     | `CHANGELOG.md`       |
| Git tag           | `vX.Y.Z` (must match `__version__`) |

Never change the contents of a version after it has been released or the tag pushed. If you need to fix something, release a new version (e.g. patch) instead.
