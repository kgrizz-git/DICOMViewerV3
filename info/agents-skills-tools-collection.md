# Agents, Skills, and Interaction Tools Collection

## Purpose

This file is a curated collection of:
- Official documentation links for agent and skill systems across IDEs
- Agent interaction tools (for example browser screenshots and recordings)
- Useful agent and skill definition repositories
- Local agent and skill definitions in this repository

This is intentionally a starter set and will grow over time.

---

## Official Docs by Platform

### Cursor
- Agent Skills: https://cursor.com/docs/context/skills
- Subagents: https://cursor.com/docs/context/subagents

Highlights:
- Skills directories: `.agents/skills/`, `.cursor/skills/`, `~/.cursor/skills/` (+ compatibility with `.claude/skills/` and `.codex/skills/`)
- Custom subagents in `.cursor/agents/` and `~/.cursor/agents/`
- Built-in subagents include Explore, Bash, Browser

### VS Code (GitHub Copilot)
- Agents overview: https://code.visualstudio.com/docs/copilot/agents/overview
- Agent Skills: https://code.visualstudio.com/docs/copilot/customization/agent-skills
- Custom agents: https://code.visualstudio.com/docs/copilot/customization/custom-agents

Highlights:
- Skills directories include `.github/skills/`, `.claude/skills/`, `.agents/skills/`
- Custom agents use `.agent.md` and support scoped tools, model selection, and subagent control

### Claude Code / Agent Skills ecosystem
- Claude skills docs: https://code.claude.com/docs/en/skills
- Anthropic skills repository: https://github.com/anthropics/skills
- Agent Skills standard: https://agentskills.io/

Highlights:
- Strong skills-first workflow
- Subagent execution patterns are available in Claude skills configuration

### Kiro
- Agent Skills: https://kiro.dev/docs/skills/
- Steering: https://kiro.dev/docs/steering/
- Hooks: https://kiro.dev/docs/hooks/
- CLI custom agents: https://kiro.dev/docs/cli/custom-agents/creating/

Highlights:
- Skills directories: `.kiro/skills/` and `~/.kiro/skills/`
- Steering directories: `.kiro/steering/` and `~/.kiro/steering/`
- Supports `AGENTS.md` in steering locations and workspace root
- CLI custom agents are JSON configurations, typically in `.kiro/agents/` or `~/.kiro/agents/`

### Antigravity
- Agent: https://antigravity.google/docs/agent
- Skills: https://antigravity.google/docs/skills
- Browser Subagent: https://antigravity.google/docs/browser-subagent
- Screenshots artifacts: https://antigravity.google/docs/screenshots
- Browser recordings artifacts: https://antigravity.google/docs/browser-recordings
- Agent Manager: https://antigravity.google/docs/agent-manager

Highlights:
- Skills directories: `<workspace-root>/.agents/skills/`, `~/.gemini/antigravity/skills/`
- Backward compatibility: `<workspace-root>/.agent/skills/`
- Browser subagent is specialized and can create screenshot/recording artifacts
- Agent Manager supports multi-workspace, multi-agent oversight

### Warp
- Getting started (Warp + Oz): https://docs.warp.dev/getting-started/getting-started-with-warp-and-oz
- Agent platform overview: https://docs.warp.dev/agent-platform

Highlights:
- Local and cloud agent workflows
- MCP support and rules documented
- Good environment for agent orchestration and CLI-based workflows

### Cline
- Documentation home: https://docs.cline.bot/home

Highlights:
- Explicit user approval model for actions
- Works in editor and terminal loops

---

## Agent Interaction Tools (Cross-IDE)

### Browser interaction and review artifacts
- Antigravity browser subagent supports browser control plus screenshots and recordings artifacts:
  - https://antigravity.google/docs/browser-subagent
  - https://antigravity.google/docs/screenshots
  - https://antigravity.google/docs/browser-recordings

### Browser task execution in agent workflows
- Cursor Browser subagent (context-isolated browser work):
  - https://cursor.com/docs/context/subagents
- VS Code integrated browser testing support for agents (experimental in local agent workflows):
  - https://code.visualstudio.com/docs/copilot/agents/overview

### Triggered automation hooks
- Kiro hooks for event-driven agent actions:
  - https://kiro.dev/docs/hooks/

---

## Cool Agent/Skill Definitions (External)

### Claude Scientific Skills (requested starter section)
- Primary repo: https://github.com/K-Dense-AI/claude-scientific-skills
- Context from search results (for discovery): https://github.com/search?q=claude-scientific-skills&type=repositories

Notes:
- Do not enumerate all skills yet
- Use this section to track candidate skills for targeted import/adaptation

