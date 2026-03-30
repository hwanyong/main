# 🏗️ Antigravity Sub-Agent Orchestrator — Implementation Plan

> Date: 2026-03-29 | Version: v1.0

---

## 📌 One-Line Summary

> **A CLI tool that controls Antigravity IDE's Agent Panel via AX (Accessibility) API,  
> enabling multiple sub-agents to find, input, and collect responses from their own conversations**

---

## 1. Current → Goal

### Current (ask_and_wait.py — single 284-line file)

```
Usage:   python3 ask_and_wait.py "question"
Flow:    Find app → first window → paste into Message Input → wait for response
Limits:  No conversation selection, no new chat, no session history, no concurrency
```

### Goal

```
Usage:   ag-agent ask "question"                    # ask in current conversation
         ag-agent ask "question" --session my-task   # ask in specific session
         ag-agent ask "question" --new               # create new conversation first
         ag-agent session list                       # list sessions
         ag-agent session connect my-task             # connect to previous conversation
```

---

## 2. Core Premises (Verified by Pre-Investigation)

- **Agent Panel only** (Agent Manager excluded) — handles all operations
- **Search field**: AXValue direct write works (no clipboard needed)
- **Message Input**: Clipboard + Cmd+V required (Electron limitation)
- **Response detection**: Send button disappear/reappear pattern valid
- **Concurrency**: Agent Panel per window = fully isolated

---

## 3. Module Structure

```
main/src/
├── cli.py                   ← CLI command parsing (argparse)
├── ax/                      ← macOS Accessibility layer
│   ├── discovery.py         ← App/window discovery
│   ├── panel.py             ← Agent Panel operations (core!)
│   ├── conversations.py     ← Past Conversations overlay
│   └── input.py             ← Keyboard/clipboard input
├── session/                 ← Session management layer
│   ├── manager.py           ← Session CRUD + auto-connect
│   ├── storage.py           ← Filesystem storage
│   └── lock.py              ← Exclusive locking (per-window)
├── core/                    ← Business logic layer
│   ├── orchestrator.py      ← Main workflow pipeline
│   ├── prompt.py            ← Prompt builder
│   └── response.py          ← Response collection/parsing
└── config/                  ← Configuration layer
    ├── loader.py            ← YAML loading + defaults
    └── defaults.py          ← Default values
```

---

## 4. Implementation Phases

### Phase 1: Foundation — Module separation + basic operation
- Extract existing code into modular structure
- Window selection, basic ask pipeline
- Verify: `python -m src ask "hello"` works identically to current

### Phase 2: Conversation Routing — Search + switch + create
- Past Conversations overlay: search, select
- New conversation creation via links[0]
- `--new` and `--session` options

### Phase 3: Session Management — History + auto-connect
- `.ag-sessions/` directory structure
- metadata.json + history.jsonl per session
- fcntl.flock-based locking
- config.yaml support

### Phase 4: Stabilization — Error recovery + state detection
- Retry logic for AX element discovery
- Timeout handling with Cancel option
- State machine: INIT → CONNECTING → READY → SENDING → WAITING → DONE
- `status` and `debug tree` commands

---

## 5. Estimated Scale

| Module | Files | ~Lines | Difficulty |
|:---|:---|:---|:---|
| ax/ | 4 | ~410 | 🟠 Medium |
| session/ | 3 | ~220 | 🟢 Easy |
| core/ | 3 | ~300 | 🟠 Medium |
| config/ | 2 | ~90 | 🟢 Easy |
| cli | 1 | ~100 | 🟢 Easy |
| **Total** | **~15** | **~1,120** | — |

From 284 lines (single file) → ~1,120 lines (modular) — 4x more code, infinitely more maintainable

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|:---|:---|
| UI update breaks AX selectors | Externalize identifiers in config.yaml |
| Conversation not found in search | Click "Show N more..." then retry |
| Clipboard race condition | Minimize lock window (restore immediately after paste) |
| New chat title differs from "Agent" | Dual check: title + conversation content presence |
