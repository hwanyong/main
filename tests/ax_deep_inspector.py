#!/usr/bin/env python3
"""
Antigravity AX Deep Inspector — Agent Panel Focus
──────────────────────────────────────────────────
Agent 패널의 대화 이력, 대화 타이틀, 사용 가능 버튼을 심층 탐색.
"""

import sys
import json
import os

try:
    from AppKit import NSWorkspace
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        AXUIElementCopyAttributeNames,
        AXUIElementCopyActionNames,
        kAXWindowsAttribute,
        kAXChildrenAttribute,
        kAXRoleAttribute,
        kAXDescriptionAttribute,
        kAXTitleAttribute,
        kAXValueAttribute,
        kAXSubroleAttribute,
    )
except ImportError:
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"
BUNDLE_IDS = ("com.google.antigravity",)
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_attr(element, attribute):
    err, val = AXUIElementCopyAttributeValue(element, attribute, None)
    return val if err == 0 else None


def get_actions(element):
    err, actions = AXUIElementCopyActionNames(element, None)
    return list(actions) if err == 0 and actions else []


def get_all_attrs(element):
    err, names = AXUIElementCopyAttributeNames(element, None)
    return list(names) if err == 0 and names else []


def safe_str(val):
    if val is None:
        return None
    try:
        s = str(val)
        return s[:300] if len(s) > 300 else s
    except Exception:
        return f"<{type(val).__name__}>"


