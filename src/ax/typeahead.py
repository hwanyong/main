"""
ax/typeahead.py — Typeahead 자동완성 조작

워크플로우(`/`) 선택과 @mention 삽입을 키보드로 제어한다.

핵심: Typeahead 항목은 AX children으로 노출되지 않는다 (Electron 가상 리스트).
따라서 "이름 타이핑으로 필터링 → Tab으로 확정" 전략 사용.

Tab 실패 시 Enter로 재시도 (사용자 결정).
워크플로우 로딩 버그 시 @[/xxx] 텍스트를 프롬프트에 그대로 주입 (사용자 결정).
"""

import time

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    kAXValueAttribute,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventKeyboardSetUnicodeString,
    kCGHIDEventTap,
)

from src.config.defaults import get_default
from src.core.events import wait_until
from src.ax.input import simulate_keypress, press_escape


def _get_ax_value(el):
    err, val = AXUIElementCopyAttributeValue(el, kAXValueAttribute, None)
    if err == 0 and val is not None:
        return str(val)
    return ""


# ── 유니코드 문자 주입 ───────────────────────────────────────
# CGEventKeyboardSetUnicodeString 사용 — 입력 소스(한/영)와 무관.
# 키코드 기반은 IME가 개입하여 한글로 변환되는 문제가 있다.

# 컨트롤 키만 키코드 사용 (IME 비개입)
_KC_TAB = 48
_KC_ENTER = 36
_KC_DOWN = 125

_HW_CHAR_GAP = 0.02  # 문자간 간격


def _type_unicode_char(ch):
    """유니코드 문자를 직접 주입한다. 입력 소스(한/영)와 무관."""
    event_down = CGEventCreateKeyboardEvent(None, 0, True)
    CGEventKeyboardSetUnicodeString(event_down, len(ch), ch)
    CGEventPost(kCGHIDEventTap, event_down)
    time.sleep(0.01)
    event_up = CGEventCreateKeyboardEvent(None, 0, False)
    CGEventPost(kCGHIDEventTap, event_up)


def _type_text(text):
    """문자열을 유니코드 주입으로 한 글자씩 타이핑한다."""
    for ch in text:
        _type_unicode_char(ch)
        time.sleep(_HW_CHAR_GAP)


# ── Typeahead 감지 ───────────────────────────────────────────

def _find_typeahead(window):
    """typeahead-menu DOM ID를 가진 AXList를 찾는다."""
    from ApplicationServices import kAXChildrenAttribute, kAXRoleAttribute
    dom_id = get_default("ax.typeahead_dom_id")

    result = [None]

    def scan(el, depth=0):
        if depth > 12 or result[0]:
            return
        err, eid = AXUIElementCopyAttributeValue(el, "AXDOMIdentifier", None)
        if err == 0 and eid and str(eid) == dom_id:
            result[0] = el
            return
        err2, ch = AXUIElementCopyAttributeValue(
            el, kAXChildrenAttribute, None
        )
        if err2 == 0 and ch:
            for c in ch:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def _is_typeahead_visible(window):
    """Typeahead 팝업이 열려 있는지 확인."""
    return _find_typeahead(window) is not None


# ── Workflow 선택 ────────────────────────────────────────────

def select_workflow(window, message_input, name):
    """
    워크플로우를 선택한다.

    1. "/" 타이핑
    2. Typeahead 나타남 대기
    3. 워크플로우 이름 타이핑 (필터링)
    4. Tab으로 확정 (실패 시 Enter 재시도)
    5. 입력값 변경 확인

    워크플로우 로딩 버그 시 → None 반환 (호출자가 fallback 처리).

    Args:
        window: AX 윈도우
        message_input: AXTextArea 요소
        name: 워크플로우 이름 (예: "code", "analyzer")

    Returns:
        str or None: 성공 시 삽입된 텍스트, 실패 시 None
    """
    before = _get_ax_value(message_input)

    # 1. "/" 타이핑 (유니코드 주입 — IME 무관)
    _type_unicode_char("/")

    # 2. Typeahead 대기 — 나타나지 않을 수 있음 (버그)
    appeared = _wait_typeahead(window)
    if not appeared:
        # Typeahead가 안 나오면 실패 — 호출자가 fallback
        _cleanup_input(message_input, before)
        return None

    # 3. 이름 타이핑
    _type_text(name)
    time.sleep(0.3)  # 필터링 안정화

    # 4. Tab → 확정
    result = _confirm_selection(message_input, before)
    return result


def insert_mention(window, message_input, path):
    """
    @mention을 삽입한다.

    1. "@" 타이핑
    2. Typeahead 나타남 대기
    3. 경로 타이핑 (필터링)
    4. Tab으로 확정 (실패 시 Enter 재시도)

    Args:
        window: AX 윈도우
        message_input: AXTextArea 요소
        path: 파일/디렉토리 경로

    Returns:
        str or None: 성공 시 삽입된 텍스트, 실패 시 None
    """
    before = _get_ax_value(message_input)

    # 1. "@" 타이핑 (유니코드 주입 — IME 무관)
    _type_unicode_char("@")

    # 2. Typeahead 대기
    appeared = _wait_typeahead(window)
    if not appeared:
        _cleanup_input(message_input, before)
        return None

    # 3. 경로의 마지막 부분만 타이핑 (필터 효율)
    filter_text = _extract_filter_text(path)
    _type_text(filter_text)
    time.sleep(0.3)

    # 4. Tab → 확정
    result = _confirm_selection(message_input, before)
    return result


def insert_mentions(window, message_input, paths):
    """
    복수 @mention을 순차적으로 삽입한다.

    Args:
        paths: 파일/디렉토리 경로 목록

    Returns:
        list[str or None]: 각 mention의 삽입 결과
    """
    results = []
    for path in paths:
        r = insert_mention(window, message_input, path)
        results.append(r)
        time.sleep(0.1)  # mention간 간격
    return results


# ── 내부 헬퍼 ────────────────────────────────────────────────

def _wait_typeahead(window, max_polls=30):
    """
    Typeahead가 나타날 때까지 대기.
    이벤트 기반이지만, Typeahead가 아예 안 나올 수 있으므로 상한 있음.
    """
    for _ in range(max_polls):
        if _is_typeahead_visible(window):
            return True
        time.sleep(0.05)
    return False


def _confirm_selection(message_input, before_value):
    """
    Tab으로 확정. 실패 시 Enter로 재시도.

    Returns:
        str or None: 값이 변했으면 새 값, 아니면 None
    """
    # Tab 시도
    simulate_keypress(_KC_TAB)
    time.sleep(0.2)

    after = _get_ax_value(message_input)
    if after != before_value:
        return after

    # Enter 재시도 (사용자 결정: Option A)
    simulate_keypress(_KC_ENTER)
    time.sleep(0.2)

    after2 = _get_ax_value(message_input)
    if after2 != before_value:
        return after2

    # 여전히 실패
    return None


def _cleanup_input(message_input, restore_value):
    """입력 필드를 ESC로 정리하고 원래 값 복원을 시도."""
    press_escape()
    time.sleep(0.05)
    # Cmd+A + Delete로 지우기
    from src.ax.input import clear_input
    if _get_ax_value(message_input) != restore_value:
        clear_input(message_input)


def _extract_filter_text(path):
    """
    경로에서 필터링에 사용할 텍스트를 추출한다.
    전체 경로 대신 파일명/마지막 세그먼트만 사용하면 필터 효율이 높다.
    """
    parts = path.rstrip("/").split("/")
    # 파일명 또는 마지막 디렉토리
    return parts[-1] if parts else path
