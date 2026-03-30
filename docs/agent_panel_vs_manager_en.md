# Agent Panel vs Agent Manager — Complete Comparison (Corrected v2)

> **Correction History**: Two errors fixed from v1
> 1. ~~Agent Manager has no Message Input~~ → ✅ **It does** (depth=15 after entering a conversation)
> 2. ~~Agent Panel cannot switch conversations~~ → ✅ **It can** (Past Conversations overlay panel)

---

## 1. Feature Comparison

| Feature | Agent Panel | Agent Manager |
|:---|:---|:---|
| **Instance** | Independent per window ✅ | App-wide singleton ⚠️ |
| **Concurrent access** | Safe — fully isolated | Dangerous — mutex required |
| **Message Input** | ✅ depth≈17 | ✅ depth=15 (after entering conversation) |
| **Send Button** | ✅ `"Send message"` (depth=16) | ✅ (appears when input has content) |
| **Current title** | ✅ `AXStaticText` depth=12 | ✅ Embedded in button title |
| **Switch conversation** | ✅ Past Conversations overlay | ✅ Direct conversation list click |
| **Create conversation** | ✅ `AXLink[0]` (+ button) | ✅ `"add New Conversation"` button |
| **Search** | ✅ Search field in overlay | ✅ `"Conversation History"` button |
| **Workspace grouping** | ✅ Grouped in overlay | ✅ Workspace folder view |
| **Mode selection** | ✅ Planning/Code toggle | ❌ Not available |
| **Model selection** | ✅ Claude Opus, etc. | ❌ Not available |

---

## 2. AX Tree Mapping

### 2.1 Agent Panel (Embedded in Editor Window)

```
[depth=12] AXGroup (Agent Panel header)
├── AXStaticText value="<conversation title>"    ← current title
├── AXLink ─────── + New Conversation             ← links[0]
├── AXLink ─────── ⏰ Past Conversations           ← links[1] ★
├── AXPopUpButton ─ ⋯ More menu
├── AXLink ─────── Other
└── AXGroup id="conversation" ── conversation area
    └── AXGroup id="antigravity.agentSidePanelInputBox"
        ├── AXPopUpButton "Add context"
        ├── AXPopUpButton "Select conversation mode, current: Planning"
        ├── AXPopUpButton "Select model, current: Claude Opus 4.6 (Thinking)"
        ├── AXButton "Record voice memo"
        └── AXButton "Send message"
```

> **Note**: AXLink buttons have **empty title/desc**. Identified by index order only.

#### Past Conversations Overlay (opens after links[1] AXPress)

```
[depth=14] Overlay conversation items (AXStaticText)
├── "Running in <workspace>"
│   └── "<title>" + "<time>"
├── "Recent in <workspace>"
│   ├── "<title 1>" + "<time>"
│   └── "<title 2>" + "<time>"
├── "Other Conversations"
│   ├── "<title>" + "<workspace>" + "<time>"
│   └── ...
└── "Show <N> more..."
```

- Conversation items are **clickable at depth=13** (AXPress switches to that conversation)
- **Closed with Escape key**

---

### 2.2 Agent Manager (Singleton Window, Cmd+E)

#### Conversation List View (default)
```
[depth=10] Navigation buttons
├── "arrow_back" / "arrow_forward"
├── "add New Conversation"
├── "history Conversation History"
├── "import_contacts Knowledge"
├── "settings Settings"
└── "lightbulb Provide Feedback"

[depth=11] Conversation items (AXButton)
├── "progress_activity <title> now"    ← currently running
├── "<title> <time>"                    ← completed
├── "Open Workspace"
└── "See all (<N>)"
```

#### Conversation Detail View (after clicking a conversation)
```
[depth=15] AXTextArea desc="Message input"    ← message input available!
[depth=15+] Conversation content, undo buttons, etc.
```

- **Exit**: `arrow_back` button (depth=10)

---

## 3. Verified Test Results

### 3.1 Past Conversations Full Flow (✅ Verified)

| Step | Action | Result |
|:---|:---|:---|
| 1 | Check current title | `"Agent"` (empty new chat) |
| 2 | links[1] AXPress → overlay opens | ✅ 6 conversations displayed |
| 3 | Click conversation item (depth=13) | ✅ Click successful |
| 4 | Check title after switch | `"Analyzing Antigravity..."` ✅ |
| 5 | Reopen Past Conversations | ✅ Same overlay |
| 6 | Click original conversation → return | ✅ Title matches |

### 3.2 Agent Manager Message Input (✅ Verified)

```
Conversation button AXPress → detail view → AXTextArea desc="Message input" found (depth=15)
```

---

## 4. Concurrency Analysis (Multi Sub-Agent)

### Agent Panel — Safe ✅
Each workspace window has its own independent Agent Panel. Multiple sub-agents can operate simultaneously without any state interference.

### Agent Manager — Dangerous ⚠️
Single shared window. Two sub-agents accessing simultaneously will corrupt each other's state.

---

## 5. Final Architecture Recommendation

### Primary Path: Agent Panel ONLY

**Agent Panel alone can handle all core operations:**

1. **Check current conversation**: depth=12 AXStaticText (identified by AXLink sibling presence)
2. **Switch conversation**: links[1] AXPress → overlay → select conversation
3. **Create new conversation**: links[0] AXPress
4. **Send message**: Find `id="antigravity.agentSidePanelInputBox"` → AXTextArea + "Send message"
5. **Set mode/model**: AXPopUpButton within same AXGroup

### Secondary Path: Agent Manager (mutex-protected)

Use only when:
- Target conversation not found in Past Conversations overlay
- Cross-workspace conversation search needed
- Agent Panel has UI bugs (e.g., workflow items not showing)

---

## 6. Identifier Reference

### Header Buttons (empty title/desc → identified by order)

```python
siblings = parent_of_title.children
links = [s for s in siblings if s.role == "AXLink"]
NEW_CONVERSATION = links[0]      # + button
PAST_CONVERSATIONS = links[1]    # ⏰ clock icon
```

### Input Box (stable via DOM ID)

```python
input_box = find_by_domid("antigravity.agentSidePanelInputBox")
send_btn = find_child(input_box, role="AXButton", title="Send message")
mode_btn = find_child(input_box, role="AXPopUpButton", title_contains="conversation mode")
model_btn = find_child(input_box, role="AXPopUpButton", title_contains="Select model")
```

### Past Conversations Items

```python
# Clickable at depth=13 → extract conversation title from child texts
# Exclude: 'Running in', 'Recent in', 'Other Conversations', 'Show ', 'AI may make mistakes'
```
