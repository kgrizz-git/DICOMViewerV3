---
name: ux-evaluation-web
description: "Provides UX/UI evaluation standards using flows, screenshots, accessibility checks, and modern design guidance."
---

# UX evaluation

## Desktop / native GUI (Qt, WPF, Electron shell, etc.)

Use when the product is **not** primarily a web app in a browser (this repo: **PySide6 / Qt**).

1. Clarify **primary user tasks** from orchestrator or plan (e.g. open study, navigate series, run QA export, toggle privacy).
2. **Evidence without Playwright:** trace **menu paths** (`QMenu`, `QAction` text), **dialogs** (`QDialog` subclasses), **shortcuts**, **toolbar** and **context menu** entries from **code** (`grep` / semantic search). List **friction**: deep nesting, missing mnemonics, unclear defaults, modal blockers, inconsistent wording.
3. **Heuristic checklist (Qt-oriented):**
   - **Focus:** tab order sensible; Esc closes dialogs where expected; default button correct.
   - **Feedback:** progress/cancel for long work; errors actionable; empty states explained.
   - **Density & scan:** overloaded toolbars vs progressive disclosure; critical actions discoverable.
   - **Privacy / safety:** PHI-adjacent labels and indexes respect privacy mode; confirmations for destructive actions.
   - **Multi-window:** layout modes (1×1, 2×2) and sync behaviors understandable from UI cues.
4. **Screenshots / screen recording:** recommend **manual** capture for critical flows when automated capture is unavailable; reference file paths if artifacts are supplied.
5. **Do not** block on Playwright for Qt-only surfaces unless the project provides a supported GUI driver.

## Web workflow

1. Clarify **user goals**, primary flows, and breakpoints (mobile/tablet/desktop) from orchestrator or plan.
2. Prefer **Playwright** (or project’s existing E2E) to drive flows, capture **screenshots**, and note friction (clarity, affordances, errors, empty states).
3. Cross-check with **current** reputable patterns (official design systems, accessibility docs)—avoid dated blog-only advice when contradicting vendor guidance.

## Playwright setup and install scope

- Treat Playwright Test setup as **repo-scoped**: `npm init playwright@latest` initializes the current repository only.
- A machine that already has Playwright browser binaries cached may still require repo-local dependency/config setup before UX runs.
- Verify setup before assessment runs:
  - Project has Playwright dependency and config
  - Required browsers/projects are installed for target flows
  - Commands run with repo package manager conventions
- Recommended evidence-oriented commands:
  - `npx playwright test --ui`
  - `npx playwright test --debug`
  - `npx playwright test --trace on`
  - `npx playwright show-report`

## Stitch and Stitch skills workflow

- Use Stitch when UX tasks include fast concept generation, guided iteration, or extracting reusable design-system semantics.
- If Stitch skills are missing locally, pull targeted skills from `google-labs-code/stitch-skills` and add only required modules.
- Recommended starting set: `stitch-design`, `design-md`, `enhance-prompt`.
- Suggested sequence:
  1. Use prompt enhancement to structure UX intent.
  2. Generate/edit candidate screens.
  3. Extract/update DESIGN.md for consistency.
  4. Re-validate recommendations against accessibility and task-flow clarity before reporting.
- Treat Stitch artifacts as decision support; final UX recommendations should still cite observed behavior from real flows and screenshots.

## Basic Figma usage for agents

- Use Figma as a design-intent source: component structure, spacing/token conventions, and interaction expectations.
- Preferred access path is a controlled integration (for example MCP-guided workflows or approved API tooling) rather than ad hoc copy/paste.
- Minimum data to capture from Figma before implementation review:
  - Key screen/frame identifiers and target user flow
  - Component variants/states (default, hover, focus, error, disabled)
  - Typography, color, spacing, and layout constraints
  - Prototype links for transitions/interaction intent
- Safety and governance:
  - Use least-privilege credentials and approved workspaces only
  - Do not embed access tokens in repo files or logs
  - Note when design artifacts are stale versus shipped UI
- Consistent citation format for reporting: `Figma intent: [FileName > FrameName > StateName] | Runtime: [screenshot path or trace link] | Delta: [description]`

## Figma + Stitch + Playwright triage flow

1. Figma: capture intended UX states and acceptance cues.
2. Stitch (optional): generate/iterate candidate screens or DESIGN.md when direction is still fluid.
3. Playwright: validate real behavior and collect screenshots/traces from running UI.
4. Report deltas by category: visual mismatch, interaction mismatch, accessibility gap, copy/content mismatch.
5. Prioritize recommendations by user impact and implementation effort.

## Assessment dimensions

- **Usability**: task success, cognitive load, copy clarity.
- **Visual design**: type scale, spacing, color contrast, hierarchy—favor clean, functional layouts.
- **Accessibility**: focus order, labels, keyboard paths, contrast (WCAG-minded).
- **Performance perception**: obvious jank, loading states (qualitative).

## Output

- Return to orchestrator: prioritized issues, quick wins vs structural changes, and **non-binding** recommendations for stacks (only where project allows choice).
- End with the structured **HANDOFF → orchestrator** block (see skill `team-orchestration-delegation`).

## Environment

- Apply **`python-venv-dependencies`** when Playwright/Python tooling is used.
