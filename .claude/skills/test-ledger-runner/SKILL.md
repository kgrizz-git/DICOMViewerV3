---
name: test-ledger-runner
description: >Runs test suites, tracks results in tests/test-ledger.md, and verifies tests promised in plans exist—without editing product code or tests. Use for tester subagent or when reporting pytest/jest/npm test outcomes.
---

# Test ledger and execution (tester)

## Rules

- **Do not edit** source, tests, or config to “make green.” Investigate, reproduce, capture logs, and report to orchestrator.
- Use **`python-venv-dependencies`** (or project’s JS/Java flow) before running suites.

## Playwright install scope and execution

- Playwright Test setup is **repo-scoped**: `npm init playwright@latest` should be run in each repository that needs Playwright tests.
- Browser binaries are usually machine-cached, but project dependency pinning and config are repository-local.
- Prefer repo-native package manager commands when present (npm/pnpm/yarn lockfile consistency).
- Baseline command sequence for Playwright suites:
  - `npx playwright test`
  - `npx playwright test --project=chromium` for focused repro
  - `npx playwright test --debug` for interactive failure investigation
  - `npx playwright show-report` and `npx playwright show-trace <trace.zip>` for evidence capture

## Stitch-assisted UX pipeline tagging

- If a failure is tied to Stitch-assisted UX generation or downstream exported flows, mark notes with `stitch` plus one short subtype label.
- Preferred labels: `stitch-setup`, `stitch-skill-missing`, `stitch-mcp`, `stitch-export`, `stitch-flow-regression`.
- Include the source context in Notes when available (for example: skill used, DESIGN.md revision, or generated flow identifier).

## Ledger file: `tests/test-ledger.md`

Append or update rows (keep **newest entries at top**):

| Suite / command  | Date | Tests related (files) | Last result | Notes |
|------------------|------|-----------------------|-------------|-------|

Group by suite/command and **keep only 5 latest runs** for a given test/suite.

Include: flaky markers, skipped tests, env prerequisites, and links to CI runs if applicable.
If Playwright is involved, include project-local setup status and relevant runtime versions when tied to failures.

## Plan alignment

- If a plan promises tests, verify they **exist** and **match** the described behavior; note gaps without implementing them.

## Reporting

- Summarize: pass/fail counts, first failure with file:line, suspected category (logic, env, data), and recommended assignee (usually **coder**).
