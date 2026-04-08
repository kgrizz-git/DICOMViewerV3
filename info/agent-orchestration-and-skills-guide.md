# Agent Orchestration and Skills: Comprehensive Guide

## Overview

This document covers tools and frameworks for long-running agents, agent skills systems, frontend interaction capabilities, and autonomous agent workflows. It focuses on practical implementations and compatibility across different AI platforms.

This repo includes example agents and skills for reference under [agents_and_skills/README.md](agents_and_skills/README.md).

## Table of Contents

1. [Long-Running Agent Orchestration](#long-running-agent-orchestration)
2. [Agent Skills Systems](#agent-skills-systems)
3. [Skills vs MCP Servers](#skills-vs-mcp-servers)
4. [Frontend Agent Interaction](#frontend-agent-interaction)
5. [Autonomous Agent Loops and Multi-Agent Workflows](#autonomous-agent-loops-and-multi-agent-workflows)
6. [Platform Compatibility Matrix](#platform-compatibility-matrix)
7. [Recommended Tools and Frameworks](#recommended-tools-and-frameworks)
8. [Implementation Examples](#implementation-examples)

---

## Long-Running Agent Orchestration

### Conductor Framework

**Conductor** is an orchestration system designed for managing long-running AI agents and complex workflows.

#### Key Features:
- **Deterministic orchestration** with safe replay capabilities
- **Horizontal scaling** for internet-scale operations
- **Polyglot workers** supporting multiple programming languages
- **LLM orchestration** for AI agent coordination
- **Self-hosted deployment** as an alternative to Temporal and Step Functions

#### Use Cases:
- Multi-agent workflows where agents run in parallel without interference
- Long-running tasks requiring state persistence and recovery
- Complex business process automation with AI agents

**Links:**
- [GitHub Repository](https://github.com/conductor-oss/conductor)
- [Documentation](https://conductor-oss.github.io/conductor/)
- [Code Conductor](https://github.com/ryanmac/code-conductor) - GitHub-native orchestration for Claude Code

### Agent Harnesses

**Harnesses** provide structured environments for long-running agents to operate reliably across multiple context windows.

#### Anthropic's Two-Part Solution:

1. **Initializer Agent**: Sets up the initial environment
   - Creates `init.sh` scripts
   - Establishes `claude-progress.txt` for tracking
   - Makes initial git commit with foundation files

2. **Coding Agent**: Makes incremental progress
   - Works on one feature at a time
   - Leaves clean, commit-ready state
   - Updates progress tracking files

#### Key Components:
- **Feature Lists**: Comprehensive JSON definitions of all required functionality
- **Incremental Progress**: Prevents agents from attempting too much at once
- **Testing Integration**: End-to-end validation with browser automation tools
- **Clean State Management**: Ensures code is always merge-ready

**Links:**
- [Anthropic's Effective Harnesses Guide](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/harness)

---

## Agent Skills Systems

### Claude Skills

**Claude Skills** is an open standard for extending AI agents with specialized capabilities using markdown-based instruction packages.

#### Structure:
```
.claude/skills/
├── skill-name/
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── assets/
```

#### SKILL.md Format:
```yaml
---
name: skill-name
description: Short description of what this skill does and when to use it
---

# Skill Name

Detailed instructions for the agent.

## When to Use
- Use this skill when...
- This skill is helpful for...

## Instructions
- Step-by-step guidance
- Domain-specific conventions
- Best practices and patterns
```

#### Key Features:
- **Portable**: Works across any Agent Skills-compatible platform
- **Version-controlled**: Stored as files in repositories
- **Progressive**: Loads resources on demand to manage context efficiently
- **Actionable**: Can include scripts, templates, and references

**Links:**
- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Agent Skills Standard](https://agentskills.io/)

### Cursor Skills

**Cursor** implements the Agent Skills open standard with additional IDE integration features.

#### Skill Directories:
- `.agents/skills/` - Project-level
- `.cursor/skills/` - Project-level  
- `~/.cursor/skills/` - User-level (global)
- Compatibility directories: `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, `~/.codex/skills/`

#### Unique Features:
- **Automatic Discovery**: Skills loaded at startup
- **Manual Invocation**: Type `/` in Agent chat to search skills
- **GitHub Integration**: Install skills directly from repositories
- **Migration Tools**: Built-in `/migrate-to-skills` command

#### Frontmatter Fields:
```yaml
---
name: required
description: required
license: optional
compatibility: optional
metadata: optional
disable-model-invocation: optional # Makes skill manual-only
---
```

**Links:**
- [Cursor Skills Documentation](https://cursor.com/docs/context/skills)

### VS Code Copilot Skills

VS Code supports the Agent Skills standard and discovers skills from multiple locations.

#### Skill Directories:
- `.github/skills/`, `.claude/skills/`, `.agents/skills/` - Project-level
- `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` - User-level

**Links:**
- [VS Code Agent Skills Documentation](https://code.visualstudio.com/docs/copilot/customization/agent-skills)

### VS Code Custom Agents

VS Code defines custom agents in `.agent.md` files (workspace or user scope). Custom agents can specify tools, models, and which agents are allowed as subagents. VS Code also supports Claude-style agent files in `.claude/agents` for compatibility.

#### Default Locations:
- Workspace: `.github/agents/`
- Workspace (Claude format): `.claude/agents/`
- User profile: `~/.copilot/agents/`

**Links:**
- [VS Code Custom Agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents)

### Kiro Skills

Kiro supports the Agent Skills standard with workspace and global scopes.

#### Skill Directories:
- `.kiro/skills/` - Workspace-level
- `~/.kiro/skills/` - Global

**Links:**
- [Kiro Agent Skills](https://kiro.dev/docs/skills/)

### Antigravity Skills

Antigravity supports the Agent Skills standard and uses workspace/global skill directories.

#### Skill Directories:
- `<workspace-root>/.agents/skills/` - Workspace-level
- `~/.gemini/antigravity/skills/` - Global
- Backward-compatible: `<workspace-root>/.agent/skills/`

**Links:**
- [Antigravity Agent Skills](https://antigravity.google/docs/skills)

### Skills.sh Ecosystem

**Skills.sh** is an open ecosystem for discovering and sharing agent skills across platforms.

#### Features:
- **Centralized Directory**: Browse and discover skills
- **Cross-Platform Compatibility**: Works with Claude, Cursor, and other agents
- **Version Management**: Track skill versions and updates
- **Community Contributions**: Open source skill development

**Links:**
- [Skills.sh Directory](https://skills.sh/)
- [Agent Skills Overview](https://agentskills.io/home)

---

## Skills vs MCP Servers

### Fundamental Differences

| Aspect | Skills | MCP Servers |
|---------|---------|-------------|
| **Execution** | Local instructions interpreted by agent | Remote API calls to external services |
| **Setup Complexity** | Low (markdown files) | High (servers, authorization, transports) |
| **Latency** | Minimal (local execution) | Network latency on each call |
| **Scalability** | Easy (file-based discovery) | Difficult (tool discovery and naming) |
| **Determinism** | Variable (agent interpretation) | High (precise API responses) |
| **Target Audience** | Non-technical users | Developers |

### When to Use Skills

**Use Skills when:**
- You need rapid prototyping and iteration
- Target users are non-technical
- Tasks require flexible, adaptive behavior
- You want minimal setup overhead
- Local execution is sufficient

**Example Use Cases:**
- Code style guidelines and conventions
- Domain-specific workflows (legal review, data analysis)
- Multi-step processes with human-like reasoning
- Educational or training scenarios

### When to Use MCP Servers

**Use MCP Servers when:**
- You need precise, deterministic execution
- Tasks require external API integration
- Real-time data access is critical
- You have development resources for setup
- Network latency is acceptable

**Example Use Cases:**
- Database queries and API calls
- External service integrations (GitHub, Slack, etc.)
- Real-time data fetching
- Production-grade tool execution

### Hybrid Approaches

Many modern systems combine both approaches:
- **Skills for high-level workflow guidance**
- **MCP for precise tool execution**
- **Skills can orchestrate MCP tool usage**
- **MCP servers can expose skill-like interfaces**

---

## Cursor Subagents (Verified)

Cursor can spawn subagents automatically or by explicit request. Subagents run in isolated context windows, can run in foreground or background, and are designed for parallel, context-heavy work.

Key points from Cursor docs:
- Built-in subagents include `Explore`, `Bash`, and `Browser`.
- Custom subagents live in `.cursor/agents/` (project) or `~/.cursor/agents/` (user), with compatibility for `.claude/agents/` and `.codex/agents/`.
- Agent can delegate automatically based on the subagent `description`, or you can invoke directly with `/name`.
- Subagents can run in parallel; each subagent uses its own context and token budget.

**Links:**
- [Cursor Subagents Documentation](https://cursor.com/docs/context/subagents)

---

## Frontend Agent Interaction

### Browser Automation Frameworks

#### Browser Use
- **Purpose**: Make websites accessible for AI agents
- **Features**: Optimized for browser automation tasks with 3-5x speed improvement
- **Integration**: Available as Claude Code skill
- **Use Cases**: Form filling, web scraping, e-commerce automation

**Links:**
- [Browser Use GitHub](https://github.com/browser-use/browser-use)
- [Documentation](https://docs.browser-use.com/)

#### Vercel Agent Browser
- **Purpose**: Browser automation CLI for agents
- **Features**: Full workflow automation with vision-based interaction
- **Integration**: Available as skill that auto-updates from repository
- **Use Cases**: Complex web workflows, testing, data extraction

**Links:**
- [Vercel Agent Browser](https://github.com/vercel-labs/agent-browser)

#### Skyvern
- **Purpose**: Automate browser-based workflows with AI vision
- **Features**: Vision LLMs instead of DOM parsing/XPath
- **Benefits**: More robust to website layout changes
- **Use Cases**: Enterprise web automation, testing

**Links:**
- [Skyvern GitHub](https://github.com/Skyvern-AI/skyvern)

### Frontend Testing and Validation

#### Microsoft Foundry Browser Automation
- **Platform**: Azure Foundry agents
- **Features**: Enterprise-grade browser automation
- **Integration**: C# SDK with streaming support
- **Use Cases**: Production UI testing, workflow automation

**Links:**
- [Foundry Browser Automation Docs](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/browser-automation)

### Key Considerations for Frontend Interaction

1. **Vision vs DOM**: Vision-based approaches are more robust to layout changes
2. **Speed vs Accuracy**: Trade-offs between automation speed and reliability
3. **Maintenance**: Consider how frequently website updates break automation
4. **Error Handling**: Implement robust retry and recovery mechanisms
5. **Performance**: Monitor token usage and execution time

---

## Autonomous Agent Loops and Multi-Agent Workflows

### Agentic Workflow Patterns

#### Sequential Workflows
- **Description**: Agents execute tasks in a predetermined sequence
- **Use Case**: Simple pipelines where order matters
- **Example**: Generate code → Run tests → Create documentation

#### Parallel Workflows
- **Description**: Multiple agents work simultaneously on different aspects
- **Use Case**: Independent tasks that can be processed together
- **Example**: Frontend and backend development in parallel

#### Hierarchical Workflows
- **Description**: Higher-level agents coordinate lower-level specialists
- **Use Case**: Complex projects requiring decomposition
- **Example**: Project manager → Technical leads → Developers

#### Iterative Workflows
- **Description**: Agents refine outputs through multiple iterations
- **Use Case**: Quality improvement and optimization
- **Example**: Write code → Review → Refactor → Review

### Coordination Strategies

#### Message Passing
- **Description**: Agents communicate through structured messages
- **Benefits**: Simple, flexible, widely supported
- **Implementation**: JSON messages with defined schemas
- **Example**: Agent A sends task completion to Agent B

#### Shared State Management
- **Description**: Centralized information storage for coordination
- **Benefits**: Consistent state, prevents race conditions
- **Implementation**: Vector databases, shared memory
- **Example**: LangChain's state management

#### Event-Driven Coordination
- **Description**: Agents respond to system state changes
- **Benefits**: Dynamic, real-time coordination
- **Implementation**: Event buses, pub/sub patterns
- **Example**: AutoGen's event system

### Feedback Loops

#### Generator-Validator Pattern
- **Generator**: Creates content or performs tasks
- **Validator**: Checks quality and compliance
- **Loop**: Validator provides feedback for improvement

#### Implementation Considerations:
- **Iteration Limits**: Prevent infinite loops
- **Quality Metrics**: Define clear success criteria
- **Learning**: Store feedback for future improvement
- **Different Models**: Use separate models for generation and validation

#### Real-World Example:
```
1. Generator Agent: Writes code for a feature
2. Validator Agent: Reviews code for:
   - Syntax correctness
   - Code style compliance
   - Test coverage
   - Security vulnerabilities
3. Feedback Loop: Validator suggests improvements
4. Iteration: Generator refactors based on feedback
5. Final Check: Validator approves or requests more changes
```

### Performance Optimization

#### Monitoring and Observability
- **Performance Metrics**: Track execution time, token usage, success rates
- **Logging**: Detailed logs for debugging and analysis
- **Alerting**: Notify on failures or performance degradation

#### Optimization Strategies
- **Caching**: Store frequently used results
- **Parallelization**: Run independent tasks simultaneously
- **Resource Management**: Optimize memory and compute usage
- **Model Selection**: Choose appropriate models for specific tasks

---

## Platform Compatibility Matrix

| Feature | Claude | Cursor | VS Code Copilot | Skills.sh |
|----------|---------|---------|------------------|------------|
| **Skills Support** | ✅ Native | ✅ Native | ✅ Native | ✅ Platform |
| **MCP Servers** | ✅ Native | ✅ Supported | ✅ Supported | ⚠️ Limited |
| **Frontend Tools** | ✅ Browser Use | ✅ Browser Use | ⚠️ Limited | ⚠️ Limited |
| **Multi-Agent** | ✅ SDK Support | ✅ Subagents | ✅ Agents | ⚠️ Limited |
| **GitHub Integration** | ✅ | ✅ | ✅ | ✅ |
| **Local Execution** | ✅ | ✅ | ✅ | ✅ |
| **Custom Tools** | ✅ | ✅ | ✅ | ✅ |

### Cross-Platform Considerations

1. **Skill Portability**: Agent Skills standard ensures compatibility
2. **MCP Limitations**: Not all platforms support MCP equally
3. **Frontend Integration**: Browser automation varies by platform
4. **Development Experience**: Each platform has unique tooling

### Other IDEs and Agents (Current Notes)

- **Kiro**: Agent Skills live in `.kiro/skills/` (workspace) and `~/.kiro/skills/` (global). Steering files live in `.kiro/steering/` (workspace) and `~/.kiro/steering/` (global), and Kiro supports `AGENTS.md` in those locations. Kiro CLI custom agents use JSON configs in `.kiro/agents/` (workspace) or `~/.kiro/agents/` (global).
- **Warp**: Provides local and cloud agents (Oz) and supports MCP servers and rules; no Agent Skills or custom agent file format is documented in Warp docs yet.
- **Cline**: Editor/terminal agent requiring explicit approval for each action; no Agent Skills or custom agent file format is documented in the public docs yet.
- **Antigravity**: Agent Skills directories are documented, and the browser subagent is a separate model specialized for browser control. It can capture screenshots and recordings as artifacts for review. For multi-workspace oversight, Antigravity also provides an Agent Manager view. See [Agent](https://antigravity.google/docs/agent), [Skills](https://antigravity.google/docs/skills), [Browser Subagent](https://antigravity.google/docs/browser-subagent), [Screenshots](https://antigravity.google/docs/screenshots), [Browser Recordings](https://antigravity.google/docs/browser-recordings), and [Agent Manager](https://antigravity.google/docs/agent-manager).

---

## Recommended Tools and Frameworks

### For Long-Running Agents
1. **Conductor** - Production orchestration
2. **LangChain Deep Agents** - Rapid prototyping
3. **Anthropic Agent SDK** - Claude-specific features

### For Skills Development
1. **Agent Skills Standard** - Cross-platform compatibility
2. **Skills.sh** - Community and discovery
3. **Platform-specific tools** - Native integrations

### For Frontend Interaction
1. **Browser Use** - General browser automation
2. **Vercel Agent Browser** - Claude Code integration
3. **Skyvern** - Enterprise-grade vision automation

### For Multi-Agent Workflows
1. **LangChain** - State management and coordination
2. **AutoGen** - Event-driven coordination
3. **Custom implementations** - Platform-specific optimizations

---

## Implementation Examples

### Example 1: Web Development Workflow

```yaml
# Project structure
.web-dev-workflow/
├── skills/
│   ├── frontend-dev/
│   │   └── SKILL.md
│   ├── backend-dev/
│   │   └── SKILL.md
│   └── testing/
│       └── SKILL.md
└── config/
    └── workflow.yaml
```

**Workflow:**
1. **Planner Agent**: Decomposes requirements into tasks
2. **Frontend Agent**: Implements UI components
3. **Backend Agent**: Implements API endpoints
4. **Testing Agent**: Validates integration
5. **Validator Agent**: Ensures quality standards
6. **Feedback Loop**: Iterates based on test results

### Example 2: E-commerce Automation

```yaml
# Skill for product monitoring
---
name: product-monitor
description: Monitor e-commerce products for price changes and availability
---

# Product Monitoring

## When to Use
- User mentions price tracking
- Need to monitor product availability
- Competitive analysis requests

## Instructions
1. Use browser automation to navigate to product pages
2. Extract price, availability, and specifications
3. Store data in structured format
4. Compare with historical data
5. Alert on significant changes

## Tools Required
- Browser automation (Browser Use)
- Data storage (local files or database)
- Notification system (email or Slack)
```

### Example 3: Multi-Agent Code Review

```python
# Coordinator agent implementation
class CodeReviewCoordinator:
    def __init__(self):
        self.agents = {
            'security': SecurityReviewer(),
            'performance': PerformanceReviewer(),
            'style': StyleReviewer(),
            'logic': LogicReviewer()
        }
    
    async def review_code(self, code):
        reviews = {}
        for name, agent in self.agents.items():
            review = await agent.analyze(code)
            reviews[name] = review
        
        # Synthesize feedback
        final_review = self.synthesize_feedback(reviews)
        return final_review
    
    def synthesize_feedback(self, reviews):
        # Combine all reviews into actionable feedback
        pass
```

---

## Best Practices

### Skill Development
1. **Clear Descriptions**: Help agents understand when to use skills
2. **Incremental Loading**: Use references/ directory for detailed info
3. **Error Handling**: Provide guidance for common failure modes
4. **Testing**: Validate skills work across different scenarios

### Multi-Agent Coordination
1. **Clear Roles**: Define specific responsibilities for each agent
2. **Communication Protocols**: Use structured message formats
3. **State Management**: Prevent conflicts and race conditions
4. **Monitoring**: Track performance and identify bottlenecks

### Frontend Interaction
1. **Robust Selectors**: Use multiple identification methods
2. **Wait Strategies**: Handle dynamic content loading
3. **Error Recovery**: Implement retry mechanisms
4. **Performance**: Optimize for speed and reliability

---

## Future Trends

### Emerging Patterns
1. **Hybrid MCP-Skills**: Combining external tools with local instructions
2. **Vision-Based Automation**: Moving beyond DOM parsing
3. **Adaptive Workflows**: Self-optimizing agent coordination
4. **Cross-Platform Standards**: Improved interoperability

### Technology Evolution
1. **Better Context Management**: More efficient token usage
2. **Improved Reliability**: Reduced hallucinations and errors
3. **Enhanced Tooling**: Better development and debugging experiences
4. **Enterprise Integration**: Production-ready deployments

---

## Conclusion

The landscape of agent orchestration and skills is rapidly evolving, with clear patterns emerging for different use cases:

- **Skills** excel at rapid prototyping and domain-specific guidance
- **MCP Servers** provide precise, deterministic tool execution
- **Frontend automation** enables real-world web interaction
- **Multi-agent workflows** handle complex, collaborative tasks

Success depends on choosing the right approach for your specific needs and ensuring compatibility across your chosen platforms. The Agent Skills standard provides a foundation for cross-platform compatibility, while platform-specific tools offer optimized experiences.

The key is to start simple, iterate based on real usage, and gradually adopt more sophisticated patterns as your requirements grow.
