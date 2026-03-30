"""
E2E 테스트: 사칙연산 계산기

ag-agent 파이프라인의 전체 플로우를 실제 개발 태스크로 검증한다.
Antigravity에 터미널 계산기를 만들라고 지시하고:
  1. 윈도우 식별 (CG + AX)
  2. 프롬프트 전달
  3. 응답 대기
  4. 응답 추출 (AX Tree)
  5. 생성된 파일 실행 검증
이 전체 체인이 동작하는지 검증한다.

Usage:
  PYTHONPATH="." .venv_monitor/bin/python3 tests/e2e_calculator.py
"""

import os
import sys
import time
import subprocess

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ax.discovery import (
    find_antigravity,
    activate_and_wait,
    enable_ax,
    wait_for_windows,
    find_window_by_workspace,
    raise_window,
    list_windows,
    _ax_element_get_window_id,
)
from src.ax.panel import (
    wait_for_message_input,
    focus_message_input,
    find_send_button,
    get_conversation_state,
    get_panel_title,
    wait_for_idle,
)
from src.ax.blockers import dismiss_all_blockers
from src.ax.client import push_prompt
from src.ax.ax_response import extract_response
from src.core.events import wait_until


WORKSPACE = sys.argv[1] if len(sys.argv) > 1 else (
    "/Users/uhd/LOCAL/01-01_Projects/GEMINI_CLI"
    "/playground/integrate_antigravity/calc_test"
)

PROMPT = """Python으로 간단한 사칙연산 계산기를 만들어줘.

요구사항:
- 파일명: calc.py
- 터미널에서 실행하는 CLI 앱
- +, -, *, / 네 가지 연산 지원
- 두 숫자를 입력받고 연산자를 선택해서 결과 출력
- 0으로 나누기 시 에러 메시지 출력
- "q" 입력 시 종료
- 반복 실행 (q 입력 전까지 계속)
"""

PASS = "✅"
FAIL = "❌"
results = []


def log(step, msg):
    print(f"[{step}] {msg}")


def record(name, passed, detail=""):
    marker = PASS if passed else FAIL
    results.append({"name": name, "passed": passed})
    print(f"  {marker} {name}" + (f" — {detail}" if detail else ""))


# ── E2E 플로우 ──────────────────────────────────────────────

