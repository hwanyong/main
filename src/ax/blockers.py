"""
ax/blockers.py — 차단 다이얼로그 자동 처리

새 워크스페이스를 열 때 나타나는 차단 요소들을 감지하고 자동으로 해제한다.
  - Workspace Trust: "Trust Folder & Continue" 버튼 (depth 9)
  - Index Workspace: "Index Workspace" 버튼 (상태바 알림)
"""

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXTitleAttribute,
)

from src.config.defaults import get_default
from src.core.events import wait_until


def _get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    if err == 0:
        return val
    return None


def _find_button_by_title(window, title_text, max_depth=15):
    """특정 title을 포함하는 AXButton을 찾는다."""
    result = [None]

    def scan(el, depth=0):
        if depth > max_depth or result[0]:
            return
        role = str(_get_attr(el, kAXRoleAttribute) or "")
        if role == "AXButton":
            title = str(_get_attr(el, kAXTitleAttribute) or "")
            if title_text in title:
                result[0] = el
                return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def has_trust_dialog(window):
    """Trust 다이얼로그가 표시 중인지 확인한다."""
    title = get_default("ax.trust_button_title")
    return _find_button_by_title(window, title) is not None


def dismiss_trust_dialog(window):
    """
    Trust 다이얼로그를 자동으로 수락한다.

    Returns:
        bool: 다이얼로그가 있었고 처리했으면 True
    """
    title = get_default("ax.trust_button_title")
    btn = _find_button_by_title(window, title)
    if not btn:
        return False

    AXUIElementPerformAction(btn, "AXPress")

    # 다이얼로그 사라짐 감시
    wait_until(lambda: _find_button_by_title(window, title) is None)
    return True


def dismiss_index_workspace(window):
    """
    Index Workspace 알림을 수락한다.

    Returns:
        bool: 알림이 있었고 처리했으면 True
    """
    title = get_default("ax.index_workspace_title")
    btn = _find_button_by_title(window, title)
    if not btn:
        return False

    AXUIElementPerformAction(btn, "AXPress")
    wait_until(lambda: _find_button_by_title(window, title) is None)
    return True


def dismiss_directory_access(window):
    """
    디렉토리 접근 권한 다이얼로그를 자동 수락한다.
    "Allow This Conversation" 버튼을 클릭한다.

    Returns:
        int: 처리된 다이얼로그 수
    """
    title = get_default("ax.allow_access_button_title")
    count = 0
    while True:
        btn = _find_button_by_title(window, title)
        if not btn:
            break
        AXUIElementPerformAction(btn, "AXPress")
        wait_until(lambda: _find_button_by_title(window, title) is None)
        count += 1
    return count


def dismiss_all_blockers(window):
    """
    윈도우의 모든 차단 요소를 순차적으로 처리한다.

    Returns:
        list[str]: 처리된 차단 요소 이름 목록
    """
    dismissed = []

    if dismiss_trust_dialog(window):
        dismissed.append("trust_dialog")

    if dismiss_index_workspace(window):
        dismissed.append("index_workspace")

    access_count = dismiss_directory_access(window)
    if access_count:
        dismissed.append(f"directory_access({access_count})")

    return dismissed
