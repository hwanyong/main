"""
cli.py — CLI 인터페이스

ag-agent 명령을 파싱하여 orchestrator로 전달한다.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="agbridge",
        description="Antigravity Bridge Daemon Client\nmacOS 기반 VS Code AI 에이전트 병렬 제어 및 메시지 큐 라우팅 도구",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어 목록")

    # ── ask ──────────────────────────────────────────────────
    ask_parser = subparsers.add_parser("ask", help="현재 워크스페이스의 에이전트에게 프롬프트(질문/지시)를 전송하고 답변을 수신합니다.")
    ask_parser.add_argument("message", nargs="+", help="에이전트에게 전달할 프롬프트 메시지 (공백 포함 가능)")
    ask_parser.add_argument("--new", action="store_true", help="강제로 기존 대화 흐름을 종료하고 완전히 새로운 세션(대화방) 생성")
    ask_parser.add_argument("--session", "-s", help="이어서 대화할 특정 세션 ID 지정 (미지정 시 최근 활성 세션 사용)")
    ask_parser.add_argument("--workspace", "-w", help="명령을 라우팅할 대상 프로젝트의 윈도우 경로 (미지정 시 현재 실행 경로)")
    ask_parser.add_argument(
        "--no-queue", action="store_true",
        help="중앙 데몬의 입력 대기열(Queue)을 무시하고 즉시 타이핑 (단일 에이전트 단독 환경 최적화용)",
    )

    # ── session ──────────────────────────────────────────────
    session_parser = subparsers.add_parser("session", help="현재 워크스페이스에 저장된 과거 대화 세션 기록을 조회하고 관리합니다.")
    session_sub = session_parser.add_subparsers(
        dest="session_command", help="세션 관리 세부 커맨드"
    )

    session_sub.add_parser("list", help="저장된 전체 세션 목록 요약 출력 (현재 활성화된 세션은 ★ 표시)")

    connect_parser = session_sub.add_parser("connect", help="특정 세션을 활성화하여 다음 번 'ask' 명령어 입력 시 대화를 이어가도록 설정")
    connect_parser.add_argument("session_id", help="연결할 대상 세션 ID")

    show_parser = session_sub.add_parser("show", help="특정 세션의 대화 내역(History) 전체를 상세 출력")
    show_parser.add_argument("session_id", help="내역을 조회할 대상 세션 ID")

    # ── status ───────────────────────────────────────────────
    status_parser = subparsers.add_parser("status", help="백그라운드 데몬 구동 여부 및 현재 워크스페이스(창)와의 연결 상태를 확인합니다.")
    status_parser.add_argument("--workspace", "-w", help="상태를 확인할 대상 프로젝트 경로")

    # ── info ─────────────────────────────────────────────────
    info_parser = subparsers.add_parser("info", help="현재 챗봇 모델, 워크플로우 트리 등 레지스트리(Cache)에 저장된 AI 런타임 환경 정보를 출력합니다.")
    info_parser.add_argument("--workspace", "-w", help="정보를 조회할 대상 프로젝트 경로")
    info_parser.add_argument("--refresh", action="store_true", help="기존 레지스트리 캐시를 삭제하고 VS Code 브라우저에서 최신 상태를 강제로 스크래핑하여 갱신")

    # ── debug ────────────────────────────────────────────────
    debug_parser = subparsers.add_parser("debug", help="[개발자 전용] macOS Accessibility(AX) 트리 분석 및 로우레벨 덤프 유틸리티")
    debug_sub = debug_parser.add_subparsers(
        dest="debug_command", help="디버깅 세부 커맨드"
    )
    tree_parser = debug_sub.add_parser("tree", help="현재 포커스되어 있는 특정 창의 접근성(AXUIElement) DOM 트리 구조를 텍스트로 출력")
    tree_parser.add_argument("--workspace", "-w", help="대상을 특정할 워크스페이스 경로")
    tree_parser.add_argument(
        "--depth", "-d", type=int, default=15, help="트리를 순회하여 출력할 최대 깊이 (기본값: 15)"
    )

    # ── 파싱 ─────────────────────────────────────────────────
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # ── 명령 실행 ────────────────────────────────────────────
    if args.command == "ask":
        from src.core.orchestrator import ask
        user_input = " ".join(args.message)
        ask(
            user_input,
            workspace=args.workspace,
            session_id=args.session,
            new_conversation=args.new,
            use_queue=not args.no_queue,
        )

    elif args.command == "session":
        _handle_session(args)

    elif args.command == "status":
        from src.core.orchestrator import status
        status(workspace=args.workspace)

    elif args.command == "info":
        from src.core.orchestrator import info
        info(workspace=args.workspace, refresh=args.refresh)

    elif args.command == "debug":
        _handle_debug(args)


def _handle_session(args):
    """세션 서브커맨드를 처리한다."""
    import os
    from src.session.manager import SessionManager

    workspace = os.getcwd()
    mgr = SessionManager(workspace)

    if args.session_command == "list":
        sessions = mgr.list_all()
        if not sessions:
            print("세션 없음")
            return
        active_id = mgr.storage.get_active()
        for s in sessions:
            marker = " ★" if s["id"] == active_id else ""
            status_icon = "🟢" if s["status"] == "active" else "⚪"
            print(
                f"{status_icon} {s['id']}{marker}"
                f"  │ {s['title']}"
                f"  │ {s['total_turns']}턴"
                f"  │ {s['updated_at'][:16]}"
            )

    elif args.session_command == "connect":
        session = mgr.connect(args.session_id)
        if session:
            print(f"✅ 세션 \"{session['id']}\"에 연결됨")
            print(f"   대화: {session['panel_title']}")
        else:
            print(f"❌ 세션 \"{args.session_id}\"를 찾을 수 없음")

    elif args.session_command == "show":
        session = mgr.find(args.session_id)
        if not session:
            print(f"❌ 세션 \"{args.session_id}\"를 찾을 수 없음")
            return

        print(f"세션: {session['id']}")
        print(f"대화: {session['panel_title']}")
        print(f"상태: {session['status']}")
        print(f"턴수: {session['total_turns']}")
        print(f"생성: {session['created_at'][:16]}")
        print(f"수정: {session['updated_at'][:16]}")

        history = mgr.storage.get_history(session["id"])
        if history:
            print(f"\n── 이력 ({len(history)}건) ──")
            for entry in history:
                role = "🧑" if entry["role"] == "user" else "🤖"
                content = entry.get("content", "")[:100]
                print(f"  [{entry['turn']}] {role} {content}")

    else:
        import argparse
        parser = argparse.ArgumentParser(prog="agbridge session")
        parser.print_help()
        print("\n자세한 정보는 'agbridge session --help'를 참고하세요.")


def _handle_debug(args):
    """디버그 서브커맨드를 처리한다."""
    if args.debug_command == "tree":
        from src.core.orchestrator import debug_tree
        debug_tree(
            workspace=args.workspace,
            max_depth=args.depth,
        )
    else:
        import argparse
        parser = argparse.ArgumentParser(prog="agbridge debug")
        parser.print_help()
        print("\n자세한 정보는 'agbridge debug --help'를 참고하세요.")


if __name__ == "__main__":
    main()
