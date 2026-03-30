"""
ax/panel.py — Agent Panel 조작

에디터 윈도우 내 Agent Panel의 모든 요소를 찾고 조작한다.
헤더 구조: [StaticText(타이틀)] [Link(+새대화)] [Link(⏰이전)] [PopUpButton] [Link] [Group]
"""

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCopyActionNames,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXTitleAttribute,
    kAXDescriptionAttribute,
    kAXValueAttribute,
    kAXFocusedAttribute,
)

from src.config.defaults import get_default
from src.core.events import wait_until


def _get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    if err == 0:
        return val
    return None


def _safe_str(val):
    if val is None:
        return None
    try:
        return str(val)[:500]
    except Exception:
        return None


# ── 헤더 그룹 탐색 ──────────────────────────────────────────

def _find_title_group(window):
    """
    Agent Panel의 타이틀 그룹을 찾는다.
    depth=12에서 AXStaticText + AXLink 형제가 있는 그룹.

    Returns:
        AXUIElement (그룹) or None
    """
    result = [None]

    def search(el, depth=0):
        if depth > 14 or result[0]:
            return
        role = _safe_str(_get_attr(el, kAXRoleAttribute))
        if role == "AXStaticText" and depth == 12:
            parent_children = _get_attr(el, "AXParent")
            if parent_children:
                siblings = _get_attr(parent_children, kAXChildrenAttribute)
                if siblings and any(
                    _safe_str(_get_attr(s, kAXRoleAttribute)) == "AXLink"
                    for s in siblings
                ):
                    result[0] = parent_children
                    return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                search(c, depth + 1)

    search(window)
    return result[0]


def get_panel_title(window):
    """
    Agent Panel의 현재 대화 타이틀을 반환한다.

    Returns:
        str or None
    """
    group = _find_title_group(window)
    if not group:
        return None
    children = _get_attr(group, kAXChildrenAttribute)
    if not children:
        return None
    first = children[0]
    if _safe_str(_get_attr(first, kAXRoleAttribute)) == "AXStaticText":
        return _safe_str(_get_attr(first, kAXValueAttribute))
    return None


def get_header_links(window):
    """
    헤더의 AXLink 요소들을 순서대로 반환한다.
    links[0] = 새 대화 (+)
    links[1] = Past Conversations (⏰)

    Returns:
        list[AXUIElement]
    """
    group = _find_title_group(window)
    if not group:
        return []
    children = _get_attr(group, kAXChildrenAttribute) or []
    return [
        c for c in children
        if _safe_str(_get_attr(c, kAXRoleAttribute)) == "AXLink"
    ]


def click_new_conversation(window):
    """
    새 대화를 생성한다 (links[0] AXPress).
    생성 후 타이틀이 "Agent"가 될 때까지 감시한다.

    Returns:
        bool: 성공 여부
    """
    links = get_header_links(window)
    if len(links) < 1:
        return False
    AXUIElementPerformAction(links[0], "AXPress")
    wait_until(lambda: get_panel_title(window) == "Agent")
    return True


def click_past_conversations(window):
    """
    Past Conversations 오버랩을 연다 (links[1] AXPress).
    검색 필드가 나타날 때까지 감시한다.

    Returns:
        bool: 성공 여부
    """
    links = get_header_links(window)
    if len(links) < 2:
        return False
    AXUIElementPerformAction(links[1], "AXPress")

    placeholder = get_default("ax.search_placeholder")

    def search_field_visible():
        return _find_search_field(window, placeholder) is not None

    wait_until(search_field_visible)
    return True


def _find_search_field(window, placeholder):
    """검색 필드(AXTextField, 특정 placeholder)를 찾는다."""
    result = [None]

    def scan(el, depth=0):
        if depth > 16 or result[0]:
            return
        role = _safe_str(_get_attr(el, kAXRoleAttribute))
        if role == "AXTextField":
            ph = _safe_str(_get_attr(el, "AXPlaceholderValue"))
            if ph and placeholder in ph:
                result[0] = el
                return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


# ── 입력 영역 탐색 ──────────────────────────────────────────

def find_message_input(window):
    """
    Message Input (AXTextArea desc="Message input")을 찾는다.

    Returns:
        AXUIElement or None
    """
    desc_target = get_default("ax.message_input_desc")
    role_target = get_default("ax.message_input_role")
    result = [None]

    def scan(el, depth=0):
        if depth > 20 or result[0]:
            return
        role = _safe_str(_get_attr(el, kAXRoleAttribute))
        desc = _safe_str(_get_attr(el, kAXDescriptionAttribute))
        if role == role_target and desc == desc_target:
            result[0] = el
            return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def wait_for_message_input(window):
    """Message Input이 나타날 때까지 감시한다."""
    result = [None]

    def check():
        mi = find_message_input(window)
        if mi:
            result[0] = mi
            return True
        return False

    wait_until(check)
    return result[0]


def focus_message_input(message_input):
    """Message Input에 포커스를 설정하고, 포커스될 때까지 감시한다."""
    AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
    wait_until(lambda: _get_attr(message_input, kAXFocusedAttribute) == True)


def get_input_value(message_input):
    """Message Input의 현재 값을 반환한다."""
    return _safe_str(_get_attr(message_input, kAXValueAttribute)) or ""


# ── 버튼 탐색 ──────────────────────────────────────────────

def find_send_button(window):
    """Send message 버튼을 찾는다."""
    desc_target = get_default("ax.send_button_desc")
    return _find_button_by_desc(window, desc_target)


def find_cancel_button(window):
    """Cancel 버튼을 찾는다."""
    desc_target = get_default("ax.cancel_button_desc")
    return _find_button_by_desc(window, desc_target)


def _find_button_by_desc(window, desc_target):
    """특정 description의 AXButton을 찾는다."""
    result = [None]

    def scan(el, depth=0):
        if depth > 20 or result[0]:
            return
        role = _safe_str(_get_attr(el, kAXRoleAttribute))
        desc = _safe_str(_get_attr(el, kAXDescriptionAttribute))
        if role == "AXButton" and desc == desc_target:
            result[0] = el
            return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


# ── 상태 감지 ──────────────────────────────────────────────

def get_conversation_state(window):
    """
    현재 대화의 상태를 반환한다.

    Returns:
        "idle" | "generating" | "unknown"
    """
    if find_send_button(window):
        return "idle"
    if find_cancel_button(window):
        return "generating"
    return "unknown"


def wait_for_idle(window):
    """대화가 idle 상태가 될 때까지 감시한다."""
    wait_until(lambda: find_send_button(window) is not None)
