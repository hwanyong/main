"""
ax/discovery.py — Antigravity 앱/윈도우 탐색

CG Window Server + AX API 이중 체계로 윈도우를 식별한다.

윈도우 식별 전략:
  1. CGWindowListCopyWindowInfo → 실제 윈도우 타이틀(kCGWindowName) 확보
  2. _AXUIElementGetWindow (private API) → AX 윈도우 ↔ CGWindowID 1:1 매핑
  3. CGWindowID로 특정 워크스페이스 윈도우를 정확히 타겟팅

_AXUIElementGetWindow는 Apple 비공개 API이므로, 향후 제거될 수 있다.
- 라이브러리 로드 실패 시: FATAL 크래시 (exit 78)
- 개별 호출 실패 시: FATAL 크래시 (exit 78)
  → 최소화/비활성 윈도우는 호출 전에 필터링하여 방지
"""

import ctypes
import os
import sys

from AppKit import NSWorkspace
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementSetAttributeValue,
    AXUIElementCopyAttributeValue,
    AXUIElementPerformAction,
    kAXWindowsAttribute,
    kAXTitleAttribute,
    kAXMainAttribute,
)
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionAll,
    kCGNullWindowID,
)

from src.config.defaults import get_default
from src.core.events import wait_until


_AX_MANUAL = "AXManualAccessibility"

_FATAL_BANNER = """
╔══════════════════════════════════════════════════╗
║  FATAL: _AXUIElementGetWindow {context}
║                                                  ║
║  이 Apple 비공개 API가 현재 macOS 버전에서        ║
║  제거되었거나 인터페이스가 변경되었습니다.        ║
║                                                  ║
║  이 API 없이는 AX 윈도우 ↔ CG 윈도우 매핑이     ║
║  불가능하므로 윈도우를 식별할 수 없습니다.        ║
╚══════════════════════════════════════════════════╝
"""


# ── Private API 로딩 ────────────────────────────────────────