def find_element_by_desc(element, target_role, target_desc, depth=0, max_depth=30):
    if depth > max_depth:
        return None
    role = safe_str(get_attr(element, kAXRoleAttribute))
    if role == target_role:
        desc = safe_str(get_attr(element, kAXDescriptionAttribute))
        if desc == target_desc:
            return element
    children = get_attr(element, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_element_by_desc(c, target_role, target_desc, depth + 1, max_depth)
            if found:
                return found
    return None


def find_element_by_title(element, target_role, target_title, depth=0, max_depth=30):
    if depth > max_depth:
        return None
    role = safe_str(get_attr(element, kAXRoleAttribute))
    if role == target_role:
        title = safe_str(get_attr(element, kAXTitleAttribute))
        if title and target_title in title:
            return element
    children = get_attr(element, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_element_by_title(c, target_role, target_title, depth + 1, max_depth)
            if found:
                return found
    return None


def deep_dump(element, depth=0, max_depth=8, path="root"):
    """요소의 모든 속성과 자식을 재귀적으로 덤프"""
    if depth > max_depth:
        return {"_truncated": True}

    role = safe_str(get_attr(element, kAXRoleAttribute))
    subrole = safe_str(get_attr(element, kAXSubroleAttribute))
    title = safe_str(get_attr(element, kAXTitleAttribute))
    desc = safe_str(get_attr(element, kAXDescriptionAttribute))
    value = safe_str(get_attr(element, kAXValueAttribute))
    actions = get_actions(element)

    node = {"_path": path, "role": role}
    if subrole:
        node["subrole"] = subrole
    if title:
        node["title"] = title
    if desc:
        node["description"] = desc
    if value:
        node["value"] = value
    if actions:
        node["actions"] = actions

    children = get_attr(element, kAXChildrenAttribute)
    if children and len(children) > 0:
        node["childCount"] = len(children)
        node["children"] = []
        for i, c in enumerate(children):
            child_node = deep_dump(c, depth + 1, max_depth, f"{path}/{role}[{i}]")
            node["children"].append(child_node)

    return node


def collect_all_text_elements(element, depth=0, max_depth=25, results=None):
    """AXStaticText인 모든 요소를 수집"""
    if results is None:
        results = []
    if depth > max_depth:
        return results

    role = safe_str(get_attr(element, kAXRoleAttribute))
    if role == "AXStaticText":
        value = safe_str(get_attr(element, kAXValueAttribute))
        title = safe_str(get_attr(element, kAXTitleAttribute))
        desc = safe_str(get_attr(element, kAXDescriptionAttribute))
        actions = get_actions(element)
        if value or title:
            results.append({
                "depth": depth,
                "value": value,
                "title": title,
                "description": desc,
                "actions": actions,
            })

    children = get_attr(element, kAXChildrenAttribute)
    if children:
        for c in children:
            collect_all_text_elements(c, depth + 1, max_depth, results)
    return results


def main():
    print("=" * 60)
    print("🔍 Antigravity Agent Panel Deep Inspector")
    print("=" * 60)

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

    windows = get_attr(ax_app, kAXWindowsAttribute)
    if not windows:
        print("❌ No windows")
        sys.exit(1)

    win = windows[0]
    win_title = safe_str(get_attr(win, kAXTitleAttribute))
    print(f"\n✅ Window: \"{win_title}\"")

    report = {}

    # ── Test 1: "Agent Section" 버튼 찾기 ──
    print("\n── Test 1: Agent Section 버튼 찾기 ──")
    agent_btn = find_element_by_title(win, "AXButton", "Agent Section")
    if agent_btn:
        title = safe_str(get_attr(agent_btn, kAXTitleAttribute))
        actions = get_actions(agent_btn)
        print(f"  ✅ Found: \"{title}\", actions={actions}")

        # Agent Section 버튼의 부모/형제 구조 탐색
        # 버튼 근처의 컨텍스트를 알기 위해 모든 속성 출력
        all_attr_names = []
        err, names = AXUIElementCopyAttributeNames(agent_btn, None)
        if err == 0 and names:
            all_attr_names = list(names)
        print(f"  Attributes: {all_attr_names}")
        report["agent_button"] = {"found": True, "title": title, "actions": actions, "attrs": all_attr_names}
    else:
        print("  ❌ Not found")
        report["agent_button"] = {"found": False}

    # ── Test 2: "Send message" 버튼 / Message input 영역 찾기 ──
    print("\n── Test 2: Message input / Send 버튼 ──")
    msg_input = find_element_by_desc(win, "AXTextArea", "Message input")
    if msg_input:
        actions = get_actions(msg_input)
        value = safe_str(get_attr(msg_input, kAXValueAttribute))
        print(f"  ✅ Message input found, value=\"{value}\", actions={actions}")
        report["message_input"] = {"found": True, "actions": actions}
    else:
        print("  ❌ Message input not found")
        report["message_input"] = {"found": False}

    send_btn = find_element_by_desc(win, "AXButton", "Send message")
    if send_btn:
        actions = get_actions(send_btn)
        print(f"  ✅ Send button found, actions={actions}")
        report["send_button"] = {"found": True, "actions": actions}
    else:
        print("  ⚠️ Send button not found (might be hidden when no input)")
        report["send_button"] = {"found": False}

    # ── Test 3: 대화 모드/모델 선택 버튼 ──
    print("\n── Test 3: 대화 모드/모델 선택 ──")
    mode_btn = find_element_by_title(win, "AXButton", "Select conversation mode")
    if mode_btn:
        title = safe_str(get_attr(mode_btn, kAXTitleAttribute))
        print(f"  ✅ Mode: \"{title}\"")
        report["conversation_mode"] = title

    model_btn = find_element_by_title(win, "AXButton", "Select model")
    if model_btn:
        title = safe_str(get_attr(model_btn, kAXTitleAttribute))
        print(f"  ✅ Model: \"{title}\"")
        report["model_select"] = title

    # ── Test 4: 대화 영역(채팅 패널) 심층 구조 ──
    print("\n── Test 4: 대화 영역 내 모든 AXStaticText 수집 ──")
    all_texts = collect_all_text_elements(win)
    
    # 대화 내용 관련 텍스트 필터링 (depth >= 17인 것들)
    chat_texts = [t for t in all_texts if t["depth"] >= 17]
    print(f"  Total AXStaticText: {len(all_texts)}")
    print(f"  Chat-depth texts (depth >= 17): {len(chat_texts)}")
    
    for t in chat_texts[:30]:
        val = t["value"] or t["title"] or ""
        if len(val) > 80:
            val = val[:80] + "..."
        print(f"    depth={t['depth']} | \"{val}\"")

    if len(chat_texts) > 30:
        print(f"    ... and {len(chat_texts) - 30} more")

    report["chat_texts_sample"] = chat_texts[:50]

    # ── Test 5: 대화 타이틀 후보 찾기 ──
    # "undo" 버튼 옆에 "Worked for Xm" / "Thought for Xs" 패턴이 보임
    # → 이것들은 대화 턴(turn) 정보의 일부
    print("\n── Test 5: 대화 패널 구조 (undo 버튼 주변) ──")
    
    undo_elements = []
    def find_undo_context(el, depth=0, max_depth=25):
        if depth > max_depth:
            return
        role = safe_str(get_attr(el, kAXRoleAttribute))
        title = safe_str(get_attr(el, kAXTitleAttribute))
        if role == "AXButton" and title == "undo":
            # undo 버튼의 부모를 탐색
            parent_info = {"depth": depth, "nearby": []}
            undo_elements.append(parent_info)
        children = get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                find_undo_context(c, depth + 1, max_depth)

    find_undo_context(win)
    print(f"  'undo' buttons found: {len(undo_elements)}")
    report["undo_buttons"] = len(undo_elements)

    # ── Test 6: Agent 패널 내부 (history/conversation list) ──
    print("\n── Test 6: AXList 내부 심층 덤프 (첫 3개) ──")
    
    all_lists = []
    def find_all_lists(el, depth=0, max_depth=25):
        if depth > max_depth:
            return
        role = safe_str(get_attr(el, kAXRoleAttribute))
        if role == "AXList":
            all_lists.append((el, depth))
        children = get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                find_all_lists(c, depth + 1, max_depth)

    find_all_lists(win)
    
    list_dumps = []
    for idx, (lst_el, lst_depth) in enumerate(all_lists[:3]):
        print(f"\n  AXList #{idx} (depth={lst_depth}):")
        dump = deep_dump(lst_el, max_depth=5)
        list_dumps.append(dump)
        
        # 요약 출력
        children = get_attr(lst_el, kAXChildrenAttribute)
        child_count = len(children) if children else 0
        print(f"    Children: {child_count}")
        if children:
            for ci, c in enumerate(children[:3]):
                c_role = safe_str(get_attr(c, kAXRoleAttribute))
                c_title = safe_str(get_attr(c, kAXTitleAttribute))
                c_desc = safe_str(get_attr(c, kAXDescriptionAttribute))
                c_value = safe_str(get_attr(c, kAXValueAttribute))
                c_actions = get_actions(c)
                gc = get_attr(c, kAXChildrenAttribute)
                gc_count = len(gc) if gc else 0
                print(f"    [{ci}] {c_role} title=\"{c_title}\" desc=\"{c_desc}\" "
                      f"value=\"{c_value}\" actions={c_actions} grandchildren={gc_count}")
                
                # 손자(grandchildren) 1단계 더
                if gc:
                    for gi, g in enumerate(gc[:3]):
                        g_role = safe_str(get_attr(g, kAXRoleAttribute))
                        g_title = safe_str(get_attr(g, kAXTitleAttribute))
                        g_desc = safe_str(get_attr(g, kAXDescriptionAttribute))
                        g_value = safe_str(get_attr(g, kAXValueAttribute))
                        g_actions = get_actions(g)
                        print(f"      [{ci}.{gi}] {g_role} title=\"{g_title}\" "
                              f"desc=\"{g_desc}\" value=\"{g_value}\" actions={g_actions}")

    report["list_dumps"] = list_dumps

    # 저장
    out_file = os.path.join(OUTPUT_DIR, "ax_deep_inspection.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n\n💾 Saved to: {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
