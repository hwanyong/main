"""
core/orchestrator.py — 메인 이벤트 체인

모든 워크플로우를 이벤트 기반으로 조율한다.
time.sleep()은 core/events.py의 wait_until() 내부에만 존재한다.
"""

import os
import sys
import time

from src.ax.discovery import (
    find_antigravity,
    activate_and_wait,
    raise_window,
    enable_ax,
    wait_for_windows,
    find_window_by_workspace,
)
from src.ax.panel import (
    get_panel_title,
    wait_for_message_input,
    focus_message_input,
    find_send_button,
    get_conversation_state,
    click_new_conversation,
    wait_for_idle,
)
from src.ax.conversations import select_conversation
from src.ax.client import push_prompt
from src.ax.blockers import dismiss_all_blockers
from src.ax.settings import select_model, select_mode
from src.ax.typeahead import select_workflow, insert_mentions
from src.core.events import wait_until
from src.core.prompt import build_prompt
from src.core.prompt_parser import parse_prompt
from src.core.workflows import get_workflows
from src.core.response import (
    collect_response,
    get_response_save_path,
    print_response,
)
from src.session.manager import SessionManager
from src.session.lock import WindowLock



# ── Ask 워크플로우 ──────────────────────────────────────────

def ask(user_input, workspace=None, session_id=None,
        new_conversation=False, use_queue=True):
    """
    메인 ask 워크플로우: 이벤트 체인으로 동작.

    프롬프트 내 지시어를 파싱하여 자동으로 GUI 설정을 변경한다.
      @[/code]              → 워크플로우 선택
      @[src/cli.py]         → @mention 삽입
      [model: Gemini 3 Flash] → 모델 변경
      [mode: fast]          → 모드 변경

    Args:
        user_input: 사용자 질문 (지시어 포함 가능)
        workspace: 워크스페이스 경로 (None이면 자동 감지)
        session_id: 세션 ID (None이면 현재 대화 사용)
        new_conversation: True면 새 대화 생성
        use_queue: True면 ClipboardQueue 사용 (멀티에이전트)
    """
    start_time = time.monotonic()

    # ── E0: PROMPT_PARSED ────────────────────────────────────
    parsed = parse_prompt(user_input)
    if parsed.has_directives():
        print(f"[0/10] 프롬프트 파싱 완료: {parsed!r:.120}")

    # ── E1: APP_ACTIVE ──────────────────────────────────────
    print("[1/10] Antigravity 탐색...")
    app, pid, ax_app = find_antigravity()
    if not app:
        print("❌ Antigravity가 실행되고 있지 않습니다.")
        sys.exit(1)

    print(f"  → PID {pid} 발견. 앱 활성화 중...")
    activate_and_wait(app)  # AX 접근을 위한 앱 레벨 활성화

    # ── E2: AX_READY ────────────────────────────────────────
    print("[2/10] AX 초기화...")
    if not enable_ax(ax_app):
        print("❌ AXManualAccessibility 설정 실패.")
        sys.exit(1)

    windows = wait_for_windows(ax_app)
    print(f"  → 윈도우 {len(windows)}개 감지")

    # ── E3: WINDOW_FOUND ────────────────────────────────────
    print("[3/10] 대상 윈도우 탐색...")
    target_window = None

    if workspace:
        # 워크스페이스 윈도우가 나타날 때까지 대기 (최대 20초)
        def find_target():
            nonlocal target_window
            target_window = find_window_by_workspace(ax_app, pid, workspace)
            return target_window is not None

        if not wait_until(find_target, timeout=20):
            print(f"❌ 워크스페이스 '{workspace}'를 포함하는 윈도우를 찾을 수 없습니다.")
            sys.exit(1)
    else:
        # 워크스페이스 미지정: 첫 번째 윈도우
        target_window = windows[0] if windows else None

    if not target_window:
        print("❌ 대상 윈도우를 찾을 수 없습니다.")
        sys.exit(1)

    # 워크스페이스 경로 추론
    workspace_path = workspace or os.getcwd()

    # ── 대화 라우팅 (잠금 불필요 — 읽기 전용) ──────────────
    print("[4/10] 대화 라우팅...")
    session_mgr = SessionManager(workspace_path)
    current_session = None
    turn = 1

    if new_conversation:
        pass  # 잠금 내부에서 처리

    elif session_id:
        current_session = session_mgr.find(session_id)
        if current_session:
            turn = session_mgr.get_next_turn(current_session["id"])
        else:
            print(f"  ⚠️ 세션 \"{session_id}\"를 찾지 못았습니다. 현재 대화 사용.")

    else:
        active = session_mgr.get_active_session()
        if active:
            current_session = active
            turn = session_mgr.get_next_turn(active["id"])
            print(f"  → 세션 \"{active['id']}\" (턴 {turn})")
        else:
            print(f"  → 현재 대화 사용")

    # 프롬프트 생성 (잠금 밖에서 준비)
    full_prompt = build_prompt(parsed.clean_text)


    # 윈도우 잠금 (같은 워크스페이스 이중 접근 방지)
    window_lock = WindowLock(workspace_path)
    window_lock.acquire()

    try:
        # ── E3.1: WINDOW_RAISED ──────────────────────────────
        print("  → 타겟 윈도우를 포그라운드로 전환...")
        raise_window(app, target_window)

        # ── E3.5: BLOCKERS_DISMISSED ─────────────────────────
        dismissed = dismiss_all_blockers(target_window)
        if dismissed:
            print(f"  → 차단 요소 해제: {dismissed}")
            print("  → 패널 재초기화 대기...")
            wait_for_idle(target_window)

        # ── 대화 라우팅 (포커스 필요한 작업) ──────────────────
        if new_conversation:
            print("  → 새 대화 생성...")
            click_new_conversation(target_window)
            panel_title = get_panel_title(target_window)
            print(f"  → 타이틀: \"{panel_title}\"")
        elif current_session:
            target_title = current_session["panel_title"]
            current_title = get_panel_title(target_window)
            if current_title != target_title:
                print(f"  → \"{target_title}\" 대화로 전환 중...")
                ok = select_conversation(target_window, target_title)
                if not ok:
                    print(f"  ⚠️ 대화 \"{target_title}\"를 찾지 못했습니다.")

        # 세션이 없으면 현재 대화로 자동 생성
        if not current_session:
            panel_title = get_panel_title(target_window) or "Agent"
            
            # Agent 등 초기 일반 타이틀일 때 덮어쓰기 방지 위해 타임스탬프 기반 ID 생성
            session_id = None
            if panel_title == "Agent":
                import datetime
                session_id = f"chat_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
            current_session = session_mgr.create(panel_title, session_id=session_id)
            turn = 1
            print(f"  → 새 세션: \"{current_session['id']}\"")
        # ── E5: INPUT_FOUND ─────────────────────────────────
        message_input = wait_for_message_input(target_window)

        # ── E5.5: SETTINGS_APPLIED ──────────────────────────
        if parsed.model:
            print(f"  → 모델 변경: {parsed.model}")
            ok = select_model(target_window, parsed.model)
            if not ok:
                print(f"  ⚠️ 모델 '{parsed.model}' 변경 실패")

        if parsed.mode:
            print(f"  → 모드 변경: {parsed.mode}")
            ok = select_mode(target_window, parsed.mode)
            if not ok:
                print(f"  ⚠️ 모드 '{parsed.mode}' 변경 실패")

        # ── E6: INPUT_FOCUSED ───────────────────────────────
        focus_message_input(message_input)

        # ── E6.5: TYPEAHEAD_APPLIED ─────────────────────────
        if parsed.workflow:
            print(f"  → 워크플로우 적용: /{parsed.workflow}")
            wf_result = select_workflow(
                target_window, message_input, parsed.workflow
            )
            if wf_result is None:
                print(f"  ⚠️ 워크플로우 Typeahead 실패. "
                      f"@[/{parsed.workflow}]를 텍스트로 주입합니다.")
                parsed.clean_text = (
                    f"@[/{parsed.workflow}] {parsed.clean_text}"
                )
                full_prompt = build_prompt(parsed.clean_text)

        if parsed.mentions:
            print(f"  → @mention {len(parsed.mentions)}개 삽입")
            results = insert_mentions(
                target_window, message_input, parsed.mentions
            )
            for i, r in enumerate(results):
                if r is None:
                    print(f"  ⚠️ mention 실패: {parsed.mentions[i]}")

        # ── E7: TEXT_PASTED & 전송 ────────────────────────────
        print(f"[6/10] 데몬에 입력 전송 요청 ({len(full_prompt)} chars)...")
        from src.ax.discovery import _ax_element_get_window_id
        cg_id = _ax_element_get_window_id(target_window)
        push_prompt(pid, cg_id, full_prompt)
        print("[7/10] 데몬 입력 처리 완료.")

        # 세션 이력: 사용자 턴 기록
        if current_session:
            session_mgr.record_user_turn(
                current_session["id"], turn, user_input,
                prompt_length=len(full_prompt),
            )

        # ── E8: SEND_DISAPPEARED (전송 확인) ─────────────────
        wait_until(lambda: find_send_button(target_window) is None)
        print("  → 전송 확인됨. 응답 생성 중...")

    finally:
        window_lock.release()

    # ══════════════════════════════════════════════════════════
    # 여기서부터는 잠금 밖 — 다른 에이전트가 병렬로 읽기 가능
    # ══════════════════════════════════════════════════════════

    # ── E10: SEND_REAPPEARED (생성 완료) ──────────────────
    print("[8/10] 응답 대기...")
    wait_for_idle(target_window)
    elapsed = time.monotonic() - start_time
    print(f"  → 응답 완료 ({elapsed:.1f}초)")

    # ── E11: AX_RESPONSE_EXTRACTED ────────────────────────
    print("[9/10] 응답 수집 (AX Tree)...")
    save_path = None
    if current_session:
        session_dir = session_mgr.storage.get_session_dir(
            current_session["id"]
        )
        save_path = get_response_save_path(session_dir, turn)

    response_data = collect_response(
        target_window, save_path=save_path
    )
    print_response(response_data)

    # 세션 이력: 어시스턴트 턴 기록
    if current_session:
        summary = ""
        if response_data:
            answer = response_data.get("markdown_answer", "")
            summary = answer[:200] if answer else str(response_data)[:200]
        session_mgr.record_assistant_turn(
            current_session["id"], turn, summary,
            response_file=save_path or "",
            duration_sec=int(elapsed),
        )
        session_mgr.increment_turns(current_session["id"])
        session_mgr.connect(current_session["id"])


