<!--
⚠️ No patient data (PHI/PII): never add DICOM files, pixel data, study
screenshots, or logs with identifiers. Tests must use synthetic/de-identified
fixtures only.
-->

## Summary

<!-- What does this change do, and why? -->

## Related issues

<!-- e.g. Closes #123 -->

## Changes

<!-- Bullet the notable changes. -->

## Testing

<!-- How did you verify this? Commands, new/updated tests, manual checks. -->

## Checklist

- [ ] No PHI/PII or DICOM study data added anywhere (code, tests, fixtures, screenshots).
- [ ] `ruff`, `basedpyright`, and the test suite pass locally.
- [ ] Documentation impact recorded: canonical user/developer/in-app docs updated for user-visible behavior, or a bounded follow-up is linked.
- [ ] For new/changed visible actions or workflows, `python scripts/check_doc_feature_coverage.py` was reviewed; for user-doc changes, `python scripts/check_user_docs_links.py` passes.
- [ ] Public or high-risk contract docstrings changed in this PR were verified against code and tests.
- [ ] For a minor/major release or substantial UI/Help change, a timestamped documentation assessment was created or the release checklist links the upcoming assessment.
- [ ] Commits use the GitHub noreply author email.