### Vetted candidate imports (high-reputation / safer defaults)

Screening criteria used in this file:
- Source is official platform docs, official extension marketplace entries, or maintained public repos from recognized teams
- Prefer mature/open projects with clear license and active maintenance
- Prefer read-only or bounded-scope tools for initial adoption
- Explicitly flag anything experimental, low-adoption, or unclear provenance

Top candidates from prior shortlist (kept, now safety-vetted):

| Candidate | Why keep | Source | Reputation / safety note |
|---|---|---|---|
| exploratory-data-analysis | Broad scientific data triage and quality checks | https://github.com/K-Dense-AI/claude-scientific-skills | K-Dense flagship repo, explicit skill metadata and docs |
| literature-review | Structured, multi-source literature workflows | https://github.com/K-Dense-AI/claude-scientific-skills | High utility for research; verify per-skill license field |
| scientific-writing | Publication-quality writing workflows | https://github.com/K-Dense-AI/claude-scientific-skills | High maturity in repo docs/examples |
| scientific-critical-thinking | Bias checks and methodological rigor | https://github.com/K-Dense-AI/claude-scientific-skills | Good safety value: improves epistemic quality |
| scientific-visualization | Better figures and communication quality | https://github.com/K-Dense-AI/claude-scientific-skills | Includes best-practice guidance |
| database-lookup | Multi-database retrieval backbone | https://github.com/K-Dense-AI/claude-scientific-skills | Use API key hygiene and source attribution |
| paper-lookup | Paper discovery + metadata workflows | https://github.com/K-Dense-AI/claude-scientific-skills | Good for citation-grounded outputs |
| hypothesis-generation | Research ideation and planning | https://github.com/K-Dense-AI/claude-scientific-skills | Keep with human review checkpoints |
| markdown-mermaid-writing | Strong documentation and workflow maps | https://github.com/K-Dense-AI/claude-scientific-skills | Open provenance; explicit skill source metadata |
| get-available-resources | Resource-aware execution planning | https://github.com/K-Dense-AI/claude-scientific-skills | Reduces risky over-allocation workflows |

---

## Interest-Mapped Scientific Spotlight (With Source + Trust/Safety)

### Physics, Mathematics, and Theory

| Interest | Skill / package to spotlight | Source | Reputation / safety note |
|---|---|---|---|
| Physics (general), high-energy physics-adjacent symbolic workflows | sympy | https://github.com/K-Dense-AI/claude-scientific-skills | Mature OSS ecosystem; exact symbolic math reduces numerical ambiguity |
| Physics and astronomy pipelines | astropy | https://github.com/K-Dense-AI/claude-scientific-skills | Widely used scientific Python standard |
| Quantum / theoretical computing tracks | qiskit, pennylane, cirq, qutip | https://github.com/K-Dense-AI/claude-scientific-skills | Reputable frameworks; use official SDK docs per framework |
| Graph theory / network science | networkx | https://github.com/K-Dense-AI/claude-scientific-skills | Highly established OSS graph toolkit |
| Group theory / abstract algebra / topology (adjacent support) | sympy advanced topics + networkx topology utilities | https://github.com/K-Dense-AI/claude-scientific-skills | Good starting point; for deep pure math, add dedicated CAS skill later |

### Radiology, MRI/fMRI, and Medical Imaging

| Interest | Skill / package to spotlight | Source | Reputation / safety note |
|---|---|---|---|
| Radiology workflows / DICOM | pydicom | https://github.com/K-Dense-AI/claude-scientific-skills | Core radiology format support; keep PHI controls strict |
| Medical imaging and digital pathology | pathml, histolab | https://github.com/K-Dense-AI/claude-scientific-skills | Useful for WSI/pathology; validate output clinically |
| MRI/fMRI data handling | NIfTI workflow via EDA references (nibabel/nilearn mentions) | https://github.com/K-Dense-AI/claude-scientific-skills | Strong research utility; clinical claims require expert review |
| Open radiology datasets | Imaging Data Commons (NCI imaging) | https://github.com/K-Dense-AI/claude-scientific-skills | Reputable public biomedical source; confirm each dataset license/DUA |

Suggested additional medical imaging dataset skills to add (new):
- OpenNeuro access skill (fMRI/MRI research datasets): https://openneuro.org/
- TCIA-native query skill (if distinct from IDC workflow): https://www.cancerimagingarchive.net/
- PhysioNet + MIMIC retrieval helper skill: https://physionet.org/

### Academic Research and Writing

