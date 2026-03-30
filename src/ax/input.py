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





def _input_has_content(message_input):
    """Message Input에 내용이 있는지 확인한다."""
    val = _get_ax_value(message_input)
    if val is None:
        return False
    s = str(val).strip()
    return len(s) > 0




def clear_input(message_input):
    """Message Input의 내용을 지운다. Cmd+A + Delete."""
    AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
    press_cmd_a()
    time.sleep(_HW_KEY_GAP)
    press_delete()
