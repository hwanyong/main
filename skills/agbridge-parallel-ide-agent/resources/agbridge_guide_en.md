# Agbridge Daemon Control Guide (Antigravity Bridge)

This document provides instructions on how to control and execute parallel workflows using the **Antigravity Bridge Daemon (`agbridge`)**. By routing prompts through this background agent, you can dispatch comprehensive codebase analysis or automation jobs in parallel without interrupting your local workflow.

## ⚠️ Core Constraints
- **Read-Only**: The Analyzer must NEVER modify, create, or delete project source code files.
- **Web Dependency Context**: Always supplement codebase analysis with Web Context Discovery to verify dependency changelogs, safety concerns, and modern best practices.

---

## 🚀 `agbridge` Command Usage

The `agbridge` CLI allows you to command your workspace agent directly from the terminal. Use these commands to execute the analyzer workflow.

### 1. Requesting Analysis (`ask`)
The foundation of the analyzer. Send a natural language prompt to the agent and dictate the scope of the analysis.

- **Basic Analysis Request**
  ```bash
  agbridge ask "Please read the codebase architecture and dependencies, then provide an analysis report. Do not modify any code."
  ```
- **Start a Completely New Analysis** (`--new` flag)
  Used to launch an isolated context for distinct tasks (e.g., security audits) without polluting past conversations.
  ```bash
  agbridge ask --new "Analyze the package.json and related configuration files for security vulnerabilities."
  ```
- **Continue a Specific Session** (`--session` / `-s`)
  ```bash
  agbridge ask --session <session_id> "Explain the logic from the database layer we analyzed earlier in more depth."
  ```
- **Target a Specific Workspace** (`--workspace` / `-w`)
  Command a VS Code instance running in the background without switching windows.
  ```bash
  agbridge ask --workspace /path/to/project "Analyze the routing logic of this specific project."
  ```
- **Bypass Queue** (`--no-queue` flag)
  Types UI input immediately instead of utilizing the IPC waiting queue (recommended only for single-agent tasks).
  ```bash
  agbridge ask --no-queue "Quickly summarize in 1 sentence what the README says."
  ```

### 2. Managing Analysis Sessions (`session`)
Manage past analysis threads to retrieve historical data or resume previous reasoning.

- **List All Past Sessions**
  ```bash
  agbridge session list
  ```
- **Connect to an Analysis Context**
  Activates a specific session ID so that your next `ask` command applies to that context.
  ```bash
  agbridge session connect <session_id>
  ```
- **Dump Full Session History**
  ```bash
  agbridge session show <session_id>
  ```

### 3. Daemon Status and System Info (`status` & `info`)
Verify AI availability before dispatching massive codebase scans.

- **Check Daemon Connection Status**
  ```bash
  agbridge status
  # Target specific path: agbridge status --workspace /path/to/project
  ```
- **View AI Registry & Cache**
  View the currently active chatbot model and workflow registry details.
  ```bash
  agbridge info
  # Force scrape UI elements to refresh cache: agbridge info --refresh
  ```

### 4. Low-Level Debugging (`debug`)
For advanced cases where the AI cannot correctly parse the UI state for analysis, dump the macOS Accessibility tree for inspection.

- **Dump AXUIElement Tree**
  ```bash
  agbridge debug tree
  # Override max depth: agbridge debug tree --depth 20
  ```

### 5. Tracking Conversation History (`.ag-sessions`)
If you want to view, track, or manage the local conversation history of your daemon interactions, look for the `.ag-sessions` folder inside your target workspace.

- **Directory Location**: `<TARGET_WORKSPACE_PATH>/.ag-sessions/`
- **Internal Structure**:
  - `history_<session_id>.json`: Contains the raw conversation log (user inputs and AI responses) for a specific background session.
  - `active_session.txt`: Tracks which session ID is currently active for the workspace.
Tracing these files is highly recommended when you need to audit the agent's analysis context or verify the JSON data generated during deep codebase scans.
