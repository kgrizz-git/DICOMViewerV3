# Clean GitHub Repository Recreation Runbook

**Last updated:** 2026-07-16

This runbook prepares a destructive repository replacement but does not
authorize or perform it. The objective is a private GitHub repository whose
published history begins with one reviewed snapshot commit and contains no
legacy refs, Dependabot branches, personal commit email, local scanner state,
or local-only DICOM/QC data.

## Verified current state

- Local `main` and local `old-main` are unrelated histories and share zero
  commits.
- `old-main` contains 672 commits. All 672 are local-only; none are reachable
  from any refreshed `origin/*` ref.
- The current GitHub repository contains 25 unique commits: 14 on `main` and 11
  additional commits reachable only from 11 Dependabot branches.
- The remote is private, uses `main`, has Issues and Projects enabled, and has
  no Actions/Dependabot secrets, Actions variables, environments, or webhooks.
- GitHub reported that rulesets and classic branch protection for this private
  repository require an account-plan upgrade or making the repository public.
  Do not make it public to obtain those features.
- GitHub Actions are enabled with `allowed_actions=all`; SHA pinning is not
  required. Tracked workflows and local hooks are therefore the available
  enforcement layers on the current plan.

## Preconditions

1. Working tree is clean and the desired snapshot commit uses the account
   noreply address.
2. Full tests, repository harness, architecture check, staged/tracked PHI gate,
   critical privacy scan, Gitleaks history scan, and local security suite pass.
3. Local SonarQube analysis is current.
4. `git ls-files` contains no `.phi-tools/`, `.sonar-local/`, `.scannerwork/`,
   `.sonar*`, `.sonarqube*`, `.direnv/`, `.env`, local study data,
   scanner reports, coverage XML, or ignored runtime state.
5. Record the source commit hash and `git write-tree` hash in the execution
   notes. The clean snapshot must reproduce that tree hash before publication.

## Recreation procedure — requires explicit approval

1. Export the reviewed commit with `git archive`, not by copying the current
   directory. This excludes `.git`, ignored tools, untracked files, and the
   local `old-main` ref by construction.
2. Extract into a new sibling directory, initialize a new repository with
   `main`, and set the repository-local author to
   `216068303+kgrizz-git@users.noreply.github.com`.
3. Stage the extracted archive with `git add -f --all`. Force-add is deliberate
   here because the archive contains only source-tracked files, while several
   required packaged icons and the PyInstaller spec match conservative ignore
   patterns. Confirm the new index tree equals the recorded source tree hash.
4. Run the blocking tracked-tree and privacy checks in the extracted snapshot.
   Initialize/install a fresh application `.venv`; do not copy either local
   virtual environment.
5. Create one root commit. Confirm exactly one reachable commit, one local
   branch, one root, a clean tree, and only the noreply author email.
6. Preserve the existing private repository only if desired as an explicitly
   local archive. Deleting the GitHub repository removes its current main and
   Dependabot refs and cannot be undone through this workflow.
7. After a separate explicit confirmation, delete and recreate
   `kgrizz-git/DICOMViewerV3` as **private**, push only the new `main`, and
   confirm the remote contains one branch and one commit.
8. Restore non-secret settings: Issues on, Projects on, Wiki/Discussions off.
   Prefer squash merges and automatic branch deletion; review whether merge
   commits and rebases should remain enabled.
9. Keep Codecov, SonarCloud, Sentry, external analysis uploads, repository
   webhooks, Actions secrets, variables, and environments absent unless a later
   explicit policy decision changes that.
10. Re-enable Dependabot only after the root snapshot is present. Its new
   branches must be based exclusively on the recreated history.

## Post-recreation evidence

Record only nonsensitive evidence: new repository URL, root commit hash, tree
hash match, branch/ref counts, check names and pass/fail status, Actions policy,
and repository visibility. Never record tokens, scanner matches, local paths,
OCR text, DICOM values, or deleted-history contents.

The local `old-main` branch must never be pushed to the recreated repository.
