# Pre-Investigation Results Report

> Investigation Date: 2026-03-29 | Target: Agent Panel Only (Agent Manager excluded)
> All items verified with actual automation

---

## Investigation 1: Past Conversations Search Field ✅

| Item | Result |
|:---|:---|
| **Search Field** | `AXTextField placeholder="Select a conversation"` (depth=14) |
| **AXValue Direct Write** | ✅ `err=0`, value actually changed |
| **Filtering** | ✅ Typing `"Verifying"` → 10 items → 2 items |
| **Clipboard Required** | ❌ Not needed — AXValue direct write works |

### Search Code Pattern

```python
search_field = find_by_role_placeholder("AXTextField", "Select a conversation")
AXUIElementSetAttributeValue(search_field, kAXFocusedAttribute, True)
AXUIElementSetAttributeValue(search_field, kAXValueAttribute, "search term")
# Results filter automatically, click depth=13 items
```

---

## Investigation 2: New Conversation Creation (links[0] AXPress) ✅

| Item | Result |
|:---|:---|
| **Trigger** | `links[0]` (first AXLink in header) AXPress |
| **Title Change** | `"Analyzing Antigravity..."` → `"Agent"` (empty new chat) |
| **Header Structure** | Identical (6 elements) |
| **Message Input** | ✅ Present (depth=18) |
| **Input Box DOM ID** | ✅ `antigravity.agentSidePanelInputBox` |
| **Input Box Children** | 7: AXGroup×2, Add context, Mode, Model, Voice, Send |
| **Recovery** | ✅ Past Conversations → click original = normal recovery |

### New Chat Identification

```python
title = get_panel_title(editor)
is_new_empty_chat = (title == "Agent")
```

---

## Investigation 3: Message Input AXValue Direct Write ❌

| Item | Result |
|:---|:---|
| **AXValue Direct Write** | ❌ err=0 returned but value unchanged |
| **Cause** | Electron/Chromium AXTextArea doesn't support AXValue write |
| **Clipboard Paste** | ✅ Cmd+V works correctly |
| **Clear** | ✅ Cmd+A + Delete works |

### Input Method Split

| Element | Method | Reason |
|:---|:---|:---|
| **Search Field** (AXTextField) | AXValue direct write ✅ | Standard text field |
| **Message Input** (AXTextArea) | Clipboard + Cmd+V ☑️ | Electron limitation |

> **Clipboard pollution**: User's clipboard is overwritten. 
> Backup → input → restore pattern required.

---

## Investigation 4: Response Completion Detection ✅

### AX Element Changes by State (Verified)

| State | Send Button | Cancel Button | Status Text |
|:---|:---|:---|:---|
| **idle** | ✅ Present | ❌ None | None |
| **generating** | ❌ Disappears | ✅ Appears (depth=16) | `"Running"` (depth=16) |
| **thinking** | ❌ Disappears | ✅ Appears | `"Thought for Ns"` (depth=18) |

### Detection Strategy

```python
def wait_for_generation(editor):
    # Phase 1: Send button disappears (generation started)
    # Phase 2: Monitor Cancel/"Running" (optional progress logging)
    # Phase 3: Send button reappears (generation complete)
```

### Additional: Cancel Button
- **depth=16**: `desc="Cancel"` — Panel-level cancel
- **depth=20**: `t="Cancel"` — Individual command cancel

---

## Summary

| # | Item | Result | Implementation Impact |
|:---|:---|:---|:---|
| 1 | Search field filtering | ✅ AXValue direct write | No clipboard needed, stable search |
| 2 | New conversation creation | ✅ links[0] AXPress | Title "Agent" identifies new chat |
| 3 | Message Input direct write | ❌ Electron limitation | Clipboard method required (backup/restore) |
| 4 | Response completion detection | ✅ Send disappear/reappear | Existing method valid + Cancel enhancement |

### Key Design Decisions

1. **Dual input approach**: Search = AXValue, Message = Clipboard
2. **Clipboard preservation**: Backup/restore mandatory
3. **State detection triad**: Send button (idle), Cancel button (generating), Running text (progress)
4. **New chat identification**: Title == "Agent" → empty new conversation
