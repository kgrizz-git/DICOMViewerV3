# VS Code Copilot Customization Reference

Brief reference note for the main VS Code Copilot customization file types.

## Prompt Files

- Reference: https://code.visualstudio.com/docs/copilot/customization/prompt-files
- Key point: Prompt files are reusable slash commands for one-off or repeatable tasks.
- Key point: They use `.prompt.md` files, typically in `.github/prompts/` for workspace scope.
- Key point: Frontmatter can set `agent`, `tools`, `model`, and input hints.
- Key point: Best for lightweight task templates, not always-on behavior.

## Custom Instructions

- Reference: https://code.visualstudio.com/docs/copilot/customization/custom-instructions
- Key point: Custom instructions shape Copilot behavior automatically across chats or for matching files.
- Key point: Use `.github/copilot-instructions.md` or `AGENTS.md` for always-on rules.
- Key point: Use `.instructions.md` files for conditional rules via `applyTo` globs.
- Key point: Best for project conventions, architecture rules, and coding standards.

## Custom Agents

- Reference: https://code.visualstudio.com/docs/copilot/customization/custom-agents
- Key point: Custom agents define a reusable persona with its own tools, model choices, and instructions.
- Key point: They use `.agent.md` files, usually in `.github/agents/`.
- Key point: Frontmatter can restrict tools, allow subagents, and define handoffs between roles.
- Key point: Best for persistent roles such as planner, reviewer, or implementation agent.

## Agent Skills

- Reference: https://code.visualstudio.com/docs/copilot/customization/agent-skills
- Key point: Agent Skills are portable capability packages made of instructions plus optional scripts and resources.
- Key point: They live in skill folders such as `.github/skills/`, `.claude/skills/`, or `.agents/skills/` with a `SKILL.md` file.
- Key point: Skills load progressively, so extra files are only pulled in when referenced.
- Key point: Best for reusable multi-step workflows like testing, debugging, or deployment.

## Terminal Command Allow/Deny List

- Reference: https://code.visualstudio.com/docs/copilot/agents/agent-tools#_automatically-approve-terminal-commands
- Key point: Use `chat.tools.terminal.autoApprove` in settings JSON to control command auto-approval.
- Key point: Set a rule to `true` to auto-approve, `false` to always require approval.
- Key point: Rules can be exact commands or regex patterns wrapped in `/.../`.
- Example:

```jsonc
"chat.tools.terminal.autoApprove": {
	"mkdir": true,
	"/^git (status|show\\b.*)$/": true,
	"rm": false
}
```

## Quick Distinction

- Prompt files: manual, task-specific slash commands.
- Custom instructions: automatic rules and conventions.
- Custom agents: named personas with scoped tools and workflows.
- Agent Skills: portable reusable capabilities with optional supporting files.