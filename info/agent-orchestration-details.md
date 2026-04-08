# Agent Orchestration Details

## Overview

This document provides detailed information about agent orchestration and skills systems, serving as a companion to the main [agent orchestration and skills guide](agent-orchestration-and-skills-guide.md).

This repo includes example agents and skills for reference under [agents_and_skills/README.md](agents_and_skills/README.md).

## Quick Reference

### Core Concepts

- **Agent Skills**: Markdown-based instruction packages for extending agent capabilities
- **MCP Servers**: Remote API tools providing deterministic execution
- **Long-running Agents**: Systems that maintain state across multiple context windows
- **Frontend Interaction**: Browser automation and UI testing capabilities
- **Multi-agent Workflows**: Collaborative agent systems with feedback loops

### Platform Support Matrix

| Platform | Skills | MCP | Frontend Tools | Multi-Agent | Setup Complexity |
|-----------|---------|---------|------------------|--------------|-------------------|
| Claude | ✅ Native | ✅ Full | ✅ SDK | ✅ Native | Low |
| Cursor | ✅ Native | ✅ Supported | ✅ Agent Mode | ✅ Subagents | Low |
| VS Code | ✅ Native | ✅ Supported | ✅ Agents | ✅ Agents + custom subagents (experimental) | Medium |
| Skills.sh | ✅ Platform | ⚠️ Limited | ⚠️ Basic | ⚠️ Limited | Low |

### Installation Commands

#### Conductor (Production Orchestration)
```bash
# Quick start (60 seconds)
npm install -g @conductor-oss/conductor-cli
conductor server start

# Docker (recommended)
docker run -p 8080:8080 conductoross/conductor:latest

# Universal installer (all agents)
curl -sSL https://conductor-oss.github.io/conductor-skills/install.sh | bash -s -- --all

# Test workflow
curl -s https://raw.githubusercontent.com/conductor-oss/conductor/main/docs/quickstart/workflow.json -o workflow.json
conductor workflow create workflow.json
conductor workflow start -w hello_workflow --sync
```

