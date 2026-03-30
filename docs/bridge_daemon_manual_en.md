# Antigravity Bridge Daemon: Architecture & User Manual

This document provides a comprehensive analysis and user manual for the **Bridge Daemon** architecture, purposefully built to support parallel multi-agent execution in Antigravity. It includes details on the system's underlying session separation mechanisms and tested usage examples.

---

## 1. Architecture Overview

Previously, Antigravity agents interacted with macOS Accessibility (AX) APIs individually to activate the VS Code window and manipulate the clipboard. This caused **critical race conditions (e.g., forced window switching, focus stealing, dropped inputs)** when multiple agents were instructed to execute simultaneously.

The **Bridge Daemon** was implemented to resolve this entirely:
* **Stateless Message Broker**: The agent driver scripts (`ag-agent.sh`) do not attempt arbitrary keyboard entry. Instead, they queue inputs via a background JSON queue file (`/tmp/ag_daemon_queue`).
* **Global Input Lock**: The central Daemon strictly enforces sequential UI interaction, ensuring only one background window is locked, surfaced, and targeted for a `Cmd+V` injection at any given millisecond.
* **Robust Verification (Verify & Retry)**: To defend against erratic macOS focus stealing from sudden popups (e.g. Modals), the Daemon measures input `Length` post-paste. On failure, it fires an `ESC` key to dismiss blocking modals, regains target focus, and automatically retries (Auto-Recovery) up to 3 times.

---

## 2. Session Isolation

When executing multi-agent workflows on a single host machine, projects do not cross-contaminate.
1. **Workspace Resolution**: When an agent sparks up, the `-w <workspace_path>` flag enforces that the agent only reads the AX DOM Tree of the window matching that explicit name.
2. **Dedicated Storage Directories**: Prompts and generated Markdown responses are persisted within a segregated `.ag-sessions` hidden tracking directory localized *inside* the respective workspace path.
3. **Collision Resistance**: In native Antigravity, initial chats are simply titled "Agent". To prevent metadata overwrite bugs where no session folder gets logged, the manager uses a unique fallback ID generation mechanism triggered by timestamps (`chat_YYYYMMDD_HHMMSS`), guaranteeing total retention of cross-turn histories.

---

## 3. Core Commands and Usage Examples

### 3.1. Daemon Lifecycle
The Daemon functions as a background job intended to stay active alongside VS Code instances.
```bash
# Starting, restarting, or shutting down the Bridge Daemon
./scripts/ag-daemon.sh start
./scripts/ag-daemon.sh restart
./scripts/ag-daemon.sh stop
```

### 3.2. Single Agent Invocation
Standard usage involves pushing single-turn prompts into a specific project workspace window.
```bash
./scripts/ag-agent.sh ask -w /path/to/project "Step 1: Write a README layout"
./scripts/ag-agent.sh ask -w /path/to/project "Step 2: Add error handling code"
```

### 3.3. Parallel Multi-Turn Stress Test (`e2e_parallel_multiturn.py`)
This script represents the culmination of the multi-agent viability tests—where a **Python** project (`calc_adv_1`) and a **Node.js** project (`calc_adv_2`) are actively generated in tandem across 5 intensive multi-stage turns.

**Test Framework Mechanisms:**
- **Double Fallback Loops**: If the core daemon strikes out on its 3 tries, the high-level Python script invokes a 3-second sleep cycle and re-submits the entire driver job up to 3 times.
- **Live Output Streaming**: The python framework hooks into the raw "🤖 Agent Response" block appearing in the macOS Interface, piping the AI's generated response directly into your active Terminal stdout.

**Running the Scenario:**
```bash
# 1. Environment Prep & Daemon Refresh
./scripts/ag-daemon.sh restart
export PYTHONPATH="."

# 2. Run the Stress Pipeline
.venv_monitor/bin/python3 tests/e2e_parallel_multiturn.py
```

> [!TIP]
> **Validated Result**: Successfully passing this test proves that `calc_adv_1` and `calc_adv_2` perfectly separated 5 independent conversational turns within their respective `.ag-sessions/history.jsonl` files without missing a beat, establishing a 0% input bleed-through rate thanks to the non-blocking queue sequence of the Bridge Daemon.
