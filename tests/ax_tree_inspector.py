#!/usr/bin/env python3
"""
Antigravity IDE AX Tree Inspector
─────────────────────────────────
Agent 패널의 대화 타이틀, AX 역할(Role), 사용 가능한 액션을 탐색하여
서브 에이전트 세션 라우팅에 필요한 AX 구조를 파악하는 진단 스크립트.
"""

import sys
import json
import os
from datetime import datetime

try:
    from AppKit import NSWorkspace
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        AXUIElementCopyAttributeNames,
        AXUIElementCopyActionNames,
        AXUIElementPerformAction,
        kAXWindowsAttribute,
        kAXChildrenAttribute,
        kAXRoleAttribute,
        kAXDescriptionAttribute,
        kAXTitleAttribute,
        kAXValueAttribute,
        kAXSubroleAttribute,
        kAXRoleDescriptionAttribute,
        kAXIdentifierAttribute,
    )
except ImportError:
    print("Error: pyobjc not available")
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"

BUNDLE_IDS = (
    "com.google.antigravity",
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "ax_inspection_result.json")


# ── AX Utilities ─────────────────────────────────────

def get_attr(element, attribute):
    err, val = AXUIElementCopyAttributeValue(element, attribute, None)
    if err == 0:
        return val
    return None


def get_all_attr_names(element):
    err, names = AXUIElementCopyAttributeNames(element, None)
    if err == 0:
        return list(names) if names else []
    return []


def get_actions(element):
    err, actions = AXUIElementCopyActionNames(element, None)
    if err == 0:
        return list(actions) if actions else []
    return []


def safe_str(val):
    if val is None:
        return None
    try:
        return str(val)
    except Exception:
        return f"<{type(val).__name__}>"


# ── Inspector Core ───────────────────────────────────

def inspect_element(element, depth=0, max_depth=15, path=""):
    """AX 요소를 재귀적으로 탐색하여 구조 정보를 수집"""
    if depth > max_depth:
        return {"_truncated": True, "_path": path}

    role = safe_str(get_attr(element, kAXRoleAttribute))
    subrole = safe_str(get_attr(element, kAXSubroleAttribute))
    title = safe_str(get_attr(element, kAXTitleAttribute))
    desc = safe_str(get_attr(element, kAXDescriptionAttribute))
    role_desc = safe_str(get_attr(element, kAXRoleDescriptionAttribute))
    identifier = safe_str(get_attr(element, kAXIdentifierAttribute))
    value = safe_str(get_attr(element, kAXValueAttribute))
    actions = get_actions(element)

    # 값이 너무 길면 잘라냄
    if value and len(value) > 200:
        value = value[:200] + "..."

    node = {
        "_path": path,
        "role": role,
    }

    # 의미 있는 속성만 포함
    if subrole:
        node["subrole"] = subrole
    if title:
        node["title"] = title
    if desc:
        node["description"] = desc
    if role_desc:
        node["roleDescription"] = role_desc
    if identifier:
        node["identifier"] = identifier
    if value:
        node["value"] = value
    if actions:
        node["actions"] = actions

    # 자식 탐색
    children = get_attr(element, kAXChildrenAttribute)
    if children and len(children) > 0:
        node["childCount"] = len(children)
        node["children"] = []
        for i, child in enumerate(children):
            child_path = f"{path}/{role}[{i}]" if path else f"{role}[{i}]"
            child_info = inspect_element(child, depth + 1, max_depth, child_path)
            node["children"].append(child_info)

    return node


def find_interesting_elements(element, depth=0, max_depth=25, results=None):
    """관심 있는 AX 요소를 찾아 수집 (대화 목록, 입력 영역, 버튼 등)"""
    if results is None:
        results = {
            "message_inputs": [],
            "lists": [],
            "tab_groups": [],
            "buttons_with_titles": [],
            "static_texts_in_lists": [],
            "identifiers": [],
        }

    if depth > max_depth:
        return results

    role = safe_str(get_attr(element, kAXRoleAttribute))
    desc = safe_str(get_attr(element, kAXDescriptionAttribute))
    title = safe_str(get_attr(element, kAXTitleAttribute))
    identifier = safe_str(get_attr(element, kAXIdentifierAttribute))
    subrole = safe_str(get_attr(element, kAXSubroleAttribute))
    actions = get_actions(element)
    value = safe_str(get_attr(element, kAXValueAttribute))

    # 식별자가 있는 모든 요소 수집
    if identifier:
        results["identifiers"].append({
            "role": role,
            "identifier": identifier,
            "title": title,
            "description": desc,
            "depth": depth,
        })

    # Message input 영역
    if role == "AXTextArea" and desc == "Message input":
        results["message_inputs"].append({
            "role": role,
            "description": desc,
            "actions": actions,
            "depth": depth,
        })

    # AXList (대화 목록 컨테이너 후보)
    if role == "AXList":
        list_children = get_attr(element, kAXChildrenAttribute)
        child_count = len(list_children) if list_children else 0
        child_preview = []
        if list_children:
            for c in list_children[:5]:
                c_role = safe_str(get_attr(c, kAXRoleAttribute))
                c_title = safe_str(get_attr(c, kAXTitleAttribute))
                c_desc = safe_str(get_attr(c, kAXDescriptionAttribute))
                c_value = safe_str(get_attr(c, kAXValueAttribute))
                c_actions = get_actions(c)
                child_preview.append({
                    "role": c_role,
                    "title": c_title,
                    "description": c_desc,
                    "value": c_value[:100] if c_value else None,
                    "actions": c_actions,
                })
        results["lists"].append({
            "role": role,
            "title": title,
            "description": desc,
            "identifier": identifier,
            "childCount": child_count,
            "children_preview": child_preview,
            "actions": actions,
            "depth": depth,
        })

    # AXTabGroup (탭 그룹)
    if role == "AXTabGroup":
        results["tab_groups"].append({
            "role": role,
            "title": title,
            "description": desc,
            "identifier": identifier,
            "actions": actions,
            "depth": depth,
        })

    # 타이틀이 있는 버튼 (Send, New Chat 등)
    if role == "AXButton" and (title or desc):
        results["buttons_with_titles"].append({
            "title": title,
            "description": desc,
            "actions": actions,
            "depth": depth,
        })

    # 자식 탐색
    children = get_attr(element, kAXChildrenAttribute)
    if children:
        for child in children:
            find_interesting_elements(child, depth + 1, max_depth, results)

    return results