| Interest | Skill / package to spotlight | Source | Reputation / safety note |
|---|---|---|---|
| Academic research discovery | research-lookup, paper-lookup | https://github.com/K-Dense-AI/claude-scientific-skills | Good source breadth; cite provenance in outputs |
| Literature synthesis | literature-review | https://github.com/K-Dense-AI/claude-scientific-skills | Use quality checks + confidence tagging |
| Academic writing quality | scientific-writing, citation-management | https://github.com/K-Dense-AI/claude-scientific-skills | Strong formatting + citation hygiene support |
| Research rigor | scientific-critical-thinking, scholar-evaluation | https://github.com/K-Dense-AI/claude-scientific-skills | Reduces methodological/interpretation risk |

### AI, ML, and Long-Horizon Coding/Orchestration

| Interest | Skill / package to spotlight | Source | Reputation / safety note |
|---|---|---|---|
| AI/ML modeling | scikit-learn, pytorch-lightning, shap, pymc, statsmodels | https://github.com/K-Dense-AI/claude-scientific-skills | Established OSS stack; strong documentation |
| Long-horizon multi-step workflows | what-if-oracle, consciousness-council, scientific-brainstorming | https://github.com/K-Dense-AI/claude-scientific-skills | Good for planning; enforce human checkpoints |
| Resource-aware orchestration | modal, get-available-resources, optimize-for-gpu | https://github.com/K-Dense-AI/claude-scientific-skills | Good ops hygiene; watch cloud credential boundaries |

### Front-end Design, Music, Audio Engineering

Current state:
- No single “music/audio engineering” flagship skill is clearly highlighted in current K-Dense top-level docs.

Recommended new skills to add (high-reputation sources):
- torchaudio skill (PyTorch audio ML): https://pytorch.org/audio/stable/index.html
- librosa skill (music/audio analysis): https://librosa.org/
- Essentia skill (music information retrieval): https://essentia.upf.edu/
- pyroomacoustics skill (acoustics/sound-field simulation): https://pyroomacoustics.readthedocs.io/

Safety notes for audio/music domain:
- Prefer deterministic transforms and reproducible seeds in DSP workflows
- Keep generated audio assets provenance-tagged for licensing and attribution

---

## UI/GUI Interactivity and Design Tooling (Vetted)

### VS Code extensions (higher-trust picks)

| Extension | ID | Why include | Reputation / safety note |
|---|---|---|---|
| Playwright Test for VS Code | ms-playwright.playwright | First-party browser automation/testing workflow in editor | Microsoft publisher, very high adoption |
| Playwright Trace Viewer | ryanrosello-og.playwright-vscode-trace-viewer | Debug trace artifacts for agent-generated browser flows | Useful bounded tool; review maintainer before broad rollout |
| BrowserStack | browserstackcom.browserstack-vscode | Cross-browser verification at scale | Established vendor; enterprise-friendly |
| LambdaTest cloud extension | lambdatest.lambdatest-cloud | Cross-browser and automation cloud support | Established vendor; review data egress policy |
| Builder | builder.builder | UI design-to-code productivity | Known design/dev platform; verify project policy fit |
| CopyCat Figma to React | copycatdev.copycat-figma-to-react | Fast Figma-to-React bootstrap | Community extension; evaluate generated code quality |

### MCP/UI interaction servers (high-confidence)

| Tool | Source | Reputation / safety note |
|---|---|---|
| Playwright MCP server | https://github.com/microsoft/playwright-mcp | Microsoft-backed; strong baseline for browser automation |
| Chrome DevTools (CLI + Skills *preferred*) | https://github.com/ChromeDevTools/chrome-devtools-mcp | Official Chrome DevTools org; excellent runtime introspection. **Prefer CLI+Skills over MCP for token efficiency** |
| Figma MCP guide | https://github.com/figma/mcp-server-guide | Official Figma guidance; design-context integration |
| Storybook MCP addon | https://github.com/storybookjs/addon-mcp | Strong for UI component testing/documentation loops |

---

## Playwright Deep Dive (docs + microsoft/playwright)

Status:
- Confirmed from official docs and repo README: Playwright supports four primary usage paths: Playwright Test, Playwright Library, Playwright MCP, and Playwright CLI.
- Cross-browser model is still one API for Chromium, Firefox, and WebKit, with strong first-party tooling for VS Code and trace-based debugging.

Primary references:
- Docs home: https://playwright.dev/
- Installation / intro: https://playwright.dev/docs/intro
- Writing tests: https://playwright.dev/docs/writing-tests
- Code generation: https://playwright.dev/docs/codegen
- Trace viewer: https://playwright.dev/docs/trace-viewer
- Best practices: https://playwright.dev/docs/best-practices
- GitHub repo: https://github.com/microsoft/playwright