# ── Status 워크플로우 ────────────────────────────────────────

def status(workspace=None):
    """현재 상태를 출력한다."""
    app, pid, ax_app = find_antigravity()
    if not app:
        print("Antigravity: 실행 중이 아님")
        return

    print(f"Antigravity: PID {pid}")

    from src.ax.discovery import list_windows
    wins = list_windows(ax_app, pid)
    print(f"윈도우: {len(wins)}개")
    for w in wins:
        title = get_panel_title(w["ax_ref"])
        state = get_conversation_state(w["ax_ref"])
        print(f"  [{state}] {w['cg_title']}")
        if title:
            print(f"         대화: \"{title}\"")

    workspace_path = workspace or os.getcwd()
    mgr = SessionManager(workspace_path)
    sessions = mgr.list_all()
    if sessions:
        print(f"\n세션: {len(sessions)}개")
        for s in sessions:
            active_id = mgr.storage.get_active()
            marker = " ★" if s["id"] == active_id else ""
            print(f"  {s['id']}{marker} — {s['title']} ({s['total_turns']}턴)")


# ── Info 워크플로우 ──────────────────────────────────────────

def info(workspace=None, refresh=False):
    """
    현재 워크스페이스에서 사용 가능한 워크플로우 통계 및
    대상 VS Code (Antigravity) 윈도우에서 지원하는 AI 모델과 모드를 덤프한다.
    """
    workspace_path = workspace or os.getcwd()
    
    # 1. 파일 시스템 기반 덤프 (Lock 불필요)
    print("── 🛠️  워크플로우 (Workflows) ──")
    wfs = get_workflows(workspace_path)
    
    if wfs["global"]:
        print("  [Global]")
        for w in wfs["global"]:
            print(f"   - {w}")
    else:
        print("  [Global] 없음")
        
    print("")
    if wfs["workspace"]:
        print("  [Workspace]")
        for w in wfs["workspace"]:
            print(f"   - {w}")
    else:
        print("  [Workspace] 없음")
    
    print("\n── 🤖 AI 모델 및 대화 모드 감지 중 ──")
    
    # 2. 레지스트리 기반 정보 조회
    from src.core.registry_init import initialize_registry
    try:
        data = initialize_registry(force=refresh)
        if not data:
            print("❌ 모델 레지스트리를 읽을 수 없습니다.")
            return

        print(f"  (버전: {data.get('antigravity_version')}, 업데이트: {data.get('last_initialized_at_utc')})")
        
        models = data.get("models", [])
        modes = data.get("modes", [])
        
        print("\n── 🧠 확인된 AI 모델 (Models) ──")
        if models:
            for m in models:
                print(f"  - {m}")
        else:
            print("  (모델 정보를 찾을 수 없습니다)")
            
        print("\n── 🔮 대화 모드 (Modes) ──")
        if modes:
            for m in modes:
                print(f"  - {m}")
        else:
             print("  (모드 정보를 찾을 수 없습니다)")

    except Exception as e:
         print(f"⚠️ 레지스트리 로드 중 오류 발생: {e}")



