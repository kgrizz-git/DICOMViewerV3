Last updated: 2026-04-07

# Logs Directory Files

- [README.md](logs/README.md) - Overview of the `logs/` directory, listing its primary files: `test-ledger.md` for append-only tester subagent output and `docs_log-*.md` for docreviewer outputs. Notes that multi-agent coordination state lives under `plans/orchestration-state.md`, not here.
- [test-ledger.md](logs/test-ledger.md) - Append-only test run ledger maintained by the **tester** subagent per the `test-ledger-runner` skill. Rows are added newest-first with columns for suite/command, date, related files, last result, and notes; no other role edits this file to mask failures.
