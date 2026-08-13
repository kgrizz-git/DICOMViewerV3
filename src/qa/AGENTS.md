# QA agent guidance

Apply the root [`AGENTS.md`](../../AGENTS.md) first. This file adds guidance
for changes under `src/qa/`.

## QA safety and entry points

- `requirements.txt` pins `pylinac` exactly. Follow the root dependency-bump
  guidance and [`PYLINAC_INTEGRATION_OVERVIEW.md`](../../dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md)
  before changing pylinac-facing behavior.
- Keep clinical data out of the repository. Use committed reviewed synthetic
  fixtures or local ignored data only under the root PHI/PII rules; never
  weaken a gate because an analysis appears to succeed.
- Start at `core/qa_app_facade.py` for app-facing flows and in `src/qa/` for
  analysis behavior. Use the on-demand
  [module tree](../../dev-docs/info/SOURCE_LAYOUT_MODULE_TREE.md) for detailed
  ownership.

## Focused verification

- QA package changes: `python -m pytest tests/qa -q`
- ACR/nuclear/pylinac behavior: select the applicable
  `tests/test_pylinac_*.py` and `tests/test_qa_*.py` files.
- UI-visible QA changes: add the optional QA smoke step; use suitable local
  phantom data only when it is already available and in scope.

Run the full suite for dependency changes or changes that cross QA, loading,
or export boundaries.