When to choose each Playwright mode:

| Mode | Install/start | Best for |
|---|---|---|
| Playwright Test | `npm init playwright@latest` | End-to-end test suites with retries, projects, reporters, and CI integration |
| Playwright Library | `npm i playwright` | Browser automation scripts (screenshots, PDF, scripted flows) without the test runner |
| Playwright MCP | `npx @playwright/mcp@latest` | Agent-driven browser control via MCP and accessibility-tree interactions |
| Playwright CLI | `npm i -g @playwright/cli@latest` | Command-based browser automation optimized for coding-agent workflows |

Install scope (important):
- `npm init playwright@latest` is project/repo-scoped. Run it in each repository where you want Playwright Test setup (`package.json`, config, test folders, CI workflow scaffolding).
- Browser binaries are machine-cached and often reused across repos, so repeated setup usually does not re-download everything.
- Global installs are mainly for machine-level agent tooling (for example `@playwright/cli` global install). They do not replace repo-level Playwright Test dependency/version pinning.

Fast start for Playwright Test (practical):
1. Initialize: `npm init playwright@latest`
2. Run all tests: `npx playwright test`
3. Run with browser visible: `npx playwright test --headed`
4. Open UI mode (watch + time travel debugging): `npx playwright test --ui`
5. Open report: `npx playwright show-report`

Minimal first test pattern:
```ts
import { test, expect } from '@playwright/test';

test('homepage has expected title', async ({ page }) => {
  await page.goto('https://playwright.dev/');
  await expect(page).toHaveTitle(/Playwright/);
});
```

How to use Playwright effectively (from docs):
- Prefer user-facing locators (`getByRole`, `getByLabel`, `getByText`, `getByTestId`) over brittle CSS/XPath chains.
- Rely on web-first assertions (`await expect(locator).toBeVisible()`) instead of manual immediate checks.
- Keep tests isolated (fresh browser context per test) and use setup/auth state reuse when needed.
- Use `codegen` or VS Code record tools to bootstrap flows, then refactor generated code for readability and resiliency.
- Mock or route third-party dependencies you do not control to reduce flaky failures.

Codegen workflows (two reliable options):
- Inspector flow: `npx playwright codegen https://your-app-url`
- VS Code flow: use Playwright extension -> Record new / Record at cursor / Pick locator

Debugging and failure triage workflow:
1. Local debug run: `npx playwright test --debug`
2. Capture traces during local development: `npx playwright test --trace on`
3. Use CI-friendly default in config: `trace: 'on-first-retry'`
4. Inspect a trace: `npx playwright show-trace path/to/trace.zip`
5. Share/inspect in browser when needed: https://trace.playwright.dev/

CI guidance (high-value defaults):
- Run on every PR/commit.
- Keep Linux CI runners unless platform-specific validation is required.
- Install only required browsers on CI to reduce time/cost (for example Chromium-only jobs).
- Use sharding for large suites (`--shard=1/3`, etc.) and keep retries intentional.

Agent + MCP note:
- For agentic browser tasks, Playwright MCP provides structured accessibility-tree interaction and deterministic element references.
- For command-driven agent workflows with lower token overhead, Playwright CLI is a strong complement.

Trust and maintenance notes (repo-specific):
- Repository: `microsoft/playwright`
- License: Apache-2.0
- Strong maturity signals: large contributor base, frequent releases, active issue/PR flow.
- Operational recommendation: pin Playwright versions in CI and update regularly with release-note review.

Quickstart checklist (compact):
1. Choose mode: Test, Library, MCP, or CLI
2. Install and run a smoke test against one critical user flow
3. Add resilient locators and web-first assertions
4. Enable trace capture on retries in CI
5. Add browser matrix only where it improves signal (not by default everywhere)

---

## Chrome DevTools Deep Dive (ChromeDevTools/chrome-devtools-mcp)

Status:
- Confirmed from official Chrome DevTools docs: Chrome DevTools provides agent-driven browser automation, DevTools inspection, Lighthouse audits, and performance tracing through **both CLI+Skills and MCP server** modes.
- **Token efficiency**: Both ship in the same package. Official docs describe CLI+Skills as "a more token-efficient alternative" for typical use cases.
- **Task-dependent choice**: Prefer CLI+Skills for one-off script generation and batch tasks; consider MCP for interactive debugging and persistent browser state across multiple agent interactions.
- Official docs: https://developer.chrome.com/docs/devtools/agents
- GitHub repo: https://github.com/ChromeDevTools/chrome-devtools-mcp

