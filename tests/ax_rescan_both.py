#!/usr/bin/env python3
"""
재탐색 1: Agent Manager에서 대화 항목 진입 후 Message Input 확인
재탐색 2: Agent Panel에서 Past Conversations 버튼 → 오버랩 패널 구조 확인
"""

import sys
import json
import os
import time

try:
    from AppKit import NSWorkspace
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
    )
    from Quartz import (
        CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
        kCGHIDEventTap, kCGEventFlagMaskCommand, kCGEventFlagMaskShift,
    )
except ImportError:
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    return val if err == 0 else None

def get_actions(el):
    err, actions = AXUIElementCopyActionNames(el, None)
    return list(actions) if err == 0 and actions else []

def safe_str(val):
    if val is None: return None
    try:
        s = str(val)
        return s[:500] if len(s) > 500 else s
    except: return f"<{type(val).__name__}>"

def sim_key(keycode, cmd=False, shift=False):
    flags = 0
    if cmd: flags |= kCGEventFlagMaskCommand
    if shift: flags |= kCGEventFlagMaskShift
    e_dn = CGEventCreateKeyboardEvent(None, keycode, True)
    e_up = CGEventCreateKeyboardEvent(None, keycode, False)
    if flags:
        CGEventSetFlags(e_dn, flags)
        CGEventSetFlags(e_up, flags)
    CGEventPost(kCGHIDEventTap, e_dn)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, e_up)


def find_element(el, match_fn, depth=0, max_depth=25):
    """범용 AX 요소 탐색"""
    if depth > max_depth:
        return None
    if match_fn(el, depth):
        return el
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            found = find_element(c, match_fn, depth + 1, max_depth)
            if found:
                return found
    return None


def find_all_elements(el, match_fn, depth=0, max_depth=25, results=None):
    """범용 AX 요소 수집"""
    if results is None:
        results = []
    if depth > max_depth:
        return results
    if match_fn(el, depth):
        results.append((el, depth))
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            find_all_elements(c, match_fn, depth + 1, max_depth, results)
    return results


def collect_all_meaningful(el, depth=0, max_depth=25, results=None):
    """타이틀/desc/value가 있는 모든 요소 수집"""
    if results is None:
        results = []
    if depth > max_depth:
        return results
    role = safe_str(get_attr(el, kAXRoleAttribute))
    title = safe_str(get_attr(el, kAXTitleAttribute))
    desc = safe_str(get_attr(el, kAXDescriptionAttribute))
    value = safe_str(get_attr(el, kAXValueAttribute))
    actions = get_actions(el)

    if title or desc or value or role in ("AXTextArea", "AXTextField", "AXList"):
        results.append({
            "depth": depth, "role": role,
            "title": title, "desc": desc,
            "value": value[:200] if value and len(value) > 200 else value,
            "actions": actions,
        })
    children = get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            collect_all_meaningful(c, depth + 1, max_depth, results)
    return results


def get_app():
    ws = NSWorkspace.sharedWorkspace()
    for app in ws.runningApplications():
        bid = app.bundleIdentifier()
        if bid and bid == "com.google.antigravity":
            return app
    return None


def get_windows(app):
    pid = app.processIdentifier()
    ax = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(ax, kAXManualAccessibility, True)
    err, wins = AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute, None)
    return (ax, wins) if err == 0 else (ax, [])