def run():
    start = time.monotonic()

    # ── 1. 앱 탐색 ──────────────────────────────────────────
    log("1/8", "Antigravity 탐색...")
    app, pid, ax_app = find_antigravity()
    record("T01_find_antigravity", app is not None, f"PID={pid}")
    if not app:
        print("Antigravity 미실행. 중단.")
        return

    # ── 2. 활성화 & AX ──────────────────────────────────────
    log("2/8", "앱 활성화 & AX 초기화...")
    activate_and_wait(app)
    ax_ok = enable_ax(ax_app)
    time.sleep(0.5)
    record("T13_enable_ax", ax_ok)

    # ── 3. 윈도우 식별 ─────────────────────────────────────
    log("3/8", "calc_test 윈도우 탐색...")
    wins = list_windows(ax_app, pid)
    record("T07_list_windows", len(wins) >= 1, f"{len(wins)}개")

    target = find_window_by_workspace(ax_app, pid, WORKSPACE)
    if target:
        cg_id = _ax_element_get_window_id(target)
        record("T08_find_window_by_workspace", True, f"CG {cg_id}")
        record("T04_ax_get_window_id", True, f"wid={cg_id}")
    else:
        record("T08_find_window_by_workspace", False, "calc_test 윈도우 없음")
        print("calc_test 윈도우를 찾을 수 없습니다. 중단.")
        return

    # ── 4. 윈도우 포그라운드 ────────────────────────────────
    log("4/8", "윈도우 raise...")
    raise_window(app, target)
    record("T11_raise_window", True)

    # 차단 요소 해제
    dismissed = dismiss_all_blockers(target)
    if dismissed:
        log("4/8", f"차단 해제: {dismissed}")
        wait_for_idle(target)

    # ── 5. 입력 & 전송 ─────────────────────────────────────
    log("5/8", "Message Input 탐색...")
    msg_input = wait_for_message_input(target)
    record("T15_find_message_input", msg_input is not None)

    log("5/8", "포커스 설정...")
    focus_message_input(msg_input)
    record("T16_focus_message_input", True)

    log("5/8", f"프롬프트 붙여넣기 및 전송 ({len(PROMPT)} chars) (via Daemon)...")
    push_prompt(pid, cg_id, PROMPT)
    record("T20_push_prompt", True)

    state_before = get_conversation_state(target)
    record("T18_conv_state_idle", state_before == "idle", state_before)

    # Send 버튼 사라짐 확인 (전송됨)
    send_gone = wait_until(
        lambda: find_send_button(target) is None, timeout=10
    )
    record("T22_send_confirmed", send_gone)

    # ── 6. 응답 대기 ───────────────────────────────────────
    log("7/8", "응답 대기...")
    wait_for_idle(target)
    elapsed = time.monotonic() - start
    record("T18_conv_state_idle_after", get_conversation_state(target) == "idle",
           f"{elapsed:.1f}초")

    # ── 7. 응답 추출 ───────────────────────────────────────
    log("8/8", "응답 추출 (AX Tree)...")
    response = extract_response(target)
    record("T30_extract_response", response is not None)

    if response:
        answer = response.get("markdown_answer", "")
        thinking = response.get("thinking", "")
        actions = response.get("actions", [])
        files = response.get("files_modified", [])

        record("T32_markdown_answer", len(answer) > 0, f"{len(answer)} chars")
        record("T33_actions", len(actions) > 0, f"{len(actions)}개 액션")

        # 액션 상세
        for a in actions:
            atype = a.get("type", "?")
            if atype == "file_edit":
                fname = a.get("file", "?")
                log("  ", f"📄 {fname}")
            elif atype == "command":
                cmd = a.get("cmd", "?")
                exit_code = a.get("exit_code", "?")
                log("  ", f"▶ {cmd[:60]}... (exit: {exit_code})")

    # ── 8. 생성물 검증 ─────────────────────────────────────
    log("결과", "생성된 calc.py 검증...")
    calc_path = os.path.join(WORKSPACE, "calc.py")
    calc_exists = os.path.isfile(calc_path)
    record("T_CALC_FILE_EXISTS", calc_exists, calc_path)

    if calc_exists:
        # Python 문법 검증
        syntax_ok = _check_syntax(calc_path)
        record("T_CALC_SYNTAX_OK", syntax_ok)

        # 기본 사칙연산 검증 (stdin 주입)
        # calc.py 입력 순서: 숫자1 → 연산자 → 숫자2
        test_cases = [
            ("3\n+\n5\n", "8"),       # 3 + 5 = 8
            ("10\n-\n3\n", "7"),      # 10 - 3 = 7
            ("4\n*\n6\n", "24"),      # 4 * 6 = 24
            ("15\n/\n3\n", "5"),      # 15 / 3 = 5
        ]
        all_pass = True
        for stdin_input, expected in test_cases:
            full_input = stdin_input + "q\n"
            output = _run_calc(calc_path, full_input)
            passed = expected in output
            if not passed:
                all_pass = False
                log("  ", f"{FAIL} 입력={stdin_input.strip()} 기대={expected} 실제={output[:100]}")
            else:
                log("  ", f"{PASS} {stdin_input.strip().replace(chr(10), ', ')} → {expected}")

        record("T_CALC_ARITHMETIC", all_pass, "4개 사칙연산")

        # 0 나누기 검증
        # 0 나누기 검증 (숫자1 → 연산자 → 숫자2=0)
        div_zero_input = "5\n/\n0\nq\n"
        div_output = _run_calc(calc_path, div_zero_input)
        div_zero_handled = "error" in div_output.lower() or "0" in div_output.lower()
        record("T_CALC_DIV_ZERO", div_zero_handled)

    # ── 결과 요약 ──────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    elapsed_total = time.monotonic() - start

    print(f"\n{'='*50}")
    print(f"  E2E Calculator Test: {passed}/{total} passed ({elapsed_total:.1f}s)")
    if failed:
        print(f"  {FAIL} 실패 항목:")
        for r in results:
            if not r["passed"]:
                print(f"    - {r['name']}")
    print(f"{'='*50}")

    return failed == 0


def _check_syntax(path):
    """Python 파일의 문법을 검증한다."""
    r = subprocess.run(
        [sys.executable, "-m", "py_compile", path],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def _run_calc(path, stdin_input):
    """calc.py를 실행하고 출력을 반환한다."""
    r = subprocess.run(
        [sys.executable, path],
        input=stdin_input, capture_output=True, text=True,
        timeout=10, cwd=os.path.dirname(path),
    )
    return r.stdout + r.stderr


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