Primary capabilities:
- **Browser automation**: navigate, interact with page elements, fill forms, capture screenshots/recordings
- **Lighthouse audits**: performance, accessibility, SEO, best practices analysis
- **Performance tracing**: record and analyze runtime performance with detailed traces
- **DevTools introspection**: access Console, Network, Coverage, and other DevTools panels
- **Real Chrome instance**: validates agent code against actual browser behavior

Install by IDE (CLI + Skills recommended):

| IDE | Installation command (CLI + Skills) |
|---|---|
| VS Code + Copilot | `npm install --save-dev @chrome-devtools/mcp && npx chrome-devtools-mcp setup-skills` |
| Cursor | `/add-plugin chrome-devtools` then select MCP + Skills setup |
| Gemini CLI | `gemini extensions install --auto-update https://github.com/ChromeDevTools/chrome-devtools-mcp` |
| Claude Code | `claude plugin install chrome-devtools@mcp-server` |
| Codex | `codex mcp add chrome-devtools -- npx chrome-devtools-mcp@latest` |
| Cline | Configure in `.cline/mcp-servers.json`: `{ "chrome-devtools": { "command": "npx", "args": ["chrome-devtools-mcp@latest"] } }` |

If MCP-only needed (less common): use `npx chrome-devtools-mcp@latest` instead of CLI+skills install.

How to choose: CLI + Skills vs MCP

| Mode | When to use | Token overhead | Best for |
|---|---|---|---|
| **CLI + Skills** | Default for one-off tasks and script generation | **Lower** (skill docs + written script) | Automation scripts, form filling, screenshot capture, Lighthouse audits, batch tasks, simple/short interactions |
| **MCP** | Interactive or session-persistent workflows | Higher (full tool schema in context per call) | Multi-turn debugging, continuous browser state across agent requests, complex interactive patterns where agent frequently changes strategy |
| **Either** | Simple isolated tasks | Comparable | Either works; pick based on repo setup and agent workflow model |

Example workflows (CLI + Skills):

1. **Lighthouse performance audit**:
   ```
   Audit the performance of https://example.com using Lighthouse.
   ```

2. **Form filling with screenshot**:
   ```
   Navigate to https://example.com/signup, fill out the form (name, email, password),
   submit, and take a screenshot of the confirmation page.
   ```

3. **Performance trace and analysis**:
   ```
   Visit developer.chrome.com and run a search for "devtools" while recording a
   performance trace. Analyze the trace and suggest performance improvements.
   ```

4. **Screenshot on multiple pages**:
   ```
   Navigate through the onboarding flow (home → features → pricing → about),
   take a screenshot of each, and report any broken links or 404s.
   ```

Core tools (both CLI+Skills and MCP expose these):
- `navigate_to` – Open a URL in a fresh or existing browser window
- `wait_for_navigation` – Wait for a page navigation to complete
- `interact_with_element` – Click, type, select, scroll on page elements
- `screenshot` – Capture current viewport
- `pdf` – Export page as PDF
- `run_lighthouse_audit` – Performance, accessibility, SEO report
- `record_trace` – Collect runtime performance trace
- `access_devtools` – Query Console errors, Network headers, Coverage stats

Debugging and troubleshooting:
- If the agent cannot find an element, request a screenshot first, then describe the element's location or text content.
- Performance traces require a stable, idle page; navigate and wait for load before recording.
- Lighthouse audits work best on public URLs; local dev servers need `--allow-local-urls` in config.

Setup notes:
- **Port defaults**: DevTools server typically runs on `http://localhost:9222` for local Chrome instances.
- **Headless vs headed**: CLI+Skills can control headless (faster, less resource overhead) or headed (visible browser for debugging) modes.
- **Installation scope**: Chrome DevTools package is repo/project-scoped if installed via npm; binaries cache shared across projects.

Trust and maintenance (repo-specific):
- Repository: `ChromeDevTools/chrome-devtools-mcp`
- License: Apache-2.0
- Official backing: Google Chrome DevTools team; first-party source
- Strong maturity signals: official documentation, active GitHub issues, regular updates
- Operational recommendation: pin to specific version in package.json; test new DevTools releases in a feature branch before rolling out to CI.

---

## Figma MCP Server Setup (figma/mcp-server-guide)

Status:
- Confirmed from the official Figma guide repo (`figma/mcp-server-guide`): the Figma MCP server provides design context, variable/token extraction, code generation, and write-to-canvas capabilities directly in your agent workflow.
- Server URL: `https://mcp.figma.com/mcp` (Streamable HTTP; no local process required)
- Rate limits apply: Starter plan / View-only seats limited to 6 tool calls per month; Dev or Full seats on paid plans receive Tier 1 REST API rate limits.

