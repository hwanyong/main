"""
ax/client.py — 데몬 IPC 클라이언트
"""

import socket
import json
import time

SOCKET_PATH = "/tmp/.ag-input-bridge.sock"

def push_prompt(pid, window_id, text):
    """
    데몬에 연결하여 포커싱 및 텍스트 붙여넣기/전송을 요청한다.
    요청 완료(확인) 때까지 블록된다.
    """
    payload = {
        "action": "paste_and_send",
        "pid": pid,
        "window_id": window_id,
        "text": text
    }
    
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(SOCKET_PATH)
        s.sendall(json.dumps(payload).encode('utf-8'))
        s.shutdown(socket.SHUT_WR)
        
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            
        result = json.loads(data.decode('utf-8'))
        
        if result.get("status") != "ok":
            raise RuntimeError(f"Daemon input failed: {result.get('message')}")

def ping_daemon():
    """데몬이 구동 중인지 확인한다."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
            s.sendall(json.dumps({"action": "ping"}).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)
            data = s.recv(1024).decode('utf-8')
            return json.loads(data).get("status") == "pong"
    except (FileNotFoundError, ConnectionRefusedError):
        return False

def stop_daemon():
    """데몬을 안전하게 종료한다."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCKET_PATH)
            s.sendall(json.dumps({"action": "stop"}).encode('utf-8'))
            s.shutdown(socket.SHUT_WR)
    except:
        pass
