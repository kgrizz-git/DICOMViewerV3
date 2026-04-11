---
name: derivation-challenge-review
description: "Adversarial review protocol for math and physics derivations. Use to challenge assumptions, test each equation transition, raise counterexamples, and require responses with explicit recalculation or citations before accepting a result."
---

# Derivation challenge review

Use this skill to perform a skeptical second-pass review of a derivation.

## Objectives

- Detect hidden assumptions, algebra slips, invalid limits, and notation ambiguity.
- Force explicit justification for each non-trivial transition.
- Produce a clear accept/revise verdict with required fixes.

## Review protocol

1. Parse and normalize
- Restate the claimed result and all assumptions.
- Build a symbol table and ensure each symbol is defined exactly once.

2. Check derivation integrity
- Verify every transition between successive equations.
- For each transition, label the rule used and confirm applicability.
- Identify missing intermediate steps and require expansion.

3. Challenge assumptions
- Ask whether assumptions are necessary, sufficient, and stated early.
- Probe edge cases (singular limits, boundary behavior, zero or infinite parameter limits, coordinate singularities, sign conventions).
- Test whether approximations are controlled and error terms are tracked.

4. Independent verification
- Re-derive critical segments by an alternate route when feasible.
- Run dimensional analysis and symmetry checks.
- Compare to known special cases or canonical formulas.

5. Citations and provenance
- Verify that named starting equations are standard or properly sourced.
- Flag equations that need references or stronger justification.

6. Adjudication
- Classify findings: blocking, major, minor, editorial.
- Provide required corrections and exact locations.
- Return verdict: accepted, accepted with revisions, or rejected pending fixes.

## Required output format

- Summary verdict.
- Findings table with: step reference, issue type, why it matters, required correction.
- Challenge questions the author must answer.
- Recheck criteria for final acceptance.

## Severity guide

- Blocking: invalid algebra/calculus step, dimension mismatch, contradiction with known limit, undefined symbol affecting conclusions.
- Major: missing assumptions, unjustified approximation, omitted derivation segments that hide non-trivial work.
- Minor: notation inconsistency, wording ambiguity, ordering/clarity issues.
- Editorial: style improvements that do not change correctness.

## Acceptance checklist

- [ ] No blocking issues remain.
- [ ] All major issues resolved with explicit math.
- [ ] Key equations tied to valid references or canonical identities.
- [ ] At least one independent consistency check passed.