def _load_ax_get_window():
    """
    _AXUIElementGetWindow private API를 로드한다.
    로드 실패 시 즉시 크래시한다 (exit 78).

    Returns:
        ctypes function
    """
    try:
        ax_lib = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/"
            "ApplicationServices.framework/"
            "ApplicationServices"
        )
        fn = ax_lib._AXUIElementGetWindow
        fn.restype = ctypes.c_int
        fn.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        return fn
    except (OSError, AttributeError) as e:
        print(
            _FATAL_BANNER.format(context="로드 실패"),
            f"\n  Error: {e}",
            f"\n  macOS: {os.uname().release}",
            f"\n  Python: {sys.version.split()[0]}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(78)


_ax_get_window_fn = _load_ax_get_window()


def _ax_element_get_window_id(ax_window):
    """
    AX 윈도우 요소에서 CGWindowID를 추출한다.

    호출 실패 시 FATAL 크래시한다.
    → 호출 전 윈도우가 활성 상태인지 반드시 확인할 것.

    Args:
        ax_window: AXUIElement (윈도우)

    Returns:
        int: CGWindowID
    """
    import objc
    window_id = ctypes.c_uint32(0)
    ptr = objc.pyobjc_id(ax_window)
    result = _ax_get_window_fn(ptr, ctypes.byref(window_id))

    if result != 0:
        print(
            _FATAL_BANNER.format(context="호출 실패"),
            f"\n  AXError code: {result}",
            "\n  이 오류는 다음 원인으로 발생합니다:",
            "\n    1. macOS 업데이트로 private API 인터페이스 변경",
            "\n    2. AX 요소가 유효하지 않은 상태 (윈도우 닫힘/최소화)",
            "\n  윈도우가 활성 상태인지 확인하세요.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(78)

    return window_id.value


# ── CG Window Server 조회 ──────────────────────────────────


def _get_cg_windows_for_pid(pid):
    """
    특정 PID의 모든 실제 윈도우 CG 정보를 반환한다.
    메뉴바, 타이틀바 등 부속 윈도우는 제외한다.

    Returns:
        dict[int, dict]: {CGWindowID: {name, x, y, w, h}}
    """
    result = {}
    all_windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionAll,
        kCGNullWindowID,
    )
    if not all_windows:
        return result

    for w in all_windows:
        if w.get("kCGWindowOwnerPID") != pid:
            continue
        if w.get("kCGWindowLayer", -1) != 0:
            continue
        cg_id = w.get("kCGWindowNumber")
        if cg_id is None:
            continue
        name = w.get("kCGWindowName", "")
        bounds = w.get("kCGWindowBounds", {})
        width = float(bounds.get("Width", 0))
        height = float(bounds.get("Height", 0))
        result[cg_id] = {
            "name": name,
            "x": float(bounds.get("X", 0)),
            "y": float(bounds.get("Y", 0)),
            "w": width,
            "h": height,
        }

    return result


# ── 기본 유틸리티 ───────────────────────────────────────────


def _get_attr(element, attr):
    err, val = AXUIElementCopyAttributeValue(element, attr, None)
    if err == 0:
        return val
    return None


# ── 앱 탐색 ────────────────────────────────────────────────


def find_antigravity():
    """
    실행 중인 Antigravity 앱을 찾는다.

    Returns:
        (NSRunningApplication, int, AXUIElement) or (None, None, None)
    """
    bundle_id = get_default("process.bundle_id")
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.bundleIdentifier() == bundle_id:
            pid = app.processIdentifier()
            ax_app = AXUIElementCreateApplication(pid)
            return app, pid, ax_app
    return None, None, None


def activate_and_wait(app):
    """
    앱을 활성화하고, 실제로 활성화될 때까지 감시한다.
    앱이 백그라운드에 있을 때만 사용.
    특정 윈도우의 포그라운드 전환에는 raise_window를 사용할 것.
    """
    app.activateWithOptions_(0)
    wait_until(lambda: app.isActive())


def raise_window(app, window):
    """
    특정 윈도우를 최상단 포그라운드로 올린다.
    """
    if not app.isActive():
        # 2 = NSApplicationActivateIgnoringOtherApps
        app.activateWithOptions_(2)
        # Timeout 추가하여 무한대기 방지
        wait_until(lambda: app.isActive(), timeout=5)

    AXUIElementPerformAction(window, "AXRaise")
    AXUIElementSetAttributeValue(window, kAXMainAttribute, True)

    def is_main():
        val = _get_attr(window, kAXMainAttribute)
        return val == True
    wait_until(is_main, timeout=5)


def enable_ax(ax_app):
    """AXManualAccessibility를 활성화한다."""
    err = AXUIElementSetAttributeValue(ax_app, _AX_MANUAL, True)
    return err == 0


def wait_for_windows(ax_app):
    """AX 윈도우 목록이 사용 가능해질 때까지 감시한다."""
    result = [None]

    def check():
        wins = _get_attr(ax_app, kAXWindowsAttribute)
        if wins and len(wins) > 0:
            result[0] = wins
            return True
        return False

    wait_until(check)
    return result[0]


# ── 윈도우 식별 (CG + AX 이중 체계) ────────────────────────


def list_windows(ax_app, pid):
    """
    모든 윈도우를 CG 타이틀 + CGWindowID와 함께 반환한다.

    Returns:
        list[dict]: [{cg_id, cg_title, ax_ref}]
    """
    cg_windows = _get_cg_windows_for_pid(pid)
    ax_windows = _get_attr(ax_app, kAXWindowsAttribute) or []
    result = []

    for ax_win in ax_windows:
        cg_id = _ax_element_get_window_id(ax_win)
        cg_info = cg_windows.get(cg_id, {})
        result.append({
            "cg_id": cg_id,
            "cg_title": cg_info.get("name", ""),
            "ax_ref": ax_win,
        })

    return result


def find_window_by_workspace(ax_app, pid, workspace_pattern):
    """
    워크스페이스 패턴이 포함된 윈도우를 찾는다.

    CG 윈도우 서버의 실제 타이틀(kCGWindowName)로 매칭한다.
    Antigravity의 kAXTitleAttribute는 항상 'Antigravity'를 반환하므로
    사용하지 않는다.

    Args:
        ax_app: AXUIElement (앱)
        pid: int
        workspace_pattern: 워크스페이스 경로 또는 폴더명

    Returns:
        AXUIElement or None
    """
    basename = os.path.basename(workspace_pattern.rstrip("/"))
    cg_windows = _get_cg_windows_for_pid(pid)
    ax_windows = _get_attr(ax_app, kAXWindowsAttribute) or []

    for ax_win in ax_windows:
        cg_id = _ax_element_get_window_id(ax_win)
        cg_info = cg_windows.get(cg_id)
        if not cg_info:
            continue
        cg_title = cg_info.get("name", "")
        if workspace_pattern in cg_title or basename in cg_title:
            return ax_win

    return None
