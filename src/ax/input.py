"""
ax/input.py — 키보드 시뮬레이션 + ClipboardQueue

입력 방식:
  - 검색 필드 (AXTextField): AXValue 직접 쓰기 (클립보드 불필요)
  - 메시지 입력 (AXTextArea): 클립보드 + Cmd+V (Electron 제한)

ClipboardQueue:
  - 티켓 기반 FIFO 큐
  - 여러 에이전트가 동시에 접근해도 순서 보장
"""

import fcntl
import os
import time

from AppKit import NSPasteboard, NSPasteboardTypeString
from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementSetAttributeValue,
    kAXValueAttribute,
    kAXFocusedAttribute,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGHIDEventTap,
    kCGEventFlagMaskCommand,
)

from src.config.defaults import get_default
from src.core.events import wait_until


_HW_KEY_GAP = 0.01  # keydown↔keyup HW 프로토콜 최소 간격


# ── 키보드 시뮬레이션 ────────────────────────────────────────

def simulate_keypress(keycode, cmd=False, shift=False):
    """키 하나를 누르고 뗀다."""
    flags = 0
    if cmd:
        flags |= kCGEventFlagMaskCommand
    if shift:
        flags |= 0x00020000  # kCGEventFlagMaskShift

    event_down = CGEventCreateKeyboardEvent(None, keycode, True)
    event_up = CGEventCreateKeyboardEvent(None, keycode, False)

    if flags:
        CGEventSetFlags(event_down, flags)
        CGEventSetFlags(event_up, flags)

    CGEventPost(kCGHIDEventTap, event_down)
    time.sleep(_HW_KEY_GAP)
    CGEventPost(kCGHIDEventTap, event_up)


def press_escape():
    """Escape 키를 누른다."""
    simulate_keypress(53)


def press_cmd_enter():
    """Cmd+Enter를 누른다."""
    simulate_keypress(36, cmd=True)


def press_cmd_a():
    """Cmd+A (전체 선택)을 누른다."""
    simulate_keypress(0, cmd=True)


def press_delete():
    """Delete 키를 누른다."""
    simulate_keypress(51)


# ── 클립보드 ─────────────────────────────────────────────────

def _get_clipboard():
    pb = NSPasteboard.generalPasteboard()
    return pb.stringForType_(NSPasteboardTypeString)