# ── Debug Tree 워크플로우 ────────────────────────────────────

def debug_tree(workspace=None, max_depth=15):
    """현재 윈도우의 AX 트리를 덤프한다."""
    from src.ax.panel import _get_attr, _safe_str
    from ApplicationServices import kAXChildrenAttribute, kAXRoleAttribute

    app, pid, ax_app = find_antigravity()
    if not app:
        print("Antigravity: 실행 중이 아님")
        return

    windows = wait_for_windows(ax_app)
    target = windows[0]

    if workspace:
        target = find_window_by_workspace(ax_app, pid, workspace) or target

    def dump(el, depth=0):
        if depth > max_depth:
            return
        role = _safe_str(_get_attr(el, kAXRoleAttribute))
        from ApplicationServices import kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute
        title = _safe_str(_get_attr(el, kAXTitleAttribute))
        desc = _safe_str(_get_attr(el, kAXDescriptionAttribute))
        val = _safe_str(_get_attr(el, kAXValueAttribute))
        domid = _safe_str(_get_attr(el, "AXDOMIdentifier"))

        parts = [f"[{depth:2d}] {'  ' * depth}{role}"]
        if title:
            parts.append(f't="{title[:60]}"')
        if desc:
            parts.append(f'd="{desc[:60]}"')
        if val and len(val) < 80:
            parts.append(f'v="{val[:60]}"')
        if domid:
            parts.append(f'id="{domid}"')
        print(" ".join(parts))

        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                dump(c, depth + 1)

    dump(target)
