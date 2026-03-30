# Event-Driven Architecture Design — Eliminating Time Dependencies

> Date: 2026-03-29 | Implementation Plan Supplement #2
> Core Principle: **"Never wait for time. Watch until the condition is met."**

---

## 1. Current Code: All 10 `time.sleep()` Locations

```
Line │ Code                        │ Intent                 │ Issue
─────┼─────────────────────────────┼────────────────────────┼────────
L128 │ time.sleep(0.05)            │ keydown↔keyup gap      │ ✅ HW protocol (keep)
L234 │ time.sleep(0.5)             │ App activation wait    │ ❌ Hope-based
L241 │ time.sleep(1.0)             │ AX init wait           │ ❌ Hope-based
L265 │ time.sleep(0.5)             │ Focus stabilization    │ ❌ Hope-based
L268 │ time.sleep(1.0)             │ Post-paste wait        │ ❌ Hope-based
L272 │ time.sleep(1.0)             │ Post-submit wait       │ ❌ Hope-based
L158 │ time.sleep(0.25)            │ Send disappear poll    │ ⚠️ Bounded polling
L169 │ time.sleep(0.5)             │ Send reappear poll     │ ⚠️ Bounded polling
L278 │ time.sleep(0.5)             │ Pre-collection wait    │ ❌ Hope-based
```

---

## 2. Event-Driven Replacement

### Building Block: `wait_until()`

```python
def wait_until(condition_fn, tick=0.05):
    """Watch until condition is True. No timeout. Ever."""
    while not condition_fn():
        time.sleep(tick)  # CPU yield, NOT a wait
```

### Every Step Replaced

| Step | Before (time) | After (event) |
|:---|:---|:---|
| App activation | `sleep(0.5)` | `wait_until(app.isActive)` |
| AX init | `sleep(1.0)` | `wait_until(ax_windows_exist)` |
| Focus | `sleep(0.5)` | `wait_until(input.focused)` |
| Paste | `sleep(1.0)` | `wait_until(input.value != "")` |
| Submit | `sleep(1.0)` | `wait_until(send_btn NOT found)` |
| Generation start | `range(20)` cap | `wait_until(send_disappeared)` — no cap |
| Generation done | `range(240)` cap | `wait_until(send_reappeared)` — no cap |
| Response ready | `sleep(0.5)` | `wait_until(response_file_exists)` |

---

## 3. Clipboard Queue Design

### Ticket-Based FIFO Queue (Not a Lock)

```
/tmp/.ag-clipboard-queue/
├── tickets/
│   ├── 0001_pid12345    ← Agent A
│   ├── 0002_pid67890    ← Agent B
│   └── 0003_pid11111    ← Agent C
├── serving              ← Current ticket being served
└── processing.lock      ← Execution lock
```

### Sequence
1. Take ticket (numbered) → 2. `wait_until(my_turn)` → 3. Execute paste → 4. Destroy ticket → next agent proceeds

### "My Turn?" Detection = Event-Based
```python
def is_my_turn():
    tickets = sorted(os.listdir(TICKETS_DIR))
    return tickets[0].startswith(f"{my_number:04d}_")

wait_until(is_my_turn)  # No timeout, just watch
```

---

## 4. Complete Event Catalog (17 Events)

| ID | Event | Condition |
|:---|:---|:---|
| E1 | APP_ACTIVE | `app.isActive() == True` |
| E2 | AX_READY | `AXUIElement.windows != None` |
| E3 | WINDOW_FOUND | Window title contains workspace |
| E4 | PANEL_TITLE_READABLE | AXStaticText at depth=12 with AXLink siblings |
| E5 | INPUT_FOUND | `AXTextArea desc="Message input"` exists |
| E6 | INPUT_FOCUSED | `input.focused == True` |
| E7 | TEXT_PASTED | `input.value != ""` |
| E8 | SEND_DISAPPEARED | Send button gone |
| E9 | CANCEL_APPEARED | Cancel button appeared |
| E10 | SEND_REAPPEARED | Send button back |
| E11 | RESPONSE_FILE_CREATED | File exists on disk |
| E12 | OVERLAY_OPENED | Search field visible |
| E13 | SEARCH_FILTERED | Conversation count changed |
| E14 | CONVERSATION_SWITCHED | Panel title == target |
| E15 | OVERLAY_CLOSED | Search field gone |
| E16 | CLIPBOARD_TURN | My ticket is front of queue |
| E17 | NEW_CHAT_CREATED | Panel title == "Agent" |

---

## 5. Only `time.sleep()` That Remains

```python
# 1. CPU yield in wait_until() — NOT a wait, it's cooperative scheduling
time.sleep(0.05)  # 50ms tick = 20 checks/sec

# 2. HW protocol between keydown↔keyup — physical keyboard requirement
time.sleep(0.01)  # Cannot be replaced by events
```

---

## 6. Implementation Plan Changes

| Item | Before | After |
|:---|:---|:---|
| `config.yaml timing:` section | Included | **Removed entirely** |
| Response timeout | 120 second cap | **No timeout** — wait until done |
| Clipboard protection | flock lock | **ClipboardQueue** (ticket FIFO) |
| All sleep() calls | "wait N seconds" | `wait_until(condition)` |
