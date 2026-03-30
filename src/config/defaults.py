"""
config/defaults.py — 기본 설정값

UI 변경 시 여기만 수정하면 된다.
timing 섹션 없음 — 이벤트 기반이므로 시간 설정 불필요.
"""


DEFAULTS = {
    "process": {
        "bundle_id": "com.google.antigravity",
    },
    "ax": {
        "input_box_dom_id": "antigravity.agentSidePanelInputBox",
        "send_button_desc": "Send message",
        "cancel_button_desc": "Cancel",
        "search_placeholder": "Select a conversation",
        "message_input_desc": "Message input",
        "message_input_role": "AXTextArea",
        "model_popup_title_prefix": "Select model",
        "mode_popup_title_prefix": "Select conversation mode",
        "trust_button_title": "Trust Folder & Continue",
        "index_workspace_title": "Index Workspace",
        "typeahead_dom_id": "typeahead-menu",
        "allow_access_button_title": "Allow This Conversation",
    },
    "response": {},
    "session": {
        "dir_name": ".ag-sessions",
        "active_session_file": "active_session",
    },
    "clipboard_queue": {
        "queue_dir": "/tmp/.ag-clipboard-queue",
        "tickets_subdir": "tickets",
        "lock_file": "processing.lock",
    },
}


def get_default(path, fallback=None):
    """
    dot-path로 기본값 조회.
    get_default("ax.send_button_desc") → "Send message"
    """
    keys = path.split(".")
    val = DEFAULTS
    for k in keys:
        if not isinstance(val, dict):
            return fallback
        val = val.get(k)
        if val is None:
            return fallback
    return val
