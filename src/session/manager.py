"""
session/manager.py — 세션 매니저

세션 생성, 조회, 연결, 자동 복귀를 담당한다.
"""

import re

from src.session.storage import SessionStorage


class SessionManager:
    """세션 생명주기를 관리한다."""

    def __init__(self, workspace_path):
        self._workspace = workspace_path
        self._storage = SessionStorage(workspace_path)

    @property
    def storage(self):
        return self._storage

    # ── 세션 생성 ────────────────────────────────────────────

    def create(self, panel_title, session_id=None, **kwargs):
        """
        새 세션을 생성한다.
        session_id가 없으면 panel_title에서 자동 생성한다.

        Returns:
            dict: metadata
        """
        if not session_id:
            session_id = self._slug_from_title(panel_title)

        return self._storage.create_session(
            session_id, panel_title, **kwargs
        )

    # ── 세션 조회 ────────────────────────────────────────────

    def find(self, identifier):
        """
        ID(부분 포함) 또는 panel_title로 세션을 찾는다.

        Args:
            identifier: 세션 ID (부분 매칭 가능) 또는 패널 타이틀

        Returns:
            dict or None
        """
        # 정확한 ID 매칭
        exact = self._storage.get_session(identifier)
        if exact:
            return exact

        # 부분 ID 매칭
        partial = self._storage.find_session_by_partial_id(identifier)
        if partial:
            return partial

        # panel_title 매칭
        by_title = self._storage.find_session_by_title(identifier)
        if by_title:
            return by_title

        return None

    def list_all(self):
        """모든 세션 목록을 반환한다."""
        return self._storage.list_sessions()

    # ── 자동 연결 ────────────────────────────────────────────

    def get_active_session(self):
        """마지막으로 사용한 세션을 반환한다."""
        active_id = self._storage.get_active()
        if not active_id:
            return None
        return self._storage.get_session(active_id)

    def connect(self, session_id):
        """세션에 연결(active로 설정)한다."""
        session = self._storage.get_session(session_id)
        if not session:
            session = self.find(session_id)
        if not session:
            return None
        self._storage.set_active(session["id"])
        return session

    # ── 이력 기록 ────────────────────────────────────────────

    def record_user_turn(self, session_id, turn, content, prompt_length=0):
        """사용자 턴을 기록한다."""
        self._storage.record_turn(
            session_id, turn, "user", content,
            prompt_length=prompt_length,
        )

    def record_assistant_turn(self, session_id, turn, summary,
                              response_file=None, duration_sec=0):
        """어시스턴트 턴을 기록한다."""
        self._storage.record_turn(
            session_id, turn, "assistant", summary,
            response_file=response_file,
            duration_sec=duration_sec,
        )

    def increment_turns(self, session_id):
        """세션의 총 턴 수를 1 증가시킨다."""
        session = self._storage.get_session(session_id)
        if session:
            self._storage.update_session(
                session_id,
                total_turns=session.get("total_turns", 0) + 1,
            )

    def get_next_turn(self, session_id):
        """다음 턴 번호를 반환한다."""
        session = self._storage.get_session(session_id)
        if not session:
            return 1
        return session.get("total_turns", 0) + 1

    # ── 유틸리티 ─────────────────────────────────────────────

    def _slug_from_title(self, title):
        """타이틀에서 slug를 생성한다."""
        slug = title.lower().strip()
        slug = re.sub(r"[^a-z0-9가-힣\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = slug[:50]
        return slug
