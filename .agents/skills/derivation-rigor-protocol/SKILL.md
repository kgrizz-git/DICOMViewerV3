---
name: derivation-rigor-protocol
description: "Protocol for careful math and physics derivations with explicit notation, assumptions, cited starting equations, and line-by-line equation transitions. Use when proving statements, deriving formulas, checking symbolic manipulations, or writing technical notes where each step must be auditable."
---

# Derivation rigor protocol

Use this skill whenever the task asks for a careful mathematical or physics derivation.

## Objectives

- Make every symbol, variable, and operator unambiguous.
- Start from well-known equations, principles, or definitions.
- Prefer sources that can be cited when the origin of an equation matters.
- Show intermediate steps so each transition can be checked.
- Flag assumptions, approximations, and domain restrictions.

## Required derivation structure

1. Problem statement and target result
- State what is given and what must be derived.
- Provide the exact target equation and the meaning of each symbol.

2. Notation and symbols
- Define all symbols before first use.
- Distinguish scalars, vectors, tensors, operators, and constants.
- State units or dimensions for physical quantities when relevant.

3. Assumptions and scope
- Enumerate assumptions explicitly (for example: linear regime, smoothness, boundary conditions, coordinate chart, gauge choice, non-relativistic limit).
- Mark whether each assumption is exact, conventional, or approximation.

4. Starting equations with provenance
- Begin from canonical equations, definitions, or conservation laws.
- If the equation is standard and broadly known, name it.
- If uncertainty exists, cite a source placeholder and request confirmation.

5. Line-by-line derivation
- Number equations or maintain clear step labels.
- For each step, state the operation used (substitution, rearrangement, differentiation, integration by parts, identity, approximation, limit).
- Do not compress multiple non-trivial manipulations into one jump.

6. Validation checks
- Algebra check: no dropped signs, factors, indices, or constants.
- Dimensional check: both sides have matching units.
- Limit check: evaluate at least one known special case.
- Consistency check: compare with known form in a relevant limit.

7. Final result and interpretation
- Restate the final expression in boxed or clearly separated form.
- Explain dependence on key parameters.
- List conditions under which the result is valid.

## Writing style requirements

- Prefer explicit equations over prose-only transformations.
- Use cautious language for unverified or source-dependent statements.
- Separate facts from interpretation.
- If a step is uncertain, mark it and propose a verification path rather than guessing.

## Prohibited shortcuts

- Undefined symbols.
- Unjustified equation jumps.
- Silent approximations.
- Claims that an equation is "well known" when provenance is unclear.

## Output checklist

- [ ] All symbols defined.
- [ ] Assumptions listed.
- [ ] Starting equations identified and named.
- [ ] Intermediate equations shown with justification.
- [ ] Dimensional and limiting-case checks included.
- [ ] Final result conditions stated.