def _set_clipboard(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


# ── AXValue 직접 쓰기 (검색 필드용) ─────────────────────────

def ax_write_value(element, text):
    """
    AXTextField에 AXValue를 직접 쓴다.
    검색 필드 등 표준 텍스트 필드에서만 동작.
    """
    AXUIElementSetAttributeValue(element, kAXFocusedAttribute, True)
    wait_until(lambda: _get_ax_value(element) is not None or True)
    AXUIElementSetAttributeValue(element, kAXValueAttribute, text)


def _get_ax_value(element):
    err, val = AXUIElementCopyAttributeValue(element, kAXValueAttribute, None)
    if err == 0:
        return val
    return None


# ── GlobalInputLock ──────────────────────────────────────────


_GLOBAL_INPUT_LOCK_PATH = "/tmp/.ag-global-input.lock"


class GlobalInputLock:
    """
    입력 파이프라인 전체를 보호하는 글로벌 잠금.

    raise_window → paste → Cmd+Enter 구간에서 다른 프로세스가
    raise_window를 호출하면 포커스가 뒤집혀 키 이벤트가 잘못된
    윈도우에 전달된다. 이 잠금은 해당 구간 전체를 OS flock으로
    직렬화하여, 입력이 반드시 의도한 윈도우에 도달하도록 보장한다.

    응답 대기/추출 구간은 잠금 밖에서 실행되므로 병렬성이 유지된다.

    장점:
      - 프로세스 크래시 시 OS가 flock을 자동 해제 (데드락 안전)
      - fcntl.LOCK_EX는 커널 대기 큐를 형성 (FIFO 보장)
    """

    def __init__(self):
        self._lock_file = None

    def acquire(self):
        """글로벌 입력 잠금을 획득한다. 다른 프로세스가 잡고 있으면 대기."""
        self._lock_file = open(_GLOBAL_INPUT_LOCK_PATH, "w")
        fcntl.flock(self._lock_file, fcntl.LOCK_EX)

    def release(self):
        """글로벌 입력 잠금을 해제한다."""
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


# ── ClipboardQueue ───────────────────────────────────────────

class ClipboardQueue:
    """
    티켓 기반 FIFO 클립보드 큐.

    여러 에이전트가 동시에 paste를 요청해도
    순서대로 처리되고, 클립보드 오염이 방지된다.
    """

    def __init__(self):
        cfg = get_default("clipboard_queue") or {}
        self._queue_dir = cfg.get("queue_dir", "/tmp/.ag-clipboard-queue")
        self._tickets_dir = os.path.join(
            self._queue_dir, cfg.get("tickets_subdir", "tickets")
        )
        self._lock_path = os.path.join(
            self._queue_dir, cfg.get("lock_file", "processing.lock")
        )
        os.makedirs(self._tickets_dir, exist_ok=True)

    def _take_ticket(self):
        """번호표를 발급한다. 파일명의 정렬 순서가 큐 순서."""
        ticket_number = f"{time.monotonic_ns():020d}"
        ticket_name = f"{ticket_number}_{os.getpid()}"
        ticket_path = os.path.join(self._tickets_dir, ticket_name)
        with open(ticket_path, "w") as f:
            f.write(str(os.getpid()))
        return ticket_name

    def _destroy_ticket(self, ticket_name):
        """번호표를 삭제한다. 다음 에이전트에게 차례를 넘긴다."""
        ticket_path = os.path.join(self._tickets_dir, ticket_name)
        if os.path.exists(ticket_path):
            os.remove(ticket_path)

    def _is_my_turn(self, ticket_name):
        """내 번호표가 큐의 맨 앞인지 확인한다."""
        try:
            tickets = sorted(os.listdir(self._tickets_dir))
        except FileNotFoundError:
            return False
        if not tickets:
            return True  # 큐가 비었으면 내 차례
        return tickets[0] == ticket_name

    def paste(self, text, message_input):
        """
        클립보드 큐에 등록 → 내 차례 대기 → 붙여넣기 → 완료.

        Args:
            text: 붙여넣을 텍스트
            message_input: AXTextArea 요소
        """
        ticket = self._take_ticket()

        # 1. 내 차례 대기 (이벤트 감시)
        wait_until(lambda: self._is_my_turn(ticket))

        try:
            # 2. 실행 잠금 (경쟁 방지)
            with open(self._lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)

                # 3. 클립보드 백업
                backup = _get_clipboard()

                # 4. 텍스트 → 클립보드 → Cmd+V
                _set_clipboard(text)
                simulate_keypress(9, cmd=True)  # Cmd+V

                # 5. 입력 확인 (이벤트 감시)
                wait_until(lambda: _input_has_content(message_input))

                # 6. 클립보드 복원
                if backup:
                    _set_clipboard(backup)
                else:
                    pb = NSPasteboard.generalPasteboard()
                    pb.clearContents()

                # flock 자동 해제 (with 블록 종료)
        finally:
            # 7. 티켓 삭제 → 다음 에이전트 진행
            self._destroy_ticket(ticket)


def _input_has_content(message_input):
    """Message Input에 내용이 있는지 확인한다."""
    val = _get_ax_value(message_input)
    if val is None:
        return False
    s = str(val).strip()
    return len(s) > 0


# ── 단순 paste (ClipboardQueue 없이, Phase1 호환) ─────────

def simple_paste(text, message_input):
    """
    ClipboardQueue 없이 단순 붙여넣기.
    싱글 에이전트 환경에서 사용.
    """
    backup = _get_clipboard()
    _set_clipboard(text)
    simulate_keypress(9, cmd=True)
    wait_until(lambda: _input_has_content(message_input))
    if backup:
        _set_clipboard(backup)
    else:
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()


def clear_input(message_input):
    """Message Input의 내용을 지운다. Cmd+A + Delete."""
    AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
    press_cmd_a()
    time.sleep(_HW_KEY_GAP)
    press_delete()
