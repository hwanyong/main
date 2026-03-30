"""
core/events.py — 이벤트 기반 대기 시스템

모든 대기는 조건이 충족될 때까지 감시한다. 타임아웃 없음.
time.sleep()은 CPU 양보 용도의 tick으로만 사용된다.
"""

import time


# ── 기본 빌딩 블록 ──────────────────────────────────────────

def wait_until(condition_fn, tick=0.05, timeout=30):
    """
    조건이 참이 될 때까지 감시.

    tick은 "대기 시간"이 아니라 "CPU 양보 간격".
    루프 탈출 조건은 condition_fn() == True 또는 timeout 초과.

    Args:
        condition_fn: 호출 시 bool 반환하는 callable
        tick: CPU 양보 간격 (초). 조건 확인 주기.
        timeout: 최대 대기 시간 (초). None이면 무제한.

    Returns:
        bool: 조건 충족이면 True, timeout이면 False
    """
    deadline = time.monotonic() + timeout if timeout else None
    while not condition_fn():
        if deadline and time.monotonic() > deadline:
            return False
        time.sleep(tick)
    return True


def wait_until_changed(get_value_fn, tick=0.05):
    """
    값이 변할 때까지 감시. 초기값을 캡처하고, 달라지면 새 값을 반환.

    Args:
        get_value_fn: 호출 시 현재 값을 반환하는 callable
        tick: CPU 양보 간격

    Returns:
        변경된 새 값
    """
    initial = get_value_fn()
    while True:
        current = get_value_fn()
        if current != initial:
            return current
        time.sleep(tick)


def wait_until_stable(get_value_fn, settle_count=3, tick=0.05):
    """
    값이 안정화될 때까지 감시.
    연속 settle_count번 같은 값이 나오면 안정화로 판단.

    Args:
        get_value_fn: 호출 시 현재 값을 반환하는 callable
        settle_count: 연속 동일 횟수 기준
        tick: CPU 양보 간격

    Returns:
        안정화된 값
    """
    count = 0
    last = None
    while count < settle_count:
        current = get_value_fn()
        if current == last:
            count += 1
        else:
            count = 1
            last = current
        time.sleep(tick)
    return last
