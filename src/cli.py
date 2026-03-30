"""
cli.py — CLI 인터페이스

ag-agent 명령을 파싱하여 orchestrator로 전달한다.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="ag-agent",
        description="Antigravity Sub-Agent Orchestrator",
    )
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령")

    # ── ask ──────────────────────────────────────────────────
    ask_parser = subparsers.add_parser("ask", help="Agent에게 질문")
    ask_parser.add_argument("message", nargs="+", help="질문 내용")
    ask_parser.add_argument("--new", action="store_true", help="새 대화 생성")
    ask_parser.add_argument("--session", "-s", help="세션 ID")
    ask_parser.add_argument("--workspace", "-w", help="워크스페이스 경로")
    ask_parser.add_argument(
        "--no-queue", action="store_true",
        help="ClipboardQueue 비활성화 (싱글 에이전트)",
    )

    # ── session ──────────────────────────────────────────────
    session_parser = subparsers.add_parser("session", help="세션 관리")
    session_sub = session_parser.add_subparsers(
        dest="session_command", help="세션 서브커맨드"
    )

    session_sub.add_parser("list", help="세션 목록")

    connect_parser = session_sub.add_parser("connect", help="세션에 연결")
    connect_parser.add_argument("session_id", help="세션 ID")

    show_parser = session_sub.add_parser("show", help="세션 이력 보기")
    show_parser.add_argument("session_id", help="세션 ID")

    # ── status ───────────────────────────────────────────────
    status_parser = subparsers.add_parser("status", help="현재 상태")
    status_parser.add_argument("--workspace", "-w", help="워크스페이스 경로")

    # ── debug ────────────────────────────────────────────────
    debug_parser = subparsers.add_parser("debug", help="디버그 도구")
    debug_sub = debug_parser.add_subparsers(
        dest="debug_command", help="디버그 서브커맨드"
    )
    tree_parser = debug_sub.add_parser("tree", help="AX 트리 덤프")
    tree_parser.add_argument("--workspace", "-w", help="워크스페이스 경로")
    tree_parser.add_argument(
        "--depth", "-d", type=int, default=15, help="최대 깊이"
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
        print("사용법: ag-agent session {list|connect|show}")


def _handle_debug(args):
    """디버그 서브커맨드를 처리한다."""
    if args.debug_command == "tree":
        from src.core.orchestrator import debug_tree
        debug_tree(
            workspace=args.workspace,
            max_depth=args.depth,
        )
    else:
        print("사용법: ag-agent debug {tree}")


if __name__ == "__main__":
    main()
