# Repository Overview

Last updated: 2026-04-07

Welcome to this repository. This page serves as the entry point for navigating the repo's contents, topics, and useful external resources.

## Quick Navigation

- [Project Ideas](#project-ideas) — Browse all project concepts and innovation ideas
- [Agent & Skills Framework](#agent--skills-framework) — Hub-and-spoke team orchestration setup
- [Information & Guides](#information--guides) — Documentation and reference material
- [Assessment Templates](#assessment-templates) — Reusable assessment and review frameworks
- [Plans](#plans) — Implementation plans and orchestration run state
- [Logs](#logs) — Test ledger and documentation review logs
- [Tools & Scripts](#tools--scripts) — Utility scripts for repo automation
- [External Resources](#external-resources) — Links to external docs, tools, and references

---

## Project Ideas

See [list-ideas.md](list-ideas.md) for a complete catalog of project ideas, research concepts, and innovation opportunities explored in this repo.

---

## Agent & Skills Framework

This repository includes a complete agent team structure for Cursor/VS Code, organized as a hub-and-spoke model with specialized roles and shared procedures.

**Key Resources:**
- **Framework Overview:** [agents_and_skills/README.md](agents_and_skills/README.md)
- **Agents:** [agents_and_skills/agents/](agents_and_skills/agents/) — Roles including orchestrator, planner, coder, reviewer, tester, UX, security, and documentation
- **Skills:** [agents_and_skills/skills/](agents_and_skills/skills/) — Shared procedures for common tasks across agents

See [list-agents_and_skills.md](list-agents_and_skills.md) for detailed agent and skill descriptions.

---

## Information & Guides

A collection of documentation, guides, and reference material covering agent orchestration, setup, best practices, and technical topics.

See [list-info.md](list-info.md) for:
- Agent orchestration and delegation guides
- Setup and configuration instructions
- Reference material and technical notes

---

## Assessment Templates

Reusable templates for assessing code quality, security, functionality, documentation, and more. Use these as starting points for comprehensive project reviews.

See [list-templates-generalized.md](list-templates-generalized.md) for available assessment frameworks and their purposes.

---

## Tools & Scripts

Utility scripts for repo automation and external skill management.

See [list-tools.md](list-tools.md) for available scripts and their descriptions.

---

## Plans

The `plans/` directory holds implementation plan markdown files and the orchestrator-owned run state for multi-agent handoffs.

**Key Resources:**
- **Orchestration State:** [plans/orchestration-state.md](plans/orchestration-state.md) — Live run state template for goal, phase, assignments, and HANDOFF log
- **Plans README:** [plans/README.md](plans/README.md) — Describes folder purpose and ownership conventions

See [list-plans.md](list-plans.md) for a complete catalog.

---

## Logs

The `logs/` directory holds append-only logs from subagents, including test run records and documentation review outputs.

**Key Resources:**
- **Test Ledger:** [logs/test-ledger.md](logs/test-ledger.md) — Maintained by the **tester** subagent per the `test-ledger-runner` skill
- **Logs README:** [logs/README.md](logs/README.md) — Explains log file naming and coordination with `plans/`

See [list-logs.md](list-logs.md) for a complete catalog.

---

## External Resources

A curated collection of external links organized by topic. These reference documentation, frameworks, tools, and tutorials relevant to projects and work in this repo.

### Documentation & Guides

- [Cursor — Agent Skills](https://cursor.com/docs/context/skills) — Official skill system documentation for Cursor
- [Cursor — Subagents](https://cursor.com/docs/context/subagents) — Custom subagent definitions for Cursor
- [Cursor — Rules](https://cursor.com/docs/context/rules) — Rules and context configuration in Cursor
- [Cursor — Changelog 2.4](https://cursor.com/changelog/2-4) — Subagents and skills feature release notes
- [VS Code Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills) — VS Code Copilot skill file documentation
- [VS Code Custom Agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents) — Custom agent definitions for VS Code Copilot
- [Claude Code Skills](https://code.claude.com/docs/en/skills) — Skills documentation for Claude Code
- [Kiro Agent Skills](https://kiro.dev/docs/skills/) — Agent skill system for Kiro IDE
- [Anthropic Agent SDK](https://docs.anthropic.com/en/agent-sdk) — Anthropic's Agent SDK documentation
- [Anthropic Effective Harnesses Guide](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — Best practices for long-running agents
- [Agent Skills Standard](https://agentskills.io/) — Cross-IDE agent skills standard
- [Skills.sh Directory](https://skills.sh/) — Community skill definitions directory
- [Model Context Protocol](https://modelcontextprotocol.io/) — Official MCP specification and documentation
- [Ollama](https://ollama.com/) — Run open-source AI models locally

### Agent & AI Frameworks

- [K-Dense-AI / claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) — Scientific skills collection for Claude
- [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/harness) — LangChain long-running agent harness
- [LangSmith Platform](https://docs.langchain.com/langsmith/home) — LangChain observability and testing
- [LangGraph](https://github.com/langchain-ai/langgraph) — LangChain multi-agent orchestration framework
- [MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters) — MCP server adapters for LangChain
- [Conductor OSS](https://conductor-oss.org) — Workflow orchestration engine for long-running agents
- [Browser Use](https://github.com/browser-use/browser-use) — Browser automation for AI agents
- [Skyvern](https://github.com/Skyvern-AI/skyvern) — LLM-based browser automation
- [Cline](https://docs.cline.bot/home) — Open-source VS Code AI coding agent
- [OpenRouter](https://openrouter.ai/) — Unified API gateway across LLM providers
- [Google AI Studio](https://aistudio.google.com/) — Prompt and workflow prototyping with Gemini
- [Stitch by Google](https://stitch.withgoogle.com/) — UI prototyping from prompts and screenshots
- [MCP Server Templates](https://github.com/modelcontextprotocol/servers) — Model Context Protocol server templates
- [Figma MCP Server](https://developers.figma.com/docs/figma-mcp-server/) — MCP server for Figma design tools
- [Modal](https://modal.com/) — Serverless GPU compute for AI/ML workloads (H100/A100 cloud Python)

### Azure Services

- [Azure Foundry Browser Automation](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/browser-automation) — Browser automation tools within Azure AI Foundry agents

### GitHub & DevOps

- [GitHub Dependabot](https://docs.github.com/en/code-security/dependabot) — Automated dependency vulnerability alerts
- [GitHub Advanced Security](https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security) — GHAS code scanning and secret detection overview

### Development Tools

- [Semgrep](https://semgrep.dev) — SAST tool for static code analysis
- [Trivy](https://github.com/aquasecurity/trivy) — Vulnerability scanner for containers and code
- [TruffleHog](https://github.com/trufflesecurity/trufflehog) — Secret detection in git history
- [GitLeaks](https://github.com/gitleaks/gitleaks) — Secret scanning tool
- [Grype](https://github.com/anchore/grype) — Vulnerability scanner for container images
- [Checkov](https://github.com/bridgecrewio/checkov) — IaC security scanning
- [Mypy](https://github.com/python/mypy) — Python static type checker
- [Pyright](https://github.com/microsoft/pyright) — Python static type checker by Microsoft
- [BasedPyright](https://github.com/detachhead/basedpyright) — Community fork of Pyright with stricter defaults
- [Google Colab](https://colab.research.google.com/) — Cloud-hosted Jupyter notebooks with GPU access
- [Kaggle](https://www.kaggle.com/) — Data science notebooks, datasets, and competitions
- [Warp Agent Platform](https://docs.warp.dev/agent-platform) — Agentic features in Warp terminal
- [Playwright](https://playwright.dev/) — Cross-browser test automation framework (used by webapp-testing and ux-evaluation-web skills)

### Other

- [Hetzner](https://www.hetzner.com/) — Low-cost VPS for self-hosted AI tools
- [Vultr](https://www.vultr.com/) — VPS hosting option for open-source AI deployments
- [DigitalOcean](https://www.digitalocean.com/) — Cloud VPS and managed services
- [Elicit](https://elicit.org/) — AI research assistant for literature review
- [Research Rabbit](https://www.researchrabbit.ai/) — Paper discovery and citation mapping
- [Semantic Scholar](https://www.semanticscholar.org/) — AI-powered academic search engine
- [Connected Papers](https://www.connectedpapers.com/) — Visual citation graph for research
- [NotebookLM](https://notebooklm.google.com) — Google AI notebook for research and source summarization

---

## Contribution & Maintenance

This overview is maintained by the [update-repo-guide.md](update-repo-guide.md) prompt, which scans the repo for:
- Directory organization and content
- External links referenced in markdown files
- Updates to list files

To refresh this page with latest content, run the update-repo-guide.md prompt.
