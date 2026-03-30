"""
session/lock.py — 윈도우 단위 배타적 잠금

같은 윈도우에 두 에이전트가 동시 접근하는 것을 방지한다.
다른 윈도우에서는 동시 실행 가능.
"""

import fcntl
import hashlib
import os


_LOCK_DIR = "/tmp/.ag-window-locks"


class WindowLock:
    """
    윈도우 단위 배타적 잠금.
    같은 워크스페이스(같은 윈도우)로의 동시 접근을 직렬화한다.
    """

    def __init__(self, workspace_path):
        os.makedirs(_LOCK_DIR, exist_ok=True)
        workspace_hash = hashlib.md5(workspace_path.encode()).hexdigest()[:12]
        self._lock_path = os.path.join(_LOCK_DIR, f"{workspace_hash}.lock")
        self._lock_file = None

    def acquire(self):
        """
        잠금을 획득한다. 이미 잠겨있으면 해제될 때까지 대기한다.
        타임아웃 없음 — 대기 큐는 OS 커널이 관리.
        """
        self._lock_file = open(self._lock_path, "w")
        fcntl.flock(self._lock_file, fcntl.LOCK_EX)

    def release(self):
        """잠금을 해제한다."""
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            self._lock_file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