Primary references:
- Guide repo: https://github.com/figma/mcp-server-guide
- Developer docs: https://developers.figma.com/docs/figma-mcp-server/
- Help article: https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Dev-Mode-MCP-Server

Setup by IDE:

| IDE | How to connect |
|---|---|
| VS Code | `⌘ Shift P` → MCP: Add Server → HTTP → URL `https://mcp.figma.com/mcp` → server ID `figma`; requires GitHub Copilot |
| Cursor | `/add-plugin figma` in agent chat; installs MCP config, skills, and rules |
| Claude Code | `claude plugin install figma@claude-plugins-official` |
| Gemini CLI | `gemini extensions install https://github.com/figma/mcp-server-guide` then `/mcp auth figma` |
| Other (Streamable HTTP) | Add `{ "mcpServers": { "figma": { "url": "https://mcp.figma.com/mcp" } } }` to mcp config |

Confirm connection: ask the agent to call `whoami` or type `#get_design_context`. If tools are not listed, restart the IDE.

Core tools:

| Tool | Best for |
|---|---|
| `get_design_context` | Structured React + Tailwind representation of a Figma selection; translate into any framework via prompt |
| `get_variable_defs` | Extract color, spacing, and typography tokens/variables from a selection |
| `get_screenshot` | Visual fidelity reference alongside code context |
| `get_metadata` | High-level XML layer map for large designs; use before targeted `get_design_context` calls |
| `get_code_connect_map` | Map Figma node IDs to existing codebase components for reuse |
| `create_design_system_rules` | Generate a rule file for agent output aligned to your design system (run once, save to rules dir) |
| `search_design_system` | Find components, variables, or styles in connected design libraries |
| `use_figma` (remote only) | Write to canvas: create/edit frames, components, variables, styles |
| `generate_diagram` | Create FigJam diagrams from Mermaid or natural language |

How to use Figma MCP effectively:
- Copy a Figma frame or layer URL and include it in your prompt; the MCP server extracts the node ID.
- Default output is React + Tailwind; adjust via prompt: "Generate in Vue", "Use components from src/components/ui", "Generate iOS SwiftUI code".
- For large designs, call `get_metadata` first for the layer map, then call `get_design_context` on specific nodes only.
- Always call `get_screenshot` alongside `get_design_context` to preserve visual fidelity.
- Run `create_design_system_rules` once per project; save output to `.cursor/rules/` or equivalent.
- Break large selections into components or logical sections for more reliable results.

Figma artifact citation format (for consistent reporting across agents):
- Frame reference: `[FileName] > [FrameName] > [StateName]` (example: `Dashboard.fig > MainView > Empty state`)
- Evidence entry: `Figma intent: [file > frame > state] | Runtime: [screenshot path or trace link] | Delta: [description]`

Best practices for Figma file structure (improves MCP code quality):
- Use components for anything reused; use variables rather than hardcoded values.
- Use semantic layer names (`CardContainer`, not `Group 5`).
- Apply Auto Layout to communicate responsive intent.
- Set up Code Connect to link Figma components to codebase components.

Authentication and security:
- Authentication is handled interactively on first use; no tokens need to be embedded in config or code.
- Do not commit Figma tokens or session data to repos or logs.
- Use least-privilege workspace access; review rate limits before building high-frequency agent workflows.

Trust notes:
- Source: `figma/mcp-server-guide` (official Figma organization repo, Apache-2.0).
- Write-to-canvas (`use_figma`) is currently free during beta but will eventually be a usage-based paid feature.

Quickstart checklist (compact):
1. Connect via IDE-specific steps above
2. Confirm: ask agent to call `whoami` or `#get_design_context`
3. Copy a Figma frame URL and ask the agent to implement from it
4. Run `create_design_system_rules` once; save output to rules directory
5. Set up Code Connect for consistent component reuse

---

## Google Stitch + design.md notes (confirmed sources)

Status:
- Confirmed via official Google post (Mar 18, 2026): Stitch explicitly supports DESIGN.md and highlights Stitch MCP server, SDK, and skills integrations.
- The public `google-labs-code/stitch-skills` repo is a practical, multi-skill library built around Stitch MCP and the Agent Skills open standard.

