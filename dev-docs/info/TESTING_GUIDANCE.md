# Test-writing guidance

Use this guide when adding or reviewing tests. Choose the lowest-cost test tier
that proves the behavior, but do **not** avoid Qt/PySide6 or pylinac merely
because they add a dependency: tests must exercise the layer where the behavior
lives.

Before writing a test, inspect the target module, its nearest existing tests,
[`tests/conftest.py`](../../tests/conftest.py), and the installed/pinned dependency
version. When behavior depends on an external API, read that library's official
documentation and use its documented contract rather than guessing from a mock.

## Test tiers

| Behavior under test | Preferred approach | Avoid |
|---|---|---|
| Pure transformations, policy, serialization, and error handling | Ordinary unit test with small synthetic inputs. | Importing Qt or pylinac when the production seam can be tested without them. |
| Qt object, widget, signal, or input behavior | Use the project `qapp` fixture and `@pytest.mark.qt`; assert visible state, emitted signals, or a documented callback. | A module-level `QApplication`, a second `QApplication`, or timing sleeps. |
| Our pylinac adapter, dispatch, normalization, or error reporting | Use a small fake pylinac module/class shaped only around the upstream contract actually consumed. Exercise success, missing-dependency, and failure paths. | A fake that reimplements pylinac or asserts private upstream implementation details. |
| Actual pylinac algorithm or dependency compatibility | Add a small focused integration/regression test using approved synthetic or committed fixtures; assert meaningful output and provenance. | Broad, expensive end-to-end coverage for every adapter branch. |

## Qt and PySide6

This repository already supports Qt tests. The session-scoped `qapp` fixture in
[`tests/conftest.py`](../../tests/conftest.py) returns the single process-wide
`QApplication`; request it as a test parameter whenever a QApplication is
needed. Mark tests that need it with `@pytest.mark.qt`.

Keep Qt tests deterministic:

- Construct only the widgets/scenes required for the behavior.
- Drive input with Qt events or the public method that production code uses.
- Assert a result, signal, or state transition. Process the event loop or wait
  for the specific signal when asynchronous delivery is involved; never use an
  arbitrary `sleep`.
- Do not depend on a display, a native file picker, or window-manager geometry.
  The test configuration defaults Qt to `QT_QPA_PLATFORM=offscreen`, matching
  CI.
- Skip only when PySide6 is genuinely optional for the test environment, using
  `pytest.importorskip("PySide6")`; do not skip a test merely because it is a
  GUI test in this repository.

`pytest-qt` is **not** a current project dependency. It is unnecessary for the
supported `qapp` pattern. Propose adding it to `requirements-dev.txt` only if a
test needs its `qtbot` interaction helpers or its signal-waiting diagnostics
often enough to justify a maintained dependency; then use its documented
`qapp`/`qtbot` lifecycle rather than creating applications manually.

References: [pytest-qt introduction](https://pytest-qt.readthedocs.io/en/master/intro.html)
and [qapp fixture reference](https://pytest-qt.readthedocs.io/en/latest/reference.html).

## Pylinac

The application pins pylinac in `requirements.txt`; tests must match that
version's public API and the project's documented viewer-specific behavior.
Start with unit tests at our boundary. Add a real pylinac integration test only
when it validates an algorithm, a compatibility assumption, or a regression
that a fake cannot establish.

For real analysis tests:

- Prefer minimal approved synthetic data or an existing approved fixture.
- For nuclear medicine, prefer the local IAEA NMQC archive when it is configured;
  CI must not download it. The PlanarUniformity and FourBar tests deliberately
  fall back to the reviewed fixtures in `tests/fixtures/dicom_nuclear/`; keep
  higher-fidelity multi-frame and SPECT checks IAEA-gated.
- Assert stable clinical/technical outcomes, exported schema, and provenance,
  not incidental object representation or fragile floating-point exactness.
- Use suitable tolerances for numerical results and record why a tolerance is
  clinically/algorithmically appropriate.
- Read the relevant upstream module documentation before choosing inputs or
  expected results. Pylinac documents both module restrictions and synthetic
  image-generation support for controlled algorithm tests.

Before adding a DICOM, raster image, archive, or other fixture, follow
[`PHI_PII_REPOSITORY_GUARDRAILS.md`](../PHI_PII_REPOSITORY_GUARDRAILS.md)
and the repository artifact-review process. Never add real clinical data as a
test shortcut.

References: [pylinac general overview](https://pylinac.readthedocs.io/en/latest/overview.html)
and [synthetic-image example](https://pylinac.readthedocs.io/en/latest/starshot_docs.html).

## Verification

For a validated defect deliberately deferred to another branch, write the
intended behavior as `@pytest.mark.xfail(strict=True)` and cite the issue in
the reason and test docstring. Do not create a green test that asserts the
defective result; an expected failure keeps the current PR non-blocking while
becoming an actionable XPASS when the later fix lands.

Every xfail must name its plan/issue and removal condition. Use xfail only for
a validated, deferred defect—not for a speculative concern, an unsupported
partial fixture, or an intentional production contract. Those cases need an
ordinary contract test or no test.

Run the new test file directly first, then the closest package tests. For GUI
or integration changes, also run the automated smoke harness; use the full
suite before a risky merge:

```bash
python -m pytest path/to/test_file.py -v
python scripts/agent_smoke_harness.py --write-report
python -m pytest tests/ -v
```
