# Implementation Plan Supplement — 3 Missing Concerns Addressed

> Date: 2026-03-29 | Supplement to Implementation Plan v1.0

---

## Q1: Session Data Details (What Gets Stored in Workspace)

### Storage Structure
```
{workspace_root}/
└── .ag-sessions/
    ├── config.yaml            ← workspace settings
    ├── active_session         ← last used session ID (1-line text)
    └── sessions/
        └── {session-id}/
            ├── metadata.json  ← session identification
            └── history.jsonl  ← conversation history (line-delimited)
```

### metadata.json Fields
| Field | Purpose |
|:---|:---|
| `id` | Unique session identifier (used in `--session` CLI arg) |
| `title` | Human-readable session name |
| `panel_title` | Agent Panel conversation title (**used for conversation matching**) |
| `workspace` | Absolute workspace path |
| `window_title_pattern` | Pattern to match window title |
| `status` | `active` / `idle` / `archived` |
| `tags` | Search/classification tags |
| `description` | Session description (for sub-agent decision making) |

### Conversation Routing Algorithm
1. Find session by ID in `.ag-sessions/sessions/`
2. Extract `panel_title` from metadata
3. Compare with current Agent Panel title
4. If different → open Past Conversations → search → switch

---

## Q2: ask_and_wait.py Interaction Pattern Benchmark

### JSON Bridge Pattern
```
Problem:  Reading AX text corrupts markdown
Solution: Instruct agent to write response to a file

User question + "Write your response to .agent_response.json, reply 'Done' in chat"
→ Agent creates file → Script reads file → Clean, structured response
```

### Improvements for Upgrade
1. Response file path: CWD → session-specific absolute path
2. Add session context to prompt (optional previous conversation summary)
3. Configurable timeout (config.yaml instead of hardcoded 120s)
4. Triple state detection: Send + Cancel + "Running" text
5. Preserve response files in session directory (don't delete)

---

## Q3: Clipboard Contention — Root Cause Analysis & Solution

### The Problem
macOS clipboard is a **system-wide shared resource**. Multiple sub-agents using clipboard simultaneously will corrupt each other's data.

### Alternatives Tested
| Method | Works? |
|:---|:---|
| AXValue direct write | ❌ Electron ignores |
| CGEventKeyboardSetUnicodeString | ❌ Electron ignores |
| **Clipboard Semaphore (flock)** | ✅ Only viable solution |

### Clipboard Semaphore Design
```
Lock file: /tmp/.ag-clipboard.lock
Lock scope: clipboard set → paste → clipboard restore (MINIMAL)
Lock duration: ~550ms
```

The lock only covers the clipboard operation, NOT the entire ask cycle. Multiple agents wait at most ~0.5 seconds, which is imperceptible.

### Future: If Antigravity adds Extension API or CLI message injection, clipboard can be completely bypassed.