Primary references:
- Google announcement: https://blog.google/innovation-and-ai/models-and-research/google-labs/stitch-ai-ui-design/
- Stitch docs root: https://stitch.withgoogle.com/docs?pli=1
- Stitch DESIGN.md overview: https://stitch.withgoogle.com/docs/design-md/overview/?pli=1
- Stitch DESIGN.md format: https://stitch.withgoogle.com/docs/design-md/format/?pli=1
- Stitch MCP setup: https://stitch.withgoogle.com/docs/mcp/setup/?pli=1
- Stitch MCP guide: https://stitch.withgoogle.com/docs/mcp/guide/?pli=1
- Stitch SDK tutorial: https://stitch.withgoogle.com/docs/sdk/tutorial/?pli=1
- Stitch skills repo: https://github.com/google-labs-code/stitch-skills

What the Stitch skills repo gives you (high-value summary):
- A coherent skill set around the Stitch lifecycle: prompting, generation/editing, design-system extraction, React conversion, and demo-video production.
- Skills are installable one-by-one with `npx skills add ...` and can be mixed by workflow.
- Skills use explicit MCP retrieval patterns (`list_projects`, `list_screens`, `get_screen`) before generation/edit calls.
- Repo structure is standardized (`SKILL.md`, `resources/`, `examples/`, optional scripts), making it easier to vet and adapt.

Core Stitch skills worth using first:

| Skill | Install command | Best use |
|---|---|---|
| stitch-design | `npx skills add google-labs-code/stitch-skills --skill stitch-design --global` | End-to-end design generation/editing with prompt enhancement and DESIGN.md context |
| design-md | `npx skills add google-labs-code/stitch-skills --skill design-md --global` | Extract a semantic design system from existing Stitch screens into DESIGN.md |
| enhance-prompt | `npx skills add google-labs-code/stitch-skills --skill enhance-prompt --global` | Turn vague UI intent into structured, Stitch-optimized prompts |
| stitch-loop | `npx skills add google-labs-code/stitch-skills --skill stitch-loop --global` | Baton-style autonomous multi-page site build loops |
| react-components | `npx skills add google-labs-code/stitch-skills --skill react:components --global` | Convert Stitch screens into React component systems |
| remotion | `npx skills add google-labs-code/stitch-skills --skill remotion --global` | Create walkthrough videos from Stitch project screens |

Recommended execution sequence (practical):
1. Use `enhance-prompt` to structure your initial screen prompt.
2. Use `stitch-design` to generate/edit target screens via Stitch MCP.
3. Use `design-md` to write `.stitch/DESIGN.md` as the project source of truth.
4. Feed that DESIGN.md into later prompts/edits for consistency.
5. Export implementation via `react:components` and optionally demo via `remotion`.

Design.md concept note:
- DESIGN.md is source-supported for Stitch specifically; treat it as a Stitch-defined interchange format, not a universal cross-vendor standard.
- In Stitch-oriented workflows, include both descriptive language and exact hex values (semantic + precise).
- It still maps cleanly to markdown-based rule/workflow approaches in other agent systems:
  - Antigravity rules/workflows markdown model: https://antigravity.google/docs/rules-workflows
  - Cursor markdown rule files in .cursor/rules: https://cursor.com/docs/context/rules
  - VS Code markdown customization/instructions model: https://code.visualstudio.com/docs/copilot/customization/custom-instructions

Operational guidance:
- Use skills CLI discovery first: `npx skills add google-labs-code/stitch-skills --list`.
- When calling Stitch MCP from agent logic, discover the active tool prefix first, then call project/screen endpoints.
- Prefer iterative edits (`edit_screens`) over full re-generation once direction is mostly correct.
- If adopting DESIGN.md internally across IDEs, define translation rules and map fields to each platform's loader.
- Keep a compact machine-actionable schema (goals, UX constraints, component map, states, accessibility checks, acceptance tests).

Trust and maintenance notes (repo-specific):
- License: Apache-2.0.
- Maintainer org: `google-labs-code` (strong provenance signal, but still treat as non-productized OSS).
- Project disclaimer in repo: "This is not an officially supported Google product."
- As with any MCP-powered workflow, apply least privilege and keep credential scope narrow.

Quickstart checklist (compact):
1. `npx skills add google-labs-code/stitch-skills --list`
2. Install: `stitch-design`, `design-md`, `enhance-prompt`
3. `list_projects` -> select `projectId`
4. Generate/edit screens with `stitch-design`
5. Write `.stitch/DESIGN.md` with `design-md`
6. Reuse DESIGN.md context in every subsequent prompt
7. Optional: export with `react:components`, demo with `remotion`

---

## Safety and Trust Checklist for New Skill/Tool Imports

- Verify publisher/owner identity and repository provenance
- Confirm license at both repo and per-skill/package level
- Prefer tools with explicit scope and least-privilege permissions
- For browser/GUI automation, sandbox credentials and use allowlists
- For clinical/medical workflows, enforce human-in-the-loop review before decisions
- Pin versions and record hashes/commit SHAs for reproducibility

