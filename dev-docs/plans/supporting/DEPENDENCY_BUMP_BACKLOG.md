# Dependency Bump Backlog

**Created:** 2026-07-18

Tracks dependency updates that are intentionally deferred because they need
clinical-QA verification or are blocked upstream. Routine dev-tooling and
patch/minor runtime floor raises are handled directly (see the `deps/safe-bumps`
change) and do not belong here.

## Needs ACR-QA verification before bumping

These are `pylinac`-coupled and can change automated ACR phantom analysis
output, so they must not be merged without re-running the clinical QA
regression. Follow
[`dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md`](completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md)
and re-verify **ACR CT + ACR MRI Large** before merging.

| Package | Current | Target | Notes |
|---|---|---|---|
| `pylinac` | `==3.43.2` | `3.45.0` | Exact pin; current verified ACR CT/MRI integration version. Dependabot opens this as the `python-patch-minor` group PR. Re-verify ACR QA after bump. |
| `scikit-image` | `>=0.22.0` | `>=0.26.0` | `pylinac` image-processing dependency; several minor versions of drift. Bump alongside / after the `pylinac` verification, not independently. |

## Blocked upstream (tracked elsewhere)

- **`pydicom` 2.x → 3.x** — capped by `pylinac==3.43.2` (`pydicom<3`). See the
  `PYSEC-2026-2266` row in [`../../security/pip-audit-exceptions.md`](../../security/pip-audit-exceptions.md).
- **`mcp` CVE exceptions** — `mcp` is pinned transitively by `semgrep`
  (`mcp==1.23.3`). Remove the three `mcp` `--ignore-vuln` entries once a
  `semgrep` release depends on `mcp>=1.28.1`. See the `mcp` rows in
  [`../../security/pip-audit-exceptions.md`](../../security/pip-audit-exceptions.md).