# ── Main ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🔍 Antigravity AX Tree Inspector")
    print("=" * 60)

    # 1. 앱 탐색
    workspace = NSWorkspace.sharedWorkspace()
    target_app = None
    for app in workspace.runningApplications():
        bid = app.bundleIdentifier()
        if bid and bid in BUNDLE_IDS:
            target_app = app
            break

    if not target_app:
        print("❌ Antigravity/VS Code not running")
        sys.exit(1)

    pid = target_app.processIdentifier()
    name = target_app.localizedName()
    bundle_id = target_app.bundleIdentifier()
    print(f"\n✅ Found: {name} (PID: {pid}, Bundle: {bundle_id})")

    # 2. AX 초기화
    ax_app = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(ax_app, kAXManualAccessibility, True)

    # 3. 윈도우 정보 수집
    windows = get_attr(ax_app, kAXWindowsAttribute)
    if not windows:
        print("❌ No windows found")
        sys.exit(1)

    print(f"\n📋 Windows found: {len(windows)}")

    report = {
        "timestamp": datetime.now().isoformat(),
        "app": {"name": name, "pid": pid, "bundle_id": bundle_id},
        "windows": [],
        "interesting_elements": None,
        "deep_tree_sample": None,
    }

    for i, win in enumerate(windows):
        win_title = safe_str(get_attr(win, kAXTitleAttribute))
        win_role = safe_str(get_attr(win, kAXRoleAttribute))
        win_subrole = safe_str(get_attr(win, kAXSubroleAttribute))
        win_id = safe_str(get_attr(win, kAXIdentifierAttribute))

        print(f"\n  Window [{i}]: \"{win_title}\"")
        print(f"    Role: {win_role}, Subrole: {win_subrole}, ID: {win_id}")

        report["windows"].append({
            "index": i,
            "title": win_title,
            "role": win_role,
            "subrole": win_subrole,
            "identifier": win_id,
        })

    # 4. 첫 번째 메인 윈도우에서 관심 요소 탐색
    main_window = windows[0]
    print(f"\n🔎 Scanning main window for interesting elements...")
    interesting = find_interesting_elements(main_window)

    print(f"\n  📝 Message inputs: {len(interesting['message_inputs'])}")
    for mi in interesting["message_inputs"]:
        print(f"    - depth={mi['depth']}, actions={mi['actions']}")

    print(f"  📋 Lists (AXList): {len(interesting['lists'])}")
    for lst in interesting["lists"]:
        print(f"    - depth={lst['depth']}, children={lst['childCount']}, "
              f"title={lst['title']}, id={lst['identifier']}")
        for cp in lst["children_preview"]:
            print(f"      child: role={cp['role']}, title={cp['title']}, "
                  f"desc={cp['description']}, actions={cp['actions']}")

    print(f"  🗂️ TabGroups: {len(interesting['tab_groups'])}")
    for tg in interesting["tab_groups"]:
        print(f"    - depth={tg['depth']}, title={tg['title']}, id={tg['identifier']}")

    print(f"  🔘 Buttons with titles: {len(interesting['buttons_with_titles'])}")
    for btn in interesting["buttons_with_titles"]:
        print(f"    - \"{btn['title'] or btn['description']}\" (depth={btn['depth']})")

    print(f"  🏷️ Elements with identifiers: {len(interesting['identifiers'])}")
    for eid in interesting["identifiers"][:20]:
        print(f"    - [{eid['role']}] id=\"{eid['identifier']}\" "
              f"title=\"{eid['title']}\" (depth={eid['depth']})")
    if len(interesting["identifiers"]) > 20:
        print(f"    ... and {len(interesting['identifiers']) - 20} more")

    report["interesting_elements"] = interesting

    # 5. 첫 3 depth까지 구조 전체 덤프
    print(f"\n🌳 Dumping tree structure (depth ≤ 4)...")
    report["deep_tree_sample"] = inspect_element(main_window, max_depth=4)

    # 6. 결과 저장
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n💾 Full report saved to: {OUTPUT_FILE}")
    print(f"   File size: {os.path.getsize(OUTPUT_FILE):,} bytes")
    print("=" * 60)


if __name__ == "__main__":
    main()