### Other useful starter repos
- Anthropic reference skills: https://github.com/anthropics/skills
- Open science skills (community): https://github.com/justaddcoffee/open-science-skills

---

## Local Agents and Skills in This Repository

### Local guide/mirror
- [agents_and_skills/README.md](agents_and_skills/README.md)

### Agents in this repo
- [agents_and_skills/agents/orchestrator.md](agents_and_skills/agents/orchestrator.md)
- [agents_and_skills/agents/planner.md](agents_and_skills/agents/planner.md)
- [agents_and_skills/agents/coder.md](agents_and_skills/agents/coder.md)
- [agents_and_skills/agents/reviewer.md](agents_and_skills/agents/reviewer.md)
- [agents_and_skills/agents/secops.md](agents_and_skills/agents/secops.md)
- [agents_and_skills/agents/tester.md](agents_and_skills/agents/tester.md)
- [agents_and_skills/agents/ux.md](agents_and_skills/agents/ux.md)
- [agents_and_skills/agents/docreviewer.md](agents_and_skills/agents/docreviewer.md)
- [agents_and_skills/agents/docwriter.md](agents_and_skills/agents/docwriter.md)

### Skills in this repo
- [agents_and_skills/skills/team-orchestration-delegation/SKILL.md](agents_and_skills/skills/team-orchestration-delegation/SKILL.md)
- [agents_and_skills/skills/plans-folder-authoring/SKILL.md](agents_and_skills/skills/plans-folder-authoring/SKILL.md)
- [agents_and_skills/skills/coder-implementation-standards/SKILL.md](agents_and_skills/skills/coder-implementation-standards/SKILL.md)
- [agents_and_skills/skills/reviewer-spec-alignment/SKILL.md](agents_and_skills/skills/reviewer-spec-alignment/SKILL.md)
- [agents_and_skills/skills/security-scanning-secops/SKILL.md](agents_and_skills/skills/security-scanning-secops/SKILL.md)
- [agents_and_skills/skills/test-ledger-runner/SKILL.md](agents_and_skills/skills/test-ledger-runner/SKILL.md)
- [agents_and_skills/skills/ux-evaluation-web/SKILL.md](agents_and_skills/skills/ux-evaluation-web/SKILL.md)
- [agents_and_skills/skills/documentation-review-write-handoff/SKILL.md](agents_and_skills/skills/documentation-review-write-handoff/SKILL.md)
- [agents_and_skills/skills/python-venv-dependencies/SKILL.md](agents_and_skills/skills/python-venv-dependencies/SKILL.md)

---

## Tool availability and failure reporting convention

This convention applies to all subagents in this team and should be enforced at the agent and skill level.

**Subagent rule** (applies to: coder, planner, tester, ux, reviewer, secops, docreviewer, docwriter):
If any required tool—package, MCP server, skill, API endpoint, command, or program—is not available or fails at invocation, report the following before continuing:
1. The exact tool name (for example: `semgrep`, `npx playwright test`, the Stitch MCP server, the Figma MCP server, a specific skill file)
2. The error or unavailability reason (not installed, auth failure, server unreachable, missing skill file, etc.)
3. The impact on the current task (which step is blocked, degraded, or must be skipped)
4. A suggested remediation if obvious (install command, auth step, workaround)

Do not silently substitute a different tool or skip the step without reporting.

**Orchestrator rule:**
When any subagent reports a tool as unavailable or failed, relay the complete report to the **user** immediately—tool name, failure reason, affected task, and suggested fix if known. Do not absorb tool failures silently or attempt to route around them without surfacing the issue.

Examples of reports that should be surfaced to the user:
- "Playwright is not installed in this repo (`npx playwright test` fails with 'Command not found'). UX flow capture is blocked. Suggested fix: `npm init playwright@latest`."
- "The Figma MCP server returned 403 (authentication expired). Design context extraction is unavailable. Suggested fix: reconnect via IDE MCP settings."
- "The `stitch-design` skill is not present locally. Stitch-based UX generation is unavailable. Pull from `google-labs-code/stitch-skills` if needed."
- "The `semgrep` command is not found. Security scanning is blocked. Suggested fix: `pip install semgrep` or `brew install semgrep`."

---

## Backlog: What to Add Next

- A short compatibility matrix focused only on agent definitions and skill directory formats
- A curated "Top 10 importable skills" list with one-line rationale each
- A section mapping equivalent concepts across tools:
  - Skill vs steering vs rules vs prompt file
  - Agent vs subagent vs mode
- A section on safe automation defaults (permissions, approvals, sandboxing)
