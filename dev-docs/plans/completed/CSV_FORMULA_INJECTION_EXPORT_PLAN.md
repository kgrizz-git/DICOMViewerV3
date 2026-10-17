# CSV formula-injection export gaps

**Status:** Implemented 2026-10-16

**Priority:** P1 (security)

**Created:** 2026-10-16

**Related:** [`src/core/spreadsheet_safety.py`](../../../src/core/spreadsheet_safety.py); cloud security scan of commit `77ae250`.

## Verdict

Both reported findings were real. Tag, ROI, QA, and the CT dose-summary CSV already routed string cells through `neutralize_spreadsheet_value` or `SafeCsvWriter`. These two writers did not.

## Findings

1. **Study index CSV** — `write_entries_csv` in `src/core/study_index/portability.py` used `csv.DictWriter` and wrote metadata (`patient_name`, `study_description`, and the other portable columns) unchanged. A value whose first character is `=`, `+`, `-`, or `@` is a formula when the file is opened in Excel or LibreOffice.

2. **SR dose-event CSV/XLSX** — `StructuredReportBrowserDialog._write_events_csv` and `_write_events_xlsx` wrote `IrradiationEventRow.columns` and dynamic column titles unchanged. Those strings come from SR content, including attacker-controlled TEXT. The separate CT dose-summary writer in `rdsr_dose_sr.py` was already neutralized and stayed out of scope.

JSON export of the SR tree is not a spreadsheet and stays unchanged.

## Decisions

- Use the existing helper. Do not invent a second prefix rule.
- Neutralize every study-index data cell on export, including paths and UIDs. Fixed column headers are not attacker-controlled.
- **Import restores one leading apostrophe** when the next character is a formula trigger. The study-index CSV is a round-trip format (`read_entries_csv` → `import_entries`). Leaving the apostrophe in the database would change names and could break path matching. A value that was already stored as `'=` is indistinguishable from a neutralized `=` after export and is restored without the apostrophe. That collision is accepted; such values are rare and the spreadsheet file stays inert either way.
- Neutralize dose-event **headers and values** in both CSV and XLSX. Dynamic column titles are concept names from the SR. Negative numeric text (for example `-1.2`) becomes a text cell, matching tag/ROI/QA exports.
- No user-guide change. Other neutralized exports do not document the apostrophe, and in-app import restores the original index text.
- Version stays `0.5.0` (unreleased). The fix is patch-class and is recorded under `[Unreleased]`.

## Checklist

- [x] Neutralize study-index CSV cells on write and restore them on read.
- [x] Neutralize SR dose-event CSV and XLSX headers and values.
- [x] Tests cover formula prefixes, a benign round trip, and the `'=` import collision.
- [x] Changelog entry under `[Unreleased]` / Fixed.
