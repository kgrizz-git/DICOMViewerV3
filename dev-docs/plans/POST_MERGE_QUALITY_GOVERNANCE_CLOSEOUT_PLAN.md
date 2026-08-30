# Plan: Post-merge quality-governance closeout

**Last updated:** 2026-08-30
**Status:** Active
**Priority:** P1
**Area:** Documentation closeout, protected-branch CI, maintainability policy

## Purpose

Close out the merged Pylinac ACR implementation correctly, then make two
independent quality-policy improvements without relying on chat history or
combining unrelated risk into one review.

This plan is deliberately executed as **three small PRs**, in order. Each PR
may use a single atomic commit if its verification results remain attached to
the change; do not delay an earlier completed PR for a later phase.

## Guardrails

- Keep SonarQube Cloud limited to the existing privacy-gated `src/` analysis on
  protected `main`/`develop` pushes. Do not add PR analysis or broaden the
  upload scope without an explicit privacy-policy decision.
- Do not place Cloud quality-gate waiting in `sonar-project.properties`: that
  file is shared configuration, while the requested enforcement is CI-only.
- Preserve the complexity ratchet: existing hotspots may retain only their
  recorded ceilings; new or regressed functions must not be grandfathered
  casually.
- Keep the three changes independently reviewable and do not bypass hooks or
  verification gates.

## Phase 1 — documentation closeout (PR 1)

1. Move the merged [Pylinac ACR full metrics export and MRI batch plan](completed/PYLINAC_ACR_FULL_METRICS_EXPORT_AND_MRI_BATCH_PLAN.md) from `plans/supporting/` to `plans/completed/`.
2. Mark its archival task complete and transfer its optional CT/MRI real-phantom
   export check to [Manual Smoke Checks](../TO_DO.md#manual-smoke-checks).
3. Replace the obsolete “two PRs” Next Up item with this plan’s single umbrella
   entry, and refresh the stale complexity backlog wording.
4. Run the documentation link and repository harness checks.

**Acceptance:** `TO_DO.md` contains no claim that the two Pylinac PRs remain,
the plan is archived, and optional human verification is still visible.

## Phase 2 — protected-branch SonarQube Cloud Quality Gate (PR 2)

1. In `.github/workflows/ci.yml`, add scanner arguments to the existing
   `sonarqube` job:

   ```yaml
   - name: SonarQube Cloud scan
     uses: SonarSource/sonarqube-scan-action@7006c4492b2e0ee0f816d36501671557c97f5995
     with:
       args: >
         -Dsonar.qualitygate.wait=true
         -Dsonar.qualitygate.timeout=600
   ```

   Retain that existing action pin (including its adjacent audit annotation)
   and preserve the existing `env: SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}`
   block alongside the new `with: args:` block.
   This makes the job poll the Cloud result and return non-zero for a failed
   Quality Gate. It runs only after the privacy gate and tests, and only for
   `main`/`develop` pushes.
2. Correct the stale `sonar-project.properties` workflow comment; the active
   scanner job lives in `ci.yml`.
3. Update `dev-docs/CONTRIBUTING.md` and
   `security/security-tool-inventory.json` to document the bounded, blocking
   post-push quality-gate behavior.
4. Validate YAML/configuration locally, run the inventory and repository-harness
   checks, then inspect the first protected-branch workflow run after merge.

**Acceptance:** a successful scan with a failed Cloud Quality Gate makes the
`SonarQube Cloud scan` job red. This is post-merge visibility, not PR merge
protection; enabling PR analysis needs a separate privacy review.

## Phase 3 — CCN 15 ratchet and CI parity (PR 3)

1. Change `BLOCK_CCN` and its docstring in
   `scripts/git_hook_line_complexity.py` from 20 to 15.
2. Use `python scripts/git_hook_line_complexity.py --all` to inventory the new
   findings without the staged ratchet. Add only newly over-15 functions to
   `scripts/line_complexity_grandfather.json`, recording their current CCN.
   Do not regenerate the whole baseline.
3. Make CI run the same canonical checker with `--all`. Lizard’s existing
   threshold-15 annotations may remain supplemental, but must not be the only
   CI enforcement.
4. Update the detailed TO_DO entry and any stale threshold references.
5. Verify valid JSON, the canonical full-tree check, focused hook tests, and
   normal pre-commit behavior.

**Acceptance:** the CCN 15 policy is identical locally and in CI, baseline
exceptions are narrow and reviewed, and a new or regressed CCN >15 function
fails both paths.

## References

- [GitHub Actions CI/CD review and storage](supporting/GITHUB_ACTIONS_CI_CD_REVIEW_AND_STORAGE.md)
- [SonarQube Cloud GitHub Actions documentation](https://docs.sonarsource.com/sonarcloud/advanced-setup/ci-based-analysis/github-actions-for-sonarcloud)
- The ignored CCN-15 discovery notes informed this plan; the durable procedure is Phase 3 above.