def main():
    print("=" * 70)
    print("🔍 재탐색: Manager 대화 진입 + Panel Past Conversations")
    print("=" * 70)

    app = get_app()
    if not app:
        print("❌ Antigravity not running")
        sys.exit(1)

    app.activateWithOptions_(0)
    time.sleep(0.5)

    report = {}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Phase 1: Agent Manager에서 대화 항목 진입
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n━━━ Phase 1: Agent Manager — 대화 항목 진입 ━━━")

    ax, wins = get_windows(app)
    
    # Manager 윈도우 찾기
    manager_win = None
    for w in wins:
        wt = safe_str(get_attr(w, kAXTitleAttribute))
        if wt == "Manager":
            manager_win = w
            break

    if not manager_win:
        # Manager가 없으면 Cmd+E로 열기
        print("  Manager 윈도우 없음 — Cmd+E로 열기...")
        sim_key(14, cmd=True)
        time.sleep(2.0)
        ax, wins = get_windows(app)
        for w in wins:
            wt = safe_str(get_attr(w, kAXTitleAttribute))
            if wt == "Manager":
                manager_win = w
                break

    if not manager_win:
        print("  ❌ Manager 윈도우를 열 수 없음")
    else:
        print("  ✅ Manager 윈도우 발견")
        
        # 현재 활성 대화 버튼 찾기 (progress_activity가 붙은 것)
        active_btn = find_element(manager_win, lambda el, d: (
            safe_str(get_attr(el, kAXRoleAttribute)) == "AXButton" and
            safe_str(get_attr(el, kAXTitleAttribute)) and
            "progress_activity" in (safe_str(get_attr(el, kAXTitleAttribute)) or "")
        ))

        if active_btn:
            btn_title = safe_str(get_attr(active_btn, kAXTitleAttribute))
            print(f"  활성 대화 버튼: \"{btn_title}\"")
            print(f"  → AXPress 실행 (대화 진입)...")
            AXUIElementPerformAction(active_btn, "AXPress")
            time.sleep(2.0)

            # 진입 후 Manager 윈도우 재스캔
            ax, wins = get_windows(app)
            
            # Manager 윈도우 다시 찾기
            for w in wins:
                wt = safe_str(get_attr(w, kAXTitleAttribute))
                if wt == "Manager":
                    manager_win = w
                    break

            print(f"\n  === 대화 진입 후 Manager 윈도우 재스캔 ===")
            mgr_elements = collect_all_meaningful(manager_win)
            
            # Message Input / Send 찾기
            msg_inputs = [e for e in mgr_elements if e["role"] == "AXTextArea"]
            text_fields = [e for e in mgr_elements if e["role"] == "AXTextField"]
            send_btns = [e for e in mgr_elements
                         if e["role"] == "AXButton" and
                         (("Send" in (e["title"] or "")) or ("Send" in (e["desc"] or "")))]
            
            print(f"  AXTextArea: {len(msg_inputs)}")
            for mi in msg_inputs:
                print(f"    [{mi['depth']}] desc=\"{mi['desc']}\" val=\"{mi['value']}\"")
            
            print(f"  AXTextField: {len(text_fields)}")
            for tf in text_fields:
                print(f"    [{tf['depth']}] desc=\"{tf['desc']}\" val=\"{tf['value']}\"")
            
            print(f"  Send buttons: {len(send_btns)}")
            for sb in send_btns:
                print(f"    [{sb['depth']}] title=\"{sb['title']}\" desc=\"{sb['desc']}\" actions={sb['actions']}")

            # 버튼 전체 목록도 (대화 진입 후 어떤 버튼이 보이는지)
            all_btns = [e for e in mgr_elements if e["role"] == "AXButton" and (e["title"] or e["desc"])]
            print(f"\n  전체 버튼 ({len(all_btns)}개):")
            for b in all_btns[:25]:
                label = b["title"] or b["desc"] or ""
                if len(label) > 80: label = label[:80] + "..."
                print(f"    [{b['depth']}] \"{label}\"")

            report["manager_after_enter"] = {
                "text_areas": msg_inputs,
                "text_fields": text_fields,
                "send_buttons": send_btns,
                "all_buttons": all_btns[:30],
            }

            # 뒤로가기 (arrow_back)
            back_btn = find_element(manager_win, lambda el, d: (
                safe_str(get_attr(el, kAXRoleAttribute)) == "AXButton" and
                safe_str(get_attr(el, kAXTitleAttribute)) == "arrow_back"
            ))
            if back_btn:
                print("\n  ← arrow_back으로 복귀")
                AXUIElementPerformAction(back_btn, "AXPress")
                time.sleep(1.0)
        else:
            print("  ⚠️ 활성 대화 버튼 (progress_activity) 없음")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Phase 2: Agent Panel — Past Conversations 버튼
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n━━━ Phase 2: Agent Panel — Past Conversations ━━━")

    # 에디터 윈도우 포커스
    ax, wins = get_windows(app)
    editor_win = None
    for w in wins:
        wt = safe_str(get_attr(w, kAXTitleAttribute))
        if wt and wt != "Manager":
            editor_win = w
            break

    if not editor_win:
        print("  ❌ 에디터 윈도우 없음")
    else:
        wt = safe_str(get_attr(editor_win, kAXTitleAttribute))
        print(f"  에디터 윈도우: \"{wt}\"")

        # "Past Conversations" 관련 버튼 찾기
        # → desc 또는 title에 "Past" 또는 "Conversation" 또는 시계 아이콘 관련
        past_candidates = find_all_elements(editor_win, lambda el, d: (
            safe_str(get_attr(el, kAXRoleAttribute)) == "AXButton" and
            any(keyword in (safe_str(get_attr(el, kAXTitleAttribute)) or "") + 
                (safe_str(get_attr(el, kAXDescriptionAttribute)) or "")
                for keyword in ["Past", "Conversation", "History", "history", "past"])
        ))

        print(f"\n  'Past/Conversation/History' 관련 버튼: {len(past_candidates)}")
        for el, d in past_candidates:
            title = safe_str(get_attr(el, kAXTitleAttribute))
            desc = safe_str(get_attr(el, kAXDescriptionAttribute))
            actions = get_actions(el)
            print(f"    [{d}] title=\"{title}\" desc=\"{desc}\" actions={actions}")

        # 시계 아이콘 → 스크린샷에서 시계 아이콘 옆에 Past Conversations 툴팁이 보였음
        # 모든 버튼 중 depth=12~16인 것들 전부 출력
        header_buttons = find_all_elements(editor_win, lambda el, d: (
            safe_str(get_attr(el, kAXRoleAttribute)) == "AXButton" and
            10 <= d <= 16 and
            (safe_str(get_attr(el, kAXTitleAttribute)) or safe_str(get_attr(el, kAXDescriptionAttribute)))
        ))
        
        print(f"\n  Agent Panel 헤더 영역 버튼 (depth 10~16): {len(header_buttons)}")
        for el, d in header_buttons:
            title = safe_str(get_attr(el, kAXTitleAttribute))
            desc = safe_str(get_attr(el, kAXDescriptionAttribute))
            actions = get_actions(el)
            label = title or desc or ""
            if len(label) > 80: label = label[:80] + "..."
            print(f"    [{d}] title=\"{title or ''}\" desc=\"{desc or ''}\"")

        report["panel_header_buttons"] = []
        for el, d in header_buttons:
            report["panel_header_buttons"].append({
                "depth": d,
                "title": safe_str(get_attr(el, kAXTitleAttribute)),
                "desc": safe_str(get_attr(el, kAXDescriptionAttribute)),
                "actions": get_actions(el),
            })

        # Past Conversations 후보 버튼 클릭 시도
        # description에 "Past Conversations"가 있을 수 있음
        past_btn = None
        for el, d in header_buttons:
            desc = safe_str(get_attr(el, kAXDescriptionAttribute))
            title = safe_str(get_attr(el, kAXTitleAttribute))
            if desc and "Past" in desc:
                past_btn = el
                break
            if title and "Past" in title:
                past_btn = el
                break
            # 시계 아이콘 관련 (schedule, history, clock)
            if title and any(k in title for k in ["schedule", "history", "clock"]):
                past_btn = el
                break
            if desc and any(k in desc for k in ["schedule", "history", "clock"]):
                past_btn = el
                break

        if past_btn:
            desc = safe_str(get_attr(past_btn, kAXDescriptionAttribute))
            title = safe_str(get_attr(past_btn, kAXTitleAttribute))
            print(f"\n  🎯 Past Conversations 버튼 발견: title=\"{title}\" desc=\"{desc}\"")
            print(f"  → AXPress 실행...")
            AXUIElementPerformAction(past_btn, "AXPress")
            time.sleep(1.5)

            # 오버랩 패널 스캔
            ax, wins = get_windows(app)
            # 에디터 윈도우 다시 찾기
            for w in wins:
                wt2 = safe_str(get_attr(w, kAXTitleAttribute))
                if wt2 and wt2 != "Manager":
                    editor_win = w
                    break

            print(f"\n  === Past Conversations 오버랩 패널 스캔 ===")
            overlay_elements = collect_all_meaningful(editor_win)
            
            # 새로 나타난 요소들 (대화 관련)
            conv_items = [e for e in overlay_elements
                          if any(kw in (e["title"] or "") + (e["desc"] or "") + (e["value"] or "")
                                 for kw in ["Analyzing", "Verifying", "Fixing", "Committing",
                                            "conversation", "Select", "Recent"])]
            
            print(f"  대화 관련 요소: {len(conv_items)}")
            for ci in conv_items[:20]:
                role = ci["role"]
                label = ci["title"] or ci["desc"] or ci["value"] or ""
                if len(label) > 100: label = label[:100] + "..."
                print(f"    [{ci['depth']}] {role} \"{label}\" actions={ci['actions']}")

            # AXTextField (검색 필드) 확인
            search_fields = [e for e in overlay_elements if e["role"] in ("AXTextField", "AXComboBox")]
            print(f"\n  검색 필드: {len(search_fields)}")
            for sf in search_fields:
                print(f"    [{sf['depth']}] {sf['role']} desc=\"{sf['desc']}\" val=\"{sf['value']}\"")

            # 새 AXList 확인
            new_lists = [e for e in overlay_elements if e["role"] == "AXList"]
            print(f"  AXList: {len(new_lists)}")

            report["past_conversations_overlay"] = {
                "conv_items": conv_items[:30],
                "search_fields": search_fields,
                "lists": new_lists,
            }

            # Escape로 오버랩 닫기
            print("\n  Escape로 오버랩 닫기...")
            sim_key(53)  # Escape
            time.sleep(0.5)
        else:
            print("\n  ⚠️ Past Conversations 버튼을 찾지 못함")
            print("  → 모든 버튼의 title/desc를 다시 검토:")
            for el, d in header_buttons:
                title = safe_str(get_attr(el, kAXTitleAttribute))
                desc = safe_str(get_attr(el, kAXDescriptionAttribute))
                print(f"    [{d}] t=\"{title}\" d=\"{desc}\"")

    # 저장
    out_file = os.path.join(OUTPUT_DIR, "rescan_manager_panel.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 Saved: {out_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
