# 🏗️ AG-Agent: Final Implementation Plan

> Date: 2026-03-29 | Version: v2.0 (Final)  
> Consolidation of: implementation_plan + supplement + event_driven_design

---

## 📌 Summary

> **An event-driven CLI tool that automates Antigravity IDE's Agent Panel via AX API,  
> enabling sub-agents to find, switch, input, and collect responses from conversations**

---

## 1. Current → Goal

### Current (ask_and_wait.py — 284-line single file)
- No conversation selection, no session history, no concurrency
- `time.sleep()` everywhere (hope-based waits)

### Goal (ag-agent)
```
ag-agent ask "question"                   # Ask in current conversation
ag-agent ask "question" --session my-task  # Ask in specific session
ag-agent ask "question" --new              # Create new conversation first
ag-agent session list/connect/show         # Session management
ag-agent status                            # System status
```
- Event-driven (no timeouts, condition-based monitoring)
- Clipboard FIFO queue (multi-agent safe)
- Session history preservation

---

## 2. Design Premises (Verified)

- **Agent Panel only** — Agent Manager excluded
- **Search field**: AXValue direct write ✅ (no clipboard)
- **Message input**: Clipboard + Cmd+V required (Electron limitation)
- **Response detection**: Send disappear → Cancel appear → Send reappear
- **New chat identification**: Panel title == "Agent"

---

## 3. Core Principles

### 3.1 Event-Driven — Never Wait for Time
```python
# ❌ Forbidden
time.sleep(1.0)  # "hope it's ready after 1 second"

# ✅ Correct
wait_until(lambda: condition == True)  # Watch until satisfied
```

### 3.2 No Timeouts
- No `timing:` section in config
- No iteration caps (`range(240)`)
- Wait until condition is met, indefinitely

### 3.3 Only Remaining Sleep
- `wait_until()` CPU yield tick (0.05s) — scheduler cooperation
- keydown↔keyup HW gap (0.01s) — physical requirement

---

## 4. Module Structure (~1,270 lines, ~16 files)

```
src/
├── cli.py                    ← CLI (argparse)
├── core/
│   ├── events.py             ← wait_until() + 17 event catalog
│   ├── orchestrator.py       ← Main event chain
│   ├── prompt.py             ← JSON Bridge prompt builder
│   └── response.py           ← Response collection + preservation
├── ax/
│   ├── discovery.py          ← App/window discovery
│   ├── panel.py              ← Agent Panel operations
│   ├── conversations.py      ← Past Conversations overlay
│   └── input.py              ← Keyboard + ClipboardQueue
├── session/
│   ├── manager.py            ← Session CRUD + auto-connect
│   ├── storage.py            ← .ag-sessions/ filesystem
│   └── lock.py               ← Per-window exclusive lock
└── config/
    ├── loader.py             ← YAML loading
    └── defaults.py           ← Default values
```

---

## 5. Key Components

### 5.1 Event Catalog (17 Events)

| ID | Event | Condition |
|:---|:---|:---|
| E1-E3 | App/AX/Window ready | Process active, AX tree available, window found |
| E4-E7 | Panel/Input ready | Title readable, input found, focused, text pasted |
| E8-E10 | Response lifecycle | Send gone, Cancel appeared, Send back |
| E11 | Response file | File exists on disk |
| E12-E15 | Overlay operations | Opened, filtered, switched, closed |
| E16 | Clipboard turn | My ticket is front of FIFO queue |
| E17 | New chat | Panel title == "Agent" |

### 5.2 ClipboardQueue (Ticket-Based FIFO)
```
/tmp/.ag-clipboard-queue/tickets/
├── 0001_pidA     ← First in line
├── 0002_pidB     ← Waiting
└── 0003_pidC     ← Waiting

Flow: Take ticket → wait_until(my_turn) → paste → destroy ticket
```

### 5.3 Session Storage
```
{workspace}/.ag-sessions/
├── config.yaml
├── active_session              ← Last used session ID
└── sessions/{id}/
    ├── metadata.json           ← 10 fields (id, panel_title, tags, etc.)
    ├── history.jsonl           ← Turn-by-turn history
    └── responses/001.json      ← Full response data (preserved)
```

### 5.4 Config (No Timing Section)
```yaml
process:
  bundle_id: "com.google.antigravity"
ax:
  input_box_dom_id: "antigravity.agentSidePanelInputBox"
  send_button_desc: "Send message"
  cancel_button_desc: "Cancel"
  search_placeholder: "Select a conversation"
response:
  use_json_bridge: true
```

---

## 6. Implementation Phases

### Phase 1: Foundation — Event system + module separation + basic ask
- `core/events.py`, `ax/discovery.py`, `ax/panel.py`, `ax/input.py`
- `core/orchestrator.py`, `core/prompt.py`, `core/response.py`
- `config/defaults.py`, `cli.py`, `__main__.py`
- **Verify**: `python -m src ask "hello"` works with event chain

### Phase 2: Conversation Routing — Search + switch + create
- `ax/conversations.py`, panel overlay controls
- `--new` and `--session` options
- Events E12-E15, E17

### Phase 3: Session Management — History + auto-connect
- `session/storage.py`, `session/manager.py`, `session/lock.py`
- `config/loader.py` (YAML)
- Session-specific response paths, preservation instead of deletion

### Phase 4: Clipboard Queue + Stabilization
- `ax/input.py` ClipboardQueue (ticket FIFO)
- Event E16, error recovery, Cancel support
- `status` and `debug tree` commands

---

## 7. Reference Documents (Consolidated Into This)

| Document | Status |
|:---|:---|
| `agent_panel_vs_manager_*.md` | → Manager excluded |
| `pre_investigation_results_*.md` | → Reflected in premises |
| `implementation_plan_*.md` | → **Replaced by this document** |
| `implementation_supplement_*.md` | → Merged |
| `event_driven_design_*.md` | → Merged |
