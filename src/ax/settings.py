"""
ax/settings.py — 모델/모드 설정 변경

AXPopUpButton 기반의 모델 선택기, 모드 선택기를 제어한다.

사전 검증 결과:
  - 모델: AXPopUpButton(depth 16) → AXButton(depth 9) [AXPress]
  - 모드: AXPopUpButton(depth 16) → AXMenuItem(depth 10) [AXPress]
  - title 포맷: "Select model, current: Claude Opus 4.6 (Thinking)"
"""

import re

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


# ── PopUpButton 탐색 ─────────────────────────────────────────

def _find_popup_button(window, title_prefix):
    """
    특정 title prefix를 가진 AXPopUpButton을 찾는다.
    depth 16 고정 (Agent Panel 내부).
    """
    result = [None]

    def scan(el, depth=0):
        if depth > 18 or result[0]:
            return
        role = str(_get_attr(el, kAXRoleAttribute) or "")
        if role == "AXPopUpButton" and depth == 16:
            title = str(_get_attr(el, kAXTitleAttribute) or "")
            if title_prefix in title:
                result[0] = el
                return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def _parse_current_value(popup_title, prefix):
    """
    "Select model, current: Claude Opus 4.6 (Thinking)" → "Claude Opus 4.6 (Thinking)"
    """
    match = re.search(r"current:\s*(.+)$", popup_title)
    if match:
        return match.group(1).strip()
    return None


# ── 항목 수집 공통 ───────────────────────────────────────────

def _collect_popup_items(window, prefix, role_filter, depth_range):
    """
    AXPopUpButton을 열어 나타나는 하위 항목(AXButton 또는 AXMenuItem)의
    AXTitle 목록을 수집한 뒤, 팝업을 닫고 결과를 반환한다.

    Args:
        window: AX 윈도우
        prefix: 팝업 버튼의 title prefix ("Select model" 등)
        role_filter: 수집할 항목의 AXRole ("AXButton" 또는 "AXMenuItem")
        depth_range: (min_depth, max_depth) 튜플

    Returns:
        list[str]: 항목 제목 목록
    """
    popup = _find_popup_button(window, prefix)
    if not popup:
        return []

    AXUIElementPerformAction(popup, "AXPress")

    import time
    time.sleep(0.5)

    items = []
    min_d, max_d = depth_range

    def scan(el, depth=0):
        if depth > max_d + 2:
            return
        role = str(_get_attr(el, kAXRoleAttribute) or "")
        if role == role_filter and min_d <= depth <= max_d:
            title = str(_get_attr(el, kAXTitleAttribute) or "")
            if title:
                items.append(title)
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)

    from src.ax.input import press_escape
    press_escape()

    return items


# ── 모델 ─────────────────────────────────────────────────────

def list_models(window):
    """사용 가능한 AI 모델 목록을 반환한다."""
    prefix = get_default("ax.model_popup_title_prefix")
    return _collect_popup_items(window, prefix, "AXButton", (7, 11))


def get_current_model(window):
    """현재 선택된 모델 이름을 반환한다."""
    prefix = get_default("ax.model_popup_title_prefix")
    popup = _find_popup_button(window, prefix)
    if not popup:
        return None
    title = str(_get_attr(popup, kAXTitleAttribute) or "")
    return _parse_current_value(title, prefix)


def select_model(window, model_name):
    """
    모델을 변경한다.

    Args:
        window: AX 윈도우
        model_name: 목표 모델명 (부분 매칭 가능, 예: "Gemini 3 Flash")

    Returns:
        bool: 성공 여부
    """
    prefix = get_default("ax.model_popup_title_prefix")
    popup = _find_popup_button(window, prefix)
    if not popup:
        return False

    # 이미 원하는 모델이면 건너뛰기
    current = get_current_model(window)
    if current and model_name.lower() in current.lower():
        return True

    # 메뉴 열기
    AXUIElementPerformAction(popup, "AXPress")

    # 메뉴 항목 대기 (AXButton이 나타날 때까지)
    target_btn = [None]

    def find_model_button():
        result = [None]

        def scan(el, depth=0):
            if depth > 12 or result[0]:
                return
            role = str(_get_attr(el, kAXRoleAttribute) or "")
            if role == "AXButton" and 7 <= depth <= 11:
                title = str(_get_attr(el, kAXTitleAttribute) or "")
                if model_name.lower() in title.lower():
                    result[0] = el
                    return
            children = _get_attr(el, kAXChildrenAttribute)
            if children:
                for c in children:
                    scan(c, depth + 1)

        scan(window)
        target_btn[0] = result[0]
        return result[0] is not None

    wait_until(find_model_button)

    if not target_btn[0]:
        # ESC로 메뉴 닫기
        from src.ax.input import press_escape
        press_escape()
        return False

    # 선택
    AXUIElementPerformAction(target_btn[0], "AXPress")

    # title 변경 확인
    wait_until(lambda: _popup_title_contains(window, prefix, model_name))
    return True


def _popup_title_contains(window, prefix, target_name):
    """PopUpButton title에 target_name이 포함되는지 확인."""
    popup = _find_popup_button(window, prefix)
    if not popup:
        return False
    title = str(_get_attr(popup, kAXTitleAttribute) or "")
    return target_name.lower() in title.lower()


# ── 모드 ─────────────────────────────────────────────────────

def list_modes(window):
    """사용 가능한 대화 모드 목록을 반환한다."""
    prefix = get_default("ax.mode_popup_title_prefix")
    return _collect_popup_items(window, prefix, "AXMenuItem", (8, 12))


def get_current_mode(window):
    """현재 선택된 모드 이름을 반환한다."""
    prefix = get_default("ax.mode_popup_title_prefix")
    popup = _find_popup_button(window, prefix)
    if not popup:
        return None
    title = str(_get_attr(popup, kAXTitleAttribute) or "")
    return _parse_current_value(title, prefix)


def select_mode(window, mode_name):
    """
    모드를 변경한다.

    Args:
        window: AX 윈도우
        mode_name: "planning" 또는 "fast"

    Returns:
        bool: 성공 여부
    """
    prefix = get_default("ax.mode_popup_title_prefix")
    popup = _find_popup_button(window, prefix)
    if not popup:
        return False

    current = get_current_mode(window)
    if current and mode_name.lower() in current.lower():
        return True

    AXUIElementPerformAction(popup, "AXPress")

    target_item = [None]

    def find_mode_item():
        result = [None]

        def scan(el, depth=0):
            if depth > 14 or result[0]:
                return
            role = str(_get_attr(el, kAXRoleAttribute) or "")
            if role == "AXMenuItem" and 8 <= depth <= 12:
                title = str(_get_attr(el, kAXTitleAttribute) or "")
                if mode_name.lower() in title.lower():
                    result[0] = el
                    return
            children = _get_attr(el, kAXChildrenAttribute)
            if children:
                for c in children:
                    scan(c, depth + 1)

        scan(window)
        target_item[0] = result[0]
        return result[0] is not None

    wait_until(find_mode_item)

    if not target_item[0]:
        from src.ax.input import press_escape
        press_escape()
        return False

    AXUIElementPerformAction(target_item[0], "AXPress")

    wait_until(lambda: _popup_title_contains(window, prefix, mode_name))
    return True
