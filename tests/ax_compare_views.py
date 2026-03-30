#!/usr/bin/env python3
"""
Antigravity Agent Manager AX Inspector
───────────────────────────────────────
Agent Manager (Cmd+E) 뷰의 대화 목록 구조를 탐색.
비교: Agent Panel (채팅 뷰) vs Agent Manager 뷰.
"""

import sys
import json
import os
import time

try:
    from AppKit import NSWorkspace, NSPasteboard, NSPasteboardTypeString
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        AXUIElementCopyActionNames,
        AXUIElementPerformAction,
        kAXWindowsAttribute,
        kAXChildrenAttribute,
        kAXRoleAttribute,
        kAXDescriptionAttribute,
        kAXTitleAttribute,
        kAXValueAttribute,
        kAXSubroleAttribute,
        kAXFocusedAttribute,
    )
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGHIDEventTap,
        kCGEventFlagMaskCommand,
        kCGEventFlagMaskShift,
    )
except ImportError:
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"
BUNDLE_IDS = ("com.google.antigravity",)
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    return val if err == 0 else None


def get_actions(el):
    err, actions = AXUIElementCopyActionNames(el, None)
    return list(actions) if err == 0 and actions else []


def safe_str(val):
    if val is None:
        return None
    try:
        s = str(val)
        return s[:500] if len(s) > 500 else s
    except Exception:
        return f"<{type(val).__name__}>"


def simulate_keypress(keycode, use_cmd=False, use_shift=False):
    flags = 0
    if use_cmd:
        flags |= kCGEventFlagMaskCommand
    if use_shift:
        flags |= kCGEventFlagMaskShift

    event_down = CGEventCreateKeyboardEvent(None, keycode, True)
    event_up = CGEventCreateKeyboardEvent(None, keycode, False)

    if flags:
        CGEventSetFlags(event_down, flags)
        CGEventSetFlags(event_up, flags)

    CGEventPost(kCGHIDEventTap, event_down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, event_up)


def collect_all_elements(el, depth=0, max_depth=30, results=None):
    """모든 AX 요소를 플랫 리스트로 수집 (타이틀/설명/값이 있는 것만)"""
    if results is None:
        results = []
    if depth > max_depth:
        return results

    role = safe_str(get_attr(el, kAXRoleAttribute))
    subrole = safe_str(get_attr(el, kAXSubroleAttribute))
    title = safe_str(get_attr(el, kAXTitleAttribute))
    desc = safe_str(get_attr(el, kAXDescriptionAttribute))
    value = safe_str(get_attr(el, kAXValueAttribute))
    actions = get_actions(el)

    # 의미 있는 요소만 수집
    if title or desc or value or role in ("AXList", "AXTabGroup", "AXTextField", "AXTextArea"):
        results.append({
            "depth": depth,
            "role": role,
            "subrole": subrole,
            "title": title,
            "description": desc,
            "value": value[:200] if value and len(value) > 200 else value,
            "actions": actions,
        })

    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            collect_all_elements(c, depth + 1, max_depth, results)
    return results


def deep_dump_targeted(el, depth=0, max_depth=10):
    """타겟 요소 주변의 심층 덤프"""
    if depth > max_depth:
        return {"_truncated": True}

    role = safe_str(get_attr(el, kAXRoleAttribute))
    subrole = safe_str(get_attr(el, kAXSubroleAttribute))
    title = safe_str(get_attr(el, kAXTitleAttribute))
    desc = safe_str(get_attr(el, kAXDescriptionAttribute))
    value = safe_str(get_attr(el, kAXValueAttribute))
    actions = get_actions(el)

    node = {"role": role}
    if subrole:
        node["subrole"] = subrole
    if title:
        node["title"] = title
    if desc:
        node["description"] = desc
    if value:
        node["value"] = value[:300] if len(value) > 300 else value
    if actions:
        node["actions"] = actions

    children = get_attr(el, kAXChildrenAttribute)
    if children and len(children) > 0:
        node["childCount"] = len(children)
        node["children"] = []
        for c in children:
            node["children"].append(deep_dump_targeted(c, depth + 1, max_depth))
    return node


def find_element_by_desc(el, target_role, target_desc, depth=0, max_depth=30):
    if depth > max_depth:
        return None
    role = safe_str(get_attr(el, kAXRoleAttribute))
    if role == target_role:
        desc = safe_str(get_attr(el, kAXDescriptionAttribute))
        if desc and target_desc in desc:
            return el
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_element_by_desc(c, target_role, target_desc, depth + 1, max_depth)
            if found:
                return found
    return None


