# Agents and skills (portable copy)

This folder keeps a **portable, versioned copy** of Cursor **subagents** and **Agent Skills** you create or want to reuse across machines and repos. Cursor loads definitions from **`.cursor/agents/`** and **`.cursor/skills/`**; treat this directory as the **source of truth** you copy or sync from. `.claude/` or `.codex/` can also be used (see below).

| Location | Role |
|----------|------|
| `agents_and_skills/agents/` | One `*.md` file per subagent (YAML frontmatter + body). |
| `agents_and_skills/skills/` | One folder per skill containing `SKILL.md` (and optional `scripts/`, `reference.md`). |
| `.cursor/agents/`, `.cursor/skills/` | What Cursor actually reads in this repo—**keep in sync** with this folder (see [Syncing](#syncing-this-folder-with-cursor)). |

For how this team fits the rest of the repo (`plans`, `logs`, `assessments`), see the root **`AGENTS.md`**.

---

## Creating Cursor subagents (official pattern)

Subagents are **markdown files with YAML frontmatter**. The parent Agent can delegate to them; each runs with its **own context** (good for noisy exploration, tests, or browser work).

1. **Read the docs**: [Subagents](https://cursor.com/docs/context/subagents) (file locations, frontmatter fields, `/name` invocation, parallel runs).
2. **Choose scope**:
   - **Project**: `.cursor/agents/<name>.md` (and mirror here as `agents_and_skills/agents/<name>.md`).
   - **Global**: `~/.cursor/agents/<name>.md` for all projects.
   - Optional compatibility paths (same format): `.claude/agents/`, `.codex/agents/`—see Subagents doc for precedence.
3. **Frontmatter** (common fields): `name`, `description`, `model` (`inherit`, `fast`, or a specific model id), `readonly`, `is_background`. The **`description`** is how the parent decides **when** to delegate—make it concrete and include trigger phrases.
4. **Body**: Role instructions, boundaries (what **not** to edit), outputs, and **which skills** to read from `skills/` by folder name.
5. **Try it**: In chat, use `/your-agent-name` or ask the Agent to run that subagent on a scoped task.

**Built-in subagents** (Explore, Bash, Browser) are provided by Cursor; you do not define those files—only **custom** ones.

---

## Creating Cursor skills (official pattern)

Skills are **reusable procedure packs** the Agent can load when relevant (dynamic context), unlike always-on [Rules](https://cursor.com/docs/context/rules).

1. **Read the docs**: [Agent Skills](https://cursor.com/docs/context/skills), [changelog overview](https://cursor.com/changelog/2-4) (Skills + Subagents).
2. **Layout**: `skills/<skill-name>/SKILL.md` (optional sibling files: `reference.md`, `examples.md`, `scripts/`).
3. **Frontmatter** (required): `name` (lowercase, hyphens, ≤64 chars), `description` (≤1024 chars, **third person**, include **what** and **when**—trigger terms help discovery).
4. **Body**: Short steps, templates, tool/command hints, anti-patterns. Keep **`SKILL.md` lean** (on the order of hundreds of lines max); push depth to linked files.
5. **Do not** put personal skills in `~/.cursor/skills-cursor/`—that tree is for Cursor’s built-in skills.

Invoke skills from subagents by naming the skill folder in the subagent body (e.g. “Read `team-orchestration-delegation`”) and/or rely on Cursor’s skill discovery when the user’s task matches the skill `description`.

---

## What we maintain here (engineering team)

These files mirror **`.cursor/`** in this repository. Names match **slash** invocation (e.g. `/orchestrator`).

### Subagents (`agents/`)

| File | Purpose |
|------|---------|
| `orchestrator.md` | Reads **`plans/orchestration-state.md`** first; delegates work; approves git branch/worktree proposals and **cloud task packets**; iteration guards; **only** updates `VERSION` / `CHANGELOG.md` for release hygiene—not product code. |
| `planner.md` | Writes **`plans/*.md`** only—phased `[ ]` checklists, **task graph and gates**, questions for user, defers UI to `ux`. |
| `coder.md` | Implements plans; modular code, lints, tests when planned; updates plan checkboxes; may propose branch or cloud batch via HANDOFF. |
| `ux.md` | UX/UI assessment; Playwright and screenshots; modern accessible patterns; structured HANDOFF. |
| `reviewer.md` | Spec vs implementation; lints; merge recommendation; updates plan checklists when verified. |
| `secops.md` | Security scans; timestamped reports under **`assessments/`**; may request cloud for heavy scans. |
| `tester.md` | Runs tests; maintains **`logs/test-ledger.md`**; does not edit app/tests to “fix” failures. |
| `docreviewer.md` | Writes **`logs/docs_log-*.md`**; does not edit product source. |
| `docwriter.md` | Edits documentation; suggests docreviewer after. |

### Skills (`skills/`)

| Skill folder | Used for |
|--------------|----------|
| `team-orchestration-delegation` | **`plans/orchestration-state.md`**, HANDOFF schema, git propose/approve, cloud packets, autonomy stops, iteration guards; roster, parallelism, semver/changelog. |
| `plans-folder-authoring` | Plan templates, task graph, gates, checklist conventions under `plans/`. |
| `coder-implementation-standards` | Implementation quality, git/cloud proposals, structured handoff, plan checkbox updates. |
| `reviewer-spec-alignment` | Review steps, merge recommendation, plan sync. |
| `security-scanning-secops` | semgrep, grype, secrets scanning, workflow review, assessment file format, cloud handoff. |
| `test-ledger-runner` | Tester ledger under **`logs/test-ledger.md`**; no-edit policy on failures; cloud requests. |
| `documentation-review-write-handoff` | Docreviewer vs docwriter vs coder routing. |
| `ux-evaluation-web` | Playwright-first UX evaluation. |
| `python-venv-dependencies` | Venv detection and `python -m` usage before tooling. |
| `radiation-transport-simulation` | Monte Carlo and deterministic radiation transport workflows (EM/particle transport), including setup, validation, and uncertainty reporting. |
| `hep-montecarlo-workflows` | High-energy-physics event generation workflows for Pythia, MadGraph, and diagram-guided validation with reproducibility and uncertainty tracking. |

---

## Syncing this folder with `.cursor/`

After editing **either** tree, align the other so Cursor sees your changes:

```bash
# From repo root — example: copy portable copy → Cursor (adjust direction as needed)
rsync -a --delete agents_and_skills/agents/ .cursor/agents/
rsync -a --delete agents_and_skills/skills/ .cursor/skills/
```

Or copy the other direction if you edited under `.cursor/` first. **`--delete`** removes stray files so orphans do not linger; omit it if you intentionally keep extra files only under one side.

Playwright/Stitch sync reminder:
- Keep these mirrored files aligned whenever tooling guidance changes:
   - `.cursor/agents/ux.md` and `agents_and_skills/agents/ux.md`
   - `.cursor/agents/tester.md` and `agents_and_skills/agents/tester.md`
   - `.cursor/skills/ux-evaluation-web/SKILL.md` and `agents_and_skills/skills/ux-evaluation-web/SKILL.md`
   - `.cursor/skills/test-ledger-runner/SKILL.md` and `agents_and_skills/skills/test-ledger-runner/SKILL.md`

For **global** reuse on one machine:

```bash
rsync -a agents_and_skills/agents/ ~/.cursor/agents/
rsync -a agents_and_skills/skills/ ~/.cursor/skills/
```

For embedding in **other repos** (subtrees, submodules, sync scripts, sparse checkout) see **`info/cross-repo-reuse-agents-skills.md`**.

---

## Research and academic writing: new subagents + scientific skills

You can extend the same pattern for **literature review, methods, data analysis narrative, LaTeX/Markdown papers, grants, and reproducibility**—without mixing those concerns into the engineering roster.

### 1. Source skills from claude-scientific-skills

The **[K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills)** repository ships many **`SKILL.md`-style** packages (research, science, engineering, analysis, writing). Ways to use them:

| Approach | When to use |
|----------|-------------|
| **Vendor a subset** | Copy selected skill **folders** into `agents_and_skills/skills/<name>/` (respect licenses, e.g. MIT). Trim or split large trees so only what you need travels with the repo. |
| **Submodule or sparse checkout** | Keep upstream updates manageable; symlink or copy into `.cursor/skills/` only the skills you enable. |
| **Personal clone + rsync** | Maintain a private fork or branch; sync chosen skills into this folder periodically. |

Match Cursor’s skill layout: each skill is a directory containing **`SKILL.md`** with valid YAML frontmatter. If upstream uses a different layout, normalize to `skills/<id>/SKILL.md` before relying on discovery.

### 2. Define research subagents in `agents_and_skills/agents/`

Create **narrow** subagents so the orchestrator can route clearly—for example:

- **`literature-analyst`**: search, summarize, compare methods; output structured notes + bibliography suggestions; **readonly** where you want no file writes.
- **`methods-planner`**: study design, assumptions, statistical plan; writes only under `plans/` or `research/plans/`.
- **`academic-writer`**: prose for papers/grants; uses house style; does not fabricate citations.
- **`reproducibility-check`**: checks scripts, env files, random seeds, data provenance; read-only or log-only output.

**Frontmatter tips**

- `description`: include phrases like “literature review”, “grant narrative”, “LaTeX”, “Methods”, “statistics”, so delegation matches.
- `model`: use `inherit` for synthesis-heavy work; `fast` for retrieval-heavy listing (if quality stays acceptable).
- `readonly: true` when the agent must **not** modify data or manuscript files—only return reports.

**Body tips**

- Require **uncertainty language** where evidence is thin; forbid invented DOIs, quotes, or “personal communication” unless supplied.
- Separate **facts** (with citation placeholders) from **interpretation**.
- Point to **which scientific skills** to read (by folder name under `skills/`) for domain steps (e.g. bioinformatics, chem, stats).

### 3. Wire the orchestrator

Update **`team-orchestration-delegation`** (skill) and **`orchestrator.md`** to list research subagents and **when** to use them vs `coder`/`planner`. Keep **research** and **product engineering** delegations explicit so tool use (wet lab vs CI, IRB vs deploy) does not blur.

### 4. Optional layout for research artifacts

If you add research work beside engineering plans:

- `research/plans/` — study plans, analysis plans (similar checklist style to `plans/`).
- `research/notes/` — literature tables, annotated bibliographies.
- `logs/` — keep using timestamped logs for formal doc review of manuscripts if desired.

---

## References

- [Cursor — Subagents](https://cursor.com/docs/context/subagents)
- [Cursor — Agent Skills](https://cursor.com/docs/context/skills)
- [Cursor — Rules](https://cursor.com/docs/context/rules)
- [Cursor — Changelog 2.4 (Subagents, Skills)](https://cursor.com/changelog/2-4)
- [K-Dense-AI / claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills)
