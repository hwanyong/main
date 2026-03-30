---
name: analyzer
description: Deeply analyze the codebase while simultaneously gathering latest web context using the Antigravity Bridge Daemon. This skill provides instructions on how to use `agbridge` to interact with the daemon for read-only codebase analysis.
---

# Context Analyzer Skill

This skill allows you to run the **Context Analyzer** workflow via the Antigravity Bridge Daemon (`agbridge`). By utilizing the daemon, you can trigger deep codebase analysis while continuing to work, or manage parallel analysis sessions across multiple workspaces.

## 🛡️ Constraints & Permissions
- **Project Files**: **READ-ONLY**. You are strictly FORBIDDEN from editing, creating, or deleting source code files.
- **Web Access**: **ALLOWED & ENCOURAGED**.
- **Execution via Daemon**: Use the `agbridge` CLI to interact with the LLM orchestrator asynchronously.

## 🚀 How to use `agbridge` Command (Daemon Integration)

The `agbridge` command allows you to control the background daemon and interact with the AI agents. Here is the full list of available commands and how to apply them to the analyzer workflow.

### 1. Requesting Analysis (`ask`)
Use `ask` to send the analyzer prompts to an agent. Describe the scope of analysis clearly.

```bash
# Basic usage: Ask the agent to analyze the current workspace without modifying files
agbridge ask "Please act as an analyzer. Analyze the current codebase architecture. Do not modify files."

# Start a completely new analysis session
agbridge ask --new "Analyze the dependencies in package.json and find security vulnerabilities."

# Continue an analysis in a specific session ID
agbridge ask --session <session_id> "Expand on the previous analysis regarding the database layer."

# Analyze a specific workspace in the background
agbridge ask --workspace /path/to/project "Analyze the routing logic of this project."

# Bypass the queue and send immediately (for single-agent environment)
agbridge ask --no-queue "Quickly read the README and summarize the core features."
```

### 2. Managing Analysis Sessions (`session`)
Use `session` to manage past or parallel analysis threads.

```bash
# View all recent sessions (useful for finding past analysis results)
agbridge session list

# Resume working on a previous analysis session context
agbridge session connect <session_id>

# View the full detailed history and outcome of an analysis session
agbridge session show <session_id>
```

### 3. Monitoring the Daemon (`status` & `info`)
Verify that the daemon is correctly connected to the target workspace before sending large analysis jobs.

```bash
# Check daemon background status and connection to the current UI
agbridge status
agbridge status --workspace /path/to/project

# Check current AI runtime environment and registry data
agbridge info
agbridge info --refresh  # Force refresh the VS Code state cache
```

### 4. Advanced Debugging (`debug`)
If the AI agent is struggling to read UI state or requires low-level DOM inspection.

```bash
# Dump the macOS Accessibility (AXUIElement) DOM tree
agbridge debug tree
agbridge debug tree --depth 20
```

---
*For detailed human-readable guides, please refer to: [guide_en.md](guide_en.md) and [guide_ko.md](guide_ko.md)*
