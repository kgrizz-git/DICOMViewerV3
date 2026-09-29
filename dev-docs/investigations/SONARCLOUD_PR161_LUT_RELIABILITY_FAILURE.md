# SonarCloud reliability failure after PR #161

**Last updated:** 2026-09-28

## Incident

PR #161, “Add per-pane look-up tables and color maps,” merged into `main` as `d0665ad` on 2026-09-28. The subsequent SonarCloud quality gate reported `new_reliability_rating` C (3), above its A (1) threshold. The reported new issues were Python rule `S1244` at `src/core/lut_curve.py:236` and `src/core/lut_engine.py:471`. The reported new coverage was 80.9%; the other reported gate conditions passed. These gate figures came from the initial incident report and were not independently queried here.

## Code assessment

`_perpendicular_distance` calculates a chord length with `np.hypot`. A zero-length chord needs the point-to-endpoint distance to avoid division by zero. A strictly positive length should use the perpendicular-distance formula, however small it is. The original `length == 0.0` expresses that boundary but triggers S1244. `length <= 0.0` preserves the zero/nonzero split for this nonnegative length without a floating-point equality check. See `src/core/lut_curve.py:228-239`.

`_gamma_curve` returned the original query when `gamma == 1.0`; all other values used `np.power(query, gamma)`. Replacing this with default `math.isclose(gamma, 1.0)` changes the transfer function for nearby values, since its default relative tolerance includes some non-one gamma values. Applying `np.power` for every valid gamma removes the branch, preserves the gamma-one numerical result on the tested ramp, and applies near-one values as specified. See `src/core/lut_engine.py:467-473` and `tests/core/test_lut_engine.py`.

The proposed `math.isclose(length, 0.0)` deserves a nuance: with default `abs_tol=0.0`, it matches only exact zero when the other operand is zero. It would not itself broaden the zero branch. The nonnegative comparison states the intended geometric boundary more directly. No approximate comparison is appropriate for gamma's exact identity optimization.

## Verification and limits

The focused LUT tests and repository gates should be run before merge. The existing gamma-one byte-identity test and the added near-one test cover the behavioral distinction. A passing local test cannot establish that the remote SonarCloud quality gate will pass; that requires the PR's SonarCloud analysis. This fix does not introduce a QC acceptance threshold or change the LUT public API.

## Follow-up

Review the new-code reliability result on the fix PR, then merge through the normal protected-branch process after required checks and review. Keep future S1244 fixes sensitive to exact boundary semantics: `math.isclose` is suitable only when approximate equality is intended.
