#!/usr/bin/env python3
"""
Agent Panel 헤더 영역의 대화 타이틀 AX 탐색
──────────────────────────────────────────
스크린샷에서 보이는 요소:
  1. "integrate_antigravity ∨"  (워크스페이스 드롭다운)
  2. "Analyzing Antigravity Proj... now"  (대화 타이틀 + 시간)
  3. "Open Agent Manager" 
  4. "∨ Agent" (섹션 헤더)
  5. "Analyzing Antigravity Project Architecture" (전체 타이틀)
  6. +, 시계, 레이아웃, ..., X 버튼들

이 요소들이 AX 트리에서 어떤 Role/속성으로 노출되는지 확인.
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


def get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    return val if err == 0 else None


def get_all_attr_names(el):
    err, names = AXUIElementCopyAttributeNames(el, None)
    return list(names) if err == 0 and names else []


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


def exhaustive_scan(el, depth=0, max_depth=30, results=None, search_terms=None):
    """
    모든 AX 요소를 잡아서, 특정 텍스트가 포함된 것을 찾는다.
    Role, title, description, value의 모든 조합을 검사.
    """
    if results is None:
        results = []
    if search_terms is None:
        search_terms = ["Analyzing", "integrate_antigravity", "Agent", "Open Agent Manager",
                        "Past Conversations", "conversation", "Conversation"]
    if depth > max_depth:
        return results

    role = safe_str(get_attr(el, kAXRoleAttribute))
    subrole = safe_str(get_attr(el, kAXSubroleAttribute))
    title = safe_str(get_attr(el, kAXTitleAttribute))
    desc = safe_str(get_attr(el, kAXDescriptionAttribute))
    value = safe_str(get_attr(el, kAXValueAttribute))
    actions = get_actions(el)

    # 검색어 매칭 여부 확인
    all_text = " ".join(filter(None, [title, desc, value]))
    matched = any(term in all_text for term in search_terms) if all_text else False

    if matched:
        # 매칭된 요소의 전체 속성 목록도 수집
        attr_names = get_all_attr_names(el)
        
        # 추가 속성 읽기 시도
        extra_attrs = {}
        for aname in attr_names:
            if aname not in ("AXRole", "AXSubrole", "AXTitle", "AXDescription",
                             "AXValue", "AXChildren", "AXParent", "AXPosition",
                             "AXSize", "AXTopLevelUIElement", "AXWindow"):
                aval = safe_str(get_attr(el, aname))
                if aval:
                    extra_attrs[aname] = aval

        results.append({
            "depth": depth,
            "role": role,
            "subrole": subrole,
            "title": title,
            "description": desc,
            "value": value[:300] if value and len(value) > 300 else value,
            "actions": actions,
            "attr_names": attr_names,
            "extra_attrs": extra_attrs,
            "matched_in": [t for t in search_terms if t in all_text],
        })

    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            exhaustive_scan(c, depth + 1, max_depth, results, search_terms)
    return results


def main():
    print("=" * 70)
    print("🔍 Agent Panel 헤더 타이틀 탐색")
    print("=" * 70)

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
    print(f"\nWindow: \"{win_title}\"")

    # 검색 대상 텍스트
    search_terms = [
        "Analyzing",           # 대화 타이틀의 일부
        "integrate_antigravity",  # 워크스페이스명
        "Open Agent Manager",     # 링크/버튼
        "Past Conversations",     # 히스토리 버튼
        "Agent",                  # 섹션 헤더
        "Conversation",           # 대화 관련
        "New Conversation",       # 새 대화 버튼
    ]

    print(f"\nSearching for: {search_terms}")
    print("-" * 70)

    results = exhaustive_scan(win, search_terms=search_terms)

    print(f"\n📋 Found {len(results)} matching elements:\n")

    for i, r in enumerate(results):
        print(f"  [{i}] depth={r['depth']} | {r['role']}"
              f"{' / ' + r['subrole'] if r['subrole'] else ''}")
        if r["title"]:
            print(f"       title: \"{r['title']}\"")
        if r["description"]:
            print(f"       desc:  \"{r['description']}\"")
        if r["value"]:
            val = r["value"]
            if len(val) > 100:
                val = val[:100] + "..."
            print(f"       value: \"{val}\"")
        if r["actions"]:
            print(f"       actions: {r['actions']}")
        if r["extra_attrs"]:
            for k, v in list(r["extra_attrs"].items())[:5]:
                print(f"       {k}: \"{v}\"")
        print(f"       matched: {r['matched_in']}")
        print()

    # JSON 저장
    out_file = os.path.join(OUTPUT_DIR, "panel_header_search.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"💾 Saved to: {out_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