**Links:**
- [Main Documentation](https://conductor-oss.org)
- [Quickstart Guide](https://conductor-oss.org/quickstart)
- [GitHub Repository](https://github.com/conductor-oss/conductor)
- [Community Slack](https://join.slack.com/t/orkes-conductor/shared_invite/zt-2vdbx239s-Eacdyqya9giNLHfrCavfaA)
- [Scaling Guide](https://github.com/conductor-oss/conductor/blob/main/docs/devguide/how-tos/Workers/scaling-workers.md)

#### LangChain Deep Agents (Rapid Prototyping)
```bash
# Installation
pip install deepagents
# or
uv add deepagents

# Quick start
from deepagents import create_deep_agent
agent = create_deep_agent()
result = agent.invoke({"messages": [{"role": "user", "content": "Research LangGraph and write a summary"}]})

# CLI installation
curl -LsSf https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/cli/scripts/install.sh | bash

# Features included:
- Planning (write_todos)
- Filesystem (read_file, write_file, edit_file, ls, glob, grep)
- Shell access (execute with sandboxing)
- Sub-agents (task delegation)
- Context management (auto-summarization)
```

**Links:**
- [Documentation](https://docs.langchain.com/oss/python/deepagents/overview)
- [Quickstart](https://docs.langchain.com/oss/python/deepagents/quickstart)
- [GitHub](https://github.com/langchain-ai/deepagents)
- [MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [LangSmith Platform](https://docs.langchain.com/langsmith/home)

#### Anthropic Agent SDK (Claude-Specific)
```bash
# Not a traditional package - uses two-part approach:
# 1. Initializer agent sets up environment
# 2. Coding agent makes incremental progress

# Key features:
- Environment management (init.sh, claude-progress.txt)
- Incremental progress tracking
- Git integration for state management
- Browser automation for testing
- Multi-context window support
- Long-running task orchestration
```

**Links:**
- [Effective Harnesses Guide](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Agent SDK Documentation](https://docs.anthropic.com/en/agent-sdk)
- [Claude Code Documentation](https://code.claude.com/docs/en/overview)

#### Agent Skills (Cross-Platform)
```bash
# Claude Skills
mkdir -p .claude/skills/
# Skills auto-discovered from .claude/skills/, .cursor/skills/, ~/.claude/skills/

# Cursor Skills  
mkdir -p .cursor/skills/
# Same structure, GitHub integration

# VS Code skills
mkdir -p .github/skills/
# Also supports .claude/skills/ and .agents/skills/ in the workspace

# Skills.sh Ecosystem
# Browse and discover skills at https://skills.sh/
# Cross-platform compatibility

# Standard structure:
skill-name/
├── SKILL.md          # Main instructions with YAML frontmatter
├── scripts/           # Executable code
├── references/        # Additional docs
└── assets/           # Templates, data
```

**Links:**
- [Agent Skills Standard](https://agentskills.io/)
- [Claude Skills Docs](https://code.claude.com/docs/en/skills)
- [Cursor Skills Docs](https://cursor.com/docs/context/skills)
- [Skills.sh Directory](https://skills.sh/)
- [VS Code Agent Skills Documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

#### VS Code Copilot Skills
```bash
# Via VS Code settings
# Type /skills in chat to open skills menu
# Install from GitHub repositories
# Compatible with Agent Skills standard
```

**Links:**
- [VS Code Skills Documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

#### VS Code Custom Agents (Overview)

VS Code defines custom agents in `.agent.md` files (workspace or user scope). Custom agents can specify tools, models, and which agents are permitted as subagents. VS Code also supports Claude-style agent files in `.claude/agents` for compatibility.

Default locations:
- Workspace: `.github/agents/`
- Workspace (Claude format): `.claude/agents/`
- User profile: `~/.copilot/agents/`

**Links:**
- [VS Code Custom Agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents)

#### Kiro Skills (Overview)

Kiro supports the Agent Skills standard with workspace and global scopes.

Skill directories:
- `.kiro/skills/` - Workspace-level
- `~/.kiro/skills/` - Global

**Links:**
- [Kiro Agent Skills](https://kiro.dev/docs/skills/)

#### Antigravity Skills (Overview)

Antigravity supports the Agent Skills standard with workspace and global scopes.

Skill directories:
- `<workspace-root>/.agents/skills/` - Workspace-level
- `~/.gemini/antigravity/skills/` - Global
- Backward-compatible: `<workspace-root>/.agent/skills/`

**Links:**
- [Antigravity Agent Skills](https://antigravity.google/docs/skills)

### Key Differences

#### Skills vs MCP
- **Skills**: Local instructions, flexible, low latency
- **MCP**: Remote APIs, deterministic, network latency

#### When to Choose MCP
- External API integration required
- Precise deterministic execution needed
- Real-time data access critical
- Development resources available

#### When to Choose Skills
- Rapid prototyping needs
- Non-technical users
- Domain-specific guidance
- Local execution sufficient

### Frontend Automation Tools

#### Browser-Based Options
1. **Browser Use** - General purpose automation, Claude skill integration
   - **Installation**: Available as Claude Code skill
   - **Features**: 3-5x faster than other models with SOTA accuracy
   - **Use Cases**: Form filling, web scraping, e-commerce automation
   - **Link**: [GitHub](https://github.com/browser-use/browser-use) | [Docs](https://docs.browser-use.com/)

2. **Vercel Agent Browser** - Claude-specific, vision-based automation
   - **Installation**: Auto-updating skill from repository
   - **Features**: Full agent-browser workflow, vision LLMs
   - **Use Cases**: Complex web workflows, testing, data extraction
   - **Link**: [GitHub](https://github.com/vercel-labs/agent-browser)

3. **Skyvern** - Enterprise-grade, vision automation
   - **Features**: Vision LLMs instead of DOM parsing/XPath
   - **Benefits**: More robust to website layout changes
   - **Use Cases**: Enterprise web automation, testing
   - **Link**: [GitHub](https://github.com/Skyvern-AI/skyvern)

4. **Microsoft Foundry Browser Automation** - Production testing framework
   - **Platform**: Azure Foundry agents
   - **Features**: Enterprise-grade browser automation, C# SDK
   - **Use Cases**: Production UI testing, workflow automation
   - **Link**: [Documentation](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/browser-automation)

#### Selection Criteria
- **Robustness**: Vision vs DOM parsing approaches
- **Integration**: Native platform compatibility
- **Maintenance**: Update frequency and breakage rates
- **Performance**: Speed vs accuracy trade-offs

### Multi-Agent Patterns

#### Workflow Types
1. **Sequential**: Linear task progression
2. **Parallel**: Independent simultaneous execution
3. **Hierarchical**: Manager-subordinate relationships
4. **Iterative**: Feedback-driven improvement

#### Coordination Strategies
- **Message Passing**: Structured agent communication
- **Shared State**: Centralized information storage
- **Event-Driven**: Dynamic response to triggers

#### Feedback Loops
- **Generator-Validator**: Quality assessment patterns
- **Iteration Limits**: Prevent infinite loops
- **Learning**: Store feedback for improvement

### Architecture Considerations

#### Scalability Patterns
- **Horizontal Scaling**: Multiple agent instances for load distribution
- **Vertical Scaling**: Enhanced capabilities within single agents
- **Hybrid Approaches**: Combining multiple coordination strategies

#### Performance Optimization
- **Context Management**: Progressive loading and summarization
- **Caching Strategies**: Store frequently accessed data
- **Resource Allocation**: Optimize memory and compute usage

### Implementation Tips

#### Skill Development
```yaml
# Standard structure
skill-name/
├── SKILL.md          # Main instructions with YAML frontmatter
├── scripts/           # Executable code and utilities
├── references/        # Additional documentation
└── assets/           # Templates, data files, examples
```

**SKILL.md Frontmatter Format:**
```yaml
---
name: required-skill-name
description: Clear description of when and how to use this skill
license: optional  # MIT, Apache 2.0, etc.
compatibility: optional  # Platforms where skill works
metadata: optional  # Additional key-value pairs
disable-model-invocation: optional  # Makes skill manual-only
---
```

#### Frontend Integration
```python
# Example browser automation
from browser_use import Agent

agent = Agent()
task = "Navigate to form and submit data"
result = agent.run(task)
```

#### Multi-Agent Coordination
```python
# Example feedback loop
class WorkflowCoordinator:
    def __init__(self):
        self.generator = GeneratorAgent()
        self.validator = ValidatorAgent()
    
    async def execute_with_feedback(self, task):
        result = await self.generator.execute(task)
        feedback = await self.validator.validate(result)
        
        while not feedback.approved:
            result = await self.generator.refine(result, feedback)
            feedback = await self.validator.validate(result)
        
        return result
```

### Best Practices

#### For Long-Running Tasks
- Use incremental progress tracking
- Implement clean state management
- Provide recovery mechanisms
- Monitor performance metrics

#### For Skills Development
- Write clear, concise descriptions
- Use progressive resource loading
- Include error handling guidance
- Test across different scenarios

#### For Frontend Interaction
- Implement robust selectors
- Handle dynamic content loading
- Use retry mechanisms
- Optimize for reliability

#### For Multi-Agent Systems
- Define clear agent roles
- Use structured communication
- Implement conflict resolution
- Set iteration limits

### Troubleshooting

#### Common Issues
- **Context Overflow**: Use progressive loading and compaction
- **Agent Conflicts**: Implement proper coordination and conflict resolution
- **Skill Discovery**: Check directory permissions and skill structure
- **Frontend Failures**: Update selectors and implement robust wait strategies
- **Network Latency**: Optimize MCP server calls and implement caching
- **State Management**: Ensure clean state persistence across sessions

#### Debugging Tools
- **Logging**: Detailed execution traces with structured logging
- **Monitoring**: Performance metrics and success rate tracking
- **Testing**: Validate across different scenarios and edge cases
- **Profiling**: Identify bottlenecks and optimization opportunities
- **Observability**: End-to-end workflow visibility

### Security Considerations

#### Best Practices
- **Input Validation**: Sanitize all external inputs and API calls
- **Access Control**: Implement proper authentication and authorization
- **Data Protection**: Encrypt sensitive data in transit and at rest
- **Audit Logging**: Track all agent actions for compliance
- **Sandboxing**: Isolate agent execution environments when possible

### Migration Strategies

#### From Traditional Automation
1. **Assessment**: Identify existing workflows suitable for agent orchestration
2. **Incremental Migration**: Start with non-critical processes
3. **Skill Development**: Create domain-specific skills for your use cases
4. **Testing**: Validate agent performance against traditional methods
5. **Rollout**: Gradual deployment with monitoring and rollback plans

---

## Additional Resources

### Community and Support
- [Agent Skills Community](https://agentskills.io/community) - Discussions and contributions
- [Conductor Community Slack](https://join.slack.com/t/orkes-conductor) - Support and discussions
- [LangChain Community](https://discord.gg/langchain) - Multi-agent coordination
- [Cursor Community](https://cursor.com/community) - Skills development and IDE integration

### Learning Materials
- [Anthropic's Agent Documentation](https://docs.anthropic.com/agent-sdk) - Official guides and tutorials
- [Conductor Tutorials](https://conductor-oss.org/tutorials) - Workflow orchestration examples
- [Browser Use Examples](https://docs.browser-use.com/examples) - Frontend automation patterns
- [Multi-Agent Patterns](https://github.com/langchain-ai/langgraph) - Coordination strategies

### Tools and Utilities
- [Skill Development Kit](https://github.com/agentskills/sdk) - Development and testing tools
- [MCP Server Templates](https://github.com/modelcontextprotocol/servers) - Server boilerplates
- [Agent Testing Framework](https://github.com/langchain-ai/agent-test) - Automated testing utilities

---

*Last updated: 2026-03-25 23:52:00*
*Document version: 1.2*

---

## Cursor Subagents (Verified)

Cursor subagents run in isolated contexts and can operate in foreground or background. Built-in subagents include `Explore`, `Bash`, and `Browser`. Custom subagents are defined in `.cursor/agents/` (project) or `~/.cursor/agents/` (user), with compatibility directories `.claude/agents/` and `.codex/agents/`.

**Links:**
- [Cursor Subagents Documentation](https://cursor.com/docs/context/subagents)

---

## Other IDEs and Agents (Current Notes)

- **Kiro**: Agent Skills live in `.kiro/skills/` (workspace) and `~/.kiro/skills/` (global). Steering files live in `.kiro/steering/` (workspace) and `~/.kiro/steering/` (global), and Kiro supports `AGENTS.md` in those locations. Kiro CLI custom agents use JSON configs in `.kiro/agents/` (workspace) or `~/.kiro/agents/` (global).
- **Warp**: Provides local and cloud agents (Oz), supports MCP servers and rules; no Agent Skills or custom agent file format is documented in Warp docs yet.
- **Cline**: Editor/terminal agent requiring explicit approval for actions; no Agent Skills or custom agent file format is documented in public docs yet.
- **Antigravity**: Agent Skills directories are documented, and the browser subagent is a separate model specialized for browser control. It can capture screenshots and recordings as artifacts for review. For multi-workspace oversight, Antigravity also provides an Agent Manager view. See [Agent](https://antigravity.google/docs/agent), [Skills](https://antigravity.google/docs/skills), [Browser Subagent](https://antigravity.google/docs/browser-subagent), [Screenshots](https://antigravity.google/docs/screenshots), [Browser Recordings](https://antigravity.google/docs/browser-recordings), and [Agent Manager](https://antigravity.google/docs/agent-manager).
