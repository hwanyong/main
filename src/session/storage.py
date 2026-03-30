"""
session/storage.py — 파일시스템 세션 저장소

.ag-sessions/ 디렉토리 구조를 관리한다.
"""

import json
import os
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


class SessionStorage:
    """워크스페이스의 .ag-sessions/ 디렉토리를 관리한다."""

    def __init__(self, workspace_path, dir_name=".ag-sessions"):
        self._workspace = workspace_path
        self._root = os.path.join(workspace_path, dir_name)
        self._sessions_dir = os.path.join(self._root, "sessions")
        self._active_file = os.path.join(self._root, "active_session")

    def ensure_dirs(self):
        """필요한 디렉토리를 생성한다."""
        os.makedirs(self._sessions_dir, exist_ok=True)

    # ── 세션 CRUD ────────────────────────────────────────────

    def create_session(self, session_id, panel_title, **kwargs):
        """
        새 세션을 생성한다.

        Returns:
            dict: metadata
        """
        self.ensure_dirs()
        session_dir = os.path.join(self._sessions_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "responses"), exist_ok=True)

        metadata = {
            "id": session_id,
            "title": kwargs.get("title", panel_title),
            "panel_title": panel_title,
            "workspace": self._workspace,
            "window_title_pattern": kwargs.get("window_title_pattern", ""),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
            "status": "active",
            "total_turns": 0,
            "tags": kwargs.get("tags", []),
            "description": kwargs.get("description", ""),
        }

        meta_path = os.path.join(session_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # history.jsonl 빈 파일 생성
        history_path = os.path.join(session_dir, "history.jsonl")
        if not os.path.exists(history_path):
            open(history_path, "w").close()

        self.set_active(session_id)
        return metadata

    def get_session(self, session_id):
        """세션 메타데이터를 반환한다."""
        meta_path = os.path.join(self._sessions_dir, session_id, "metadata.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_sessions(self):
        """모든 세션 목록을 반환한다."""
        if not os.path.exists(self._sessions_dir):
            return []
        result = []
        for name in sorted(os.listdir(self._sessions_dir)):
            meta = self.get_session(name)
            if meta:
                result.append(meta)
        return result

    def update_session(self, session_id, **updates):
        """세션 메타데이터를 업데이트한다."""
        meta = self.get_session(session_id)
        if not meta:
            return None
        meta.update(updates)
        meta["updated_at"] = _now_iso()
        meta_path = os.path.join(self._sessions_dir, session_id, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return meta

    # ── 이력 기록 ────────────────────────────────────────────

    def record_turn(self, session_id, turn, role, content, **extra):
        """대화 이력에 한 턴을 추가한다."""
        history_path = os.path.join(
            self._sessions_dir, session_id, "history.jsonl"
        )
        entry = {
            "turn": turn,
            "ts": _now_iso(),
            "role": role,
            "content": content,
        }
        entry.update(extra)
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_history(self, session_id):
        """세션 이력을 반환한다."""
        history_path = os.path.join(
            self._sessions_dir, session_id, "history.jsonl"
        )
        if not os.path.exists(history_path):
            return []
        entries = []
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # ── Active Session ───────────────────────────────────────

    def get_active(self):
        """마지막으로 사용한 세션 ID를 반환한다."""
        if not os.path.exists(self._active_file):
            return None
        with open(self._active_file, "r") as f:
            return f.read().strip() or None

    def set_active(self, session_id):
        """현재 세션을 active로 기록한다."""
        self.ensure_dirs()
        with open(self._active_file, "w") as f:
            f.write(session_id)

    # ── 유틸리티 ─────────────────────────────────────────────

    def get_session_dir(self, session_id):
        """세션 디렉토리 경로를 반환한다."""
        return os.path.join(self._sessions_dir, session_id)

    def find_session_by_title(self, panel_title):
        """panel_title로 세션을 찾는다."""
        for session in self.list_sessions():
            if session.get("panel_title") == panel_title:
                return session
        return None

    def find_session_by_partial_id(self, partial_id):
        """부분 ID로 세션을 찾는다."""
        for session in self.list_sessions():
            if partial_id in session.get("id", ""):
                return session
        return None
