"""
core/response.py — 응답 수집 + 출력

AX Tree에서 추출한 구조화된 응답을 처리한다.
세션이 있으면 응답을 파일로 보존한다.
"""

import json
import os

from src.ax.ax_response import extract_response


def collect_response(window, save_path=None):
    """
    AX Tree에서 에이전트 응답을 추출한다.

    Args:
        window: AX 윈도우 레퍼런스
        save_path: 응답을 저장할 경로 (세션용, 선택)

    Returns:
        dict or None: 구조화된 응답
    """
    data = extract_response(window)
    if not data:
        return None

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    return data


def get_response_save_path(session_dir, turn):
    """
    세션 응답 파일 경로를 생성한다.

    Args:
        session_dir: 세션 디렉토리
        turn: 턴 번호

    Returns:
        str: 응답 파일 절대 경로
    """
    responses_dir = os.path.join(session_dir, "responses")
    os.makedirs(responses_dir, exist_ok=True)
    return os.path.join(responses_dir, f"{turn:03d}.json")


def print_response(data):
    """구조화된 응답을 콘솔에 출력한다."""
    if not data:
        print("⚠️  응답 없음")
        return

    answer = data.get("markdown_answer", "")
    thinking = data.get("thinking", "")
    actions = data.get("actions", [])
    files = data.get("files_modified", [])

    print("\n" + "=" * 50)
    print("🤖 Agent Response")
    print("=" * 50)

    if thinking:
        print(f"\n🧠 Thinking:\n{thinking[:500]}\n")

    if actions:
        print("🛠️ Actions:")
        for a in actions:
            action_type = a.get("type", "")
            if action_type == "file_edit":
                fname = a.get("file", "?")
                adds = a.get("additions", "")
                dels = a.get("deletions", "")
                print(f"  📄 {fname} (+{adds} -{dels})")
            elif action_type == "command":
                cmd = a.get("cmd", "?")
                exit_code = a.get("exit_code", "?")
                print(f"  ▶ {cmd[:80]} (exit: {exit_code})")
                output = a.get("output", "")
                if output:
                    print(f"    → {output[:200]}")
            else:
                print(f"  • {a.get('detail', str(a))}")
        print()

    if answer:
        print(f"📝 Answer:\n{answer}\n")

    if files:
        print(f"📁 Files Modified: {', '.join(files)}\n")

    print("=" * 50)