def find_element_by_title_contains(el, target_role, text, depth=0, max_depth=30):
    if depth > max_depth:
        return None
    role = safe_str(get_attr(el, kAXRoleAttribute))
    if role == target_role:
        title = safe_str(get_attr(el, kAXTitleAttribute))
        if title and text in title:
            return el
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_element_by_title_contains(c, target_role, text, depth + 1, max_depth)
            if found:
                return found
    return None


def find_text_field_by_desc(el, target_desc, depth=0, max_depth=30):
    """AXTextField / AXTextArea / AXComboBox with matching description or placeholder"""
    if depth > max_depth:
        return None
    role = safe_str(get_attr(el, kAXRoleAttribute))
    if role in ("AXTextField", "AXTextArea", "AXComboBox"):
        desc = safe_str(get_attr(el, kAXDescriptionAttribute))
        value = safe_str(get_attr(el, kAXValueAttribute))
        title = safe_str(get_attr(el, kAXTitleAttribute))
        if (desc and target_desc in desc) or (title and target_desc in title) or (value and target_desc in value):
            return el
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_text_field_by_desc(c, target_desc, depth + 1, max_depth)
            if found:
                return found
    return None


def main():
    print("=" * 70)
    print("🔍 Agent Panel vs Agent Manager 비교 탐색")
    print("=" * 70)

    # 앱 탐색
    workspace = NSWorkspace.sharedWorkspace()
    target_app = None
    for app in workspace.runningApplications():
        bid = app.bundleIdentifier()
        if bid and bid in BUNDLE_IDS:
            target_app = app
            break

    if not target_app:
        print("❌ Antigravity not running")
        sys.exit(1)

    pid = target_app.processIdentifier()
    ax_app = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(ax_app, kAXManualAccessibility, True)

    # 앱 활성화
    target_app.activateWithOptions_(0)
    time.sleep(0.5)

    report = {"agent_panel": {}, "agent_manager": {}}

    # ━━━ Phase 1: 현재 Agent Panel 상태 캡처 ━━━
    print("\n━━━ Phase 1: Agent Panel (현재 채팅 뷰) ━━━")

    windows = get_attr(ax_app, kAXWindowsAttribute)
    if not windows:
        print("❌ No windows")
        sys.exit(1)

    win = windows[0]
    panel_title = safe_str(get_attr(win, kAXTitleAttribute))
    print(f"  Window: \"{panel_title}\"")

    # Agent Panel에서 보이는 요소 수집
    panel_elements = collect_all_elements(win)
    print(f"  Total meaningful elements: {len(panel_elements)}")

    # Past Conversations 관련 요소 찾기
    past_conv_btn = find_element_by_desc(win, "AXButton", "Past Conversations")
    if past_conv_btn:
        print(f"  ✅ 'Past Conversations' button found!")
        pca = get_actions(past_conv_btn)
        print(f"     Actions: {pca}")
        report["agent_panel"]["past_conversations_button"] = {"found": True, "actions": pca}
    else:
        # title로도 시도
        past_conv_btn = find_element_by_title_contains(win, "AXButton", "Past Conversations")
        if past_conv_btn:
            print(f"  ✅ 'Past Conversations' button found (via title)!")
            report["agent_panel"]["past_conversations_button"] = {"found": True, "via": "title"}
        else:
            print(f"  ⚠️ 'Past Conversations' button not found")
            report["agent_panel"]["past_conversations_button"] = {"found": False}

    # Select a conversation 관련 요소
    select_conv = find_text_field_by_desc(win, "Select a conversation")
    if select_conv:
        print(f"  ✅ 'Select a conversation' text field found!")
        report["agent_panel"]["select_conversation"] = {"found": True}
    else:
        print(f"  ⚠️ 'Select a conversation' not found (dropdown not open)")
        report["agent_panel"]["select_conversation"] = {"found": False}

    # Message input, buttons 등 핵심 요소
    panel_buttons = [e for e in panel_elements if e["role"] == "AXButton" and (e["title"] or e["description"])]
    panel_texts = [e for e in panel_elements if e["role"] == "AXStaticText" and e["value"]]

    report["agent_panel"]["button_count"] = len(panel_buttons)
    report["agent_panel"]["text_count"] = len(panel_texts)
    report["agent_panel"]["window_title"] = panel_title

    # ━━━ Phase 2: Cmd+E로 Agent Manager 전환 ━━━
    print("\n━━━ Phase 2: Agent Manager (Cmd+E 전환) ━━━")
    print("  Simulating Cmd+E...")

    # keycode 14 = 'E'
    simulate_keypress(14, use_cmd=True)
    time.sleep(2.0)  # Agent Manager 로딩 대기

    # AX 트리 다시 스캔
    windows = get_attr(ax_app, kAXWindowsAttribute)
    if not windows:
        print("❌ No windows after Cmd+E")
        sys.exit(1)

    # 모든 윈도우 확인
    print(f"  Windows after Cmd+E: {len(windows)}")
    for i, w in enumerate(windows):
        wt = safe_str(get_attr(w, kAXTitleAttribute))
        print(f"    [{i}] \"{wt}\"")

    # 주 윈도우(또는 새 윈도우) 탐색
    manager_win = windows[0]
    manager_title = safe_str(get_attr(manager_win, kAXTitleAttribute))
    print(f"\n  Scanning window: \"{manager_title}\"")

    # Agent Manager의 모든 요소 수집
    manager_elements = collect_all_elements(manager_win)
    print(f"  Total meaningful elements: {len(manager_elements)}")

    # 대화 관련 요소 찾기
    manager_buttons = [e for e in manager_elements if e["role"] == "AXButton" and (e["title"] or e["description"])]
    manager_texts = [e for e in manager_elements if e["role"] == "AXStaticText" and e["value"]]
    manager_links = [e for e in manager_elements if e["role"] == "AXLink"]
    manager_groups = [e for e in manager_elements if e["role"] == "AXGroup" and (e["title"] or e["description"])]

    print(f"\n  Buttons: {len(manager_buttons)}")
    for b in manager_buttons[:30]:
        label = b["title"] or b["description"] or ""
        if len(label) > 80:
            label = label[:80] + "..."
        print(f"    [{b['depth']}] \"{label}\" actions={b['actions']}")

    print(f"\n  Static Texts: {len(manager_texts)}")
    for t in manager_texts[:40]:
        val = t["value"] or ""
        if len(val) > 80:
            val = val[:80] + "..."
        print(f"    [{t['depth']}] \"{val}\"")

    print(f"\n  Links: {len(manager_links)}")
    for l in manager_links[:10]:
        label = l["title"] or l["description"] or l["value"] or ""
        print(f"    [{l['depth']}] \"{label}\" actions={l['actions']}")

    print(f"\n  Named Groups: {len(manager_groups)}")
    for g in manager_groups[:10]:
        label = g["title"] or g["description"] or ""
        print(f"    [{g['depth']}] \"{label}\"")

    report["agent_manager"]["window_title"] = manager_title
    report["agent_manager"]["button_count"] = len(manager_buttons)
    report["agent_manager"]["text_count"] = len(manager_texts)
    report["agent_manager"]["link_count"] = len(manager_links)
    report["agent_manager"]["group_count"] = len(manager_groups)
    report["agent_manager"]["buttons"] = manager_buttons[:40]
    report["agent_manager"]["texts"] = manager_texts[:60]
    report["agent_manager"]["links"] = manager_links[:20]
    report["agent_manager"]["groups"] = manager_groups[:20]

    # ── 대화 목록 있는 AXList 찾기 ──
    print(f"\n  ── AXList 요소들 ──")
    manager_lists = [e for e in manager_elements if e["role"] == "AXList"]
    print(f"  AXList count: {len(manager_lists)}")

    # 대화 제목이 텍스트로 보이는지 확인
    conversation_candidates = []
    for t in manager_texts:
        val = t["value"] or ""
        # 대화 타이틀 패턴 매칭 (대문자로 시작하는 영어 구, 한글 등)
        if len(val) > 5 and t["depth"] >= 10:
            conversation_candidates.append(t)

    print(f"\n  Conversation title candidates (depth >= 10, len > 5):")
    for c in conversation_candidates[:20]:
        print(f"    [{c['depth']}] \"{c['value']}\"")

    report["agent_manager"]["conversation_candidates"] = conversation_candidates[:30]

    # ━━━ Phase 3: Cmd+E로 원래 뷰로 복귀 ━━━
    print("\n━━━ Phase 3: Cmd+E로 복귀 ━━━")
    simulate_keypress(14, use_cmd=True)
    time.sleep(1.0)
    print("  ✅ Restored to Agent Panel")

    # 저장
    out_file = os.path.join(OUTPUT_DIR, "agent_panel_vs_manager.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n💾 Saved to: {out_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
