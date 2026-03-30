"""
ax/conversations.py — Past Conversations 오버랩 조작

검색, 선택, 대화 목록, 오버랩 닫기를 담당한다.
"""

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCopyActionNames,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXValueAttribute,
)

from src.config.defaults import get_default
from src.core.events import wait_until, wait_until_changed
from src.ax.panel import (
    get_panel_title,
    click_past_conversations,
    _find_search_field,
    _get_attr,
    _safe_str,
)
from src.ax.input import ax_write_value, press_escape


# ── 대화 목록 수집 ──────────────────────────────────────────

_EXCLUDE_TEXTS = (
    "integrate_antigravity",
    "AI may make mistakes",
    "Show ",
    "Running in",
    "Recent in",
    "Other Conversation",
)


def _collect_conversation_items(window):
    """
    Past Conversations 오버랩에서 대화 항목을 수집한다.
    depth=13에서 AXPress 가능한 요소 → 대화 항목.

    Returns:
        list[dict]: [{title, el}]
    """
    items = []

    def _get_actions(el):
        err, actions = AXUIElementCopyActionNames(el, None)
        if err == 0 and actions:
            return list(actions)
        return []

    def scan(el, depth=0):
        if depth > 16:
            return
        if depth == 13 and "AXPress" in _get_actions(el):
            texts = _extract_texts(el)
            if texts and not _is_excluded(texts):
                items.append({"title": texts[0], "el": el})
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return items


def _extract_texts(el):
    """요소와 자식에서 텍스트를 추출한다."""
    texts = []
    val = _safe_str(_get_attr(el, kAXValueAttribute))
    if val:
        texts.append(val)
    children = _get_attr(el, kAXChildrenAttribute)
    if children:
        for c in children:
            cv = _safe_str(_get_attr(c, kAXValueAttribute))
            if cv:
                texts.append(cv)
            grandchildren = _get_attr(c, kAXChildrenAttribute)
            if grandchildren:
                for gc in grandchildren:
                    gcv = _safe_str(_get_attr(gc, kAXValueAttribute))
                    if gcv:
                        texts.append(gcv)
    return texts


def _is_excluded(texts):
    """배제 목록에 해당하는지 확인한다."""
    for text in texts:
        for exclude in _EXCLUDE_TEXTS:
            if exclude in text:
                return True
    return False


# ── Public API ──────────────────────────────────────────────

def list_conversations(window):
    """
    Past Conversations 오버랩을 열고, 대화 목록을 반환한다.
    오버랩은 열린 상태로 유지된다.

    Returns:
        list[dict]: [{title, el}]
    """
    click_past_conversations(window)
    return _collect_conversation_items(window)


def search_conversation(window, query):
    """
    Past Conversations에서 검색어로 필터링한다.
    오버랩이 이미 열려있어야 한다.

    Args:
        window: AX 윈도우
        query: 검색어

    Returns:
        list[dict]: 필터링된 [{title, el}]
    """
    placeholder = get_default("ax.search_placeholder")
    field = _find_search_field(window, placeholder)
    if not field:
        return []

    # 필터링 전 항목 수 캡처
    before_count = len(_collect_conversation_items(window))

    # AXValue 직접 쓰기 (클립보드 불필요!)
    ax_write_value(field, query)

    # 항목 수가 변할 때까지 감시
    def items_changed():
        current = len(_collect_conversation_items(window))
        return current != before_count

    wait_until(items_changed)

    return _collect_conversation_items(window)


def select_conversation(window, target_title):
    """
    Past Conversations에서 특정 대화를 찾아 선택한다.
    오버랩 열기 → 검색 → 클릭 → 전환 확인.

    Args:
        window: AX 윈도우
        target_title: 찾을 대화 타이틀

    Returns:
        bool: 성공 여부
    """
    current_title = get_panel_title(window)
    if current_title == target_title:
        return True  # 이미 해당 대화

    # 오버랩 열기
    click_past_conversations(window)

    # 검색
    placeholder = get_default("ax.search_placeholder")
    field = _find_search_field(window, placeholder)
    if field:
        ax_write_value(field, target_title)
        # 필터링 대기
        wait_until(lambda: len(_collect_conversation_items(window)) > 0)

    # 대화 찾기 + 클릭
    items = _collect_conversation_items(window)
    target_item = None
    for item in items:
        if target_title in item["title"]:
            target_item = item
            break

    if not target_item:
        press_escape()
        return False

    AXUIElementPerformAction(target_item["el"], "AXPress")

    # 타이틀 변경 감시
    wait_until(lambda: get_panel_title(window) == target_title)
    return True


def close_overlay():
    """Past Conversations 오버랩을 닫는다."""
    press_escape()
