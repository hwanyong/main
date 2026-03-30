"""
ax/daemon.py — 입력 전용 브릿지 데몬 (Bridge Daemon)

단일 백그라운드 프로세스로 동작하며, 클라이언트(에이전트)로부터
Unix Domain Socket을 통해 {pid, workspace, text} 페이로드를 받아 순차적으로 키 이벤트를 제어한다.
"""

import socket
import json
import threading
import queue
import os
import time
import sys

from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication
from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    kAXMainAttribute,
    kAXWindowsAttribute
)

from src.ax.discovery import find_window_by_workspace, _get_attr
from src.ax.panel import find_message_input
from src.ax.input import _get_clipboard, _set_clipboard, simulate_keypress, _input_has_content
from src.core.events import wait_until

SOCKET_PATH = "/tmp/.ag-input-bridge.sock"

class InputDaemon:
    def __init__(self):
        self.q = queue.Queue()
        self.running = False
        self.server = None

    def start(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(SOCKET_PATH)
        self.server.listen(10)
        self.running = True
        
        worker = threading.Thread(target=self._process_queue, daemon=True)
        worker.start()
        
        from src.core.registry_init import initialize_registry
        try:
            initialize_registry()
        except Exception as e:
            print(f"Daemon initialization warning: {e}")
            
        print(f"Daemon listening on {SOCKET_PATH}...")
        try:
            while self.running:
                conn, _ = self.server.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            if self.running:
                print(f"Server error: {e}")

    def stop(self):
        self.running = False
        if self.server:
            self.server.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        print("Daemon stopped.")

    def _handle_client(self, conn):
        try:
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
                
            if not data: return
            
            payload = json.loads(data.decode('utf-8'))
            
            if payload.get("action") == "ping":
                conn.sendall(json.dumps({"status": "pong"}).encode('utf-8'))
                conn.close()
                return

            if payload.get("action") == "stop":
                conn.sendall(json.dumps({"status": "stopping"}).encode('utf-8'))
                conn.close()
                self.stop()
                sys.exit(0)

            event = threading.Event()
            result = {}
            
            self.q.put({
                "payload": payload,
                "event": event,
                "result": result
            })
            
            event.wait()
            conn.sendall(json.dumps(result).encode('utf-8'))
        except Exception as e:
            try:
                conn.sendall(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            except:
                pass
        finally:
            conn.close()

    def _process_queue(self):
        while self.running:
            try:
                item = self.q.get(timeout=1.0)
            except queue.Empty:
                continue

            payload = item["payload"]
            result = item["result"]
            
            if payload.get("action") == "paste_and_send":
                try:
                    self._do_paste_and_send(payload)
                    result["status"] = "ok"
                except Exception as e:
                    result["status"] = "error"
                    result["message"] = str(e)
                finally:
                    item["event"].set()
            else:
                result["status"] = "error"
                result["message"] = f"Unknown action: {payload.get('action')}"
                item["event"].set()

    def _do_paste_and_send(self, payload):
        pid = payload.get("pid")
        window_id = payload.get("window_id")
        text = payload.get("text")
        
        if not all([pid, window_id, text]):
            raise ValueError("Missing pid, window_id, or text")
            
        ax_app = AXUIElementCreateApplication(pid)
        target_window = None
        from src.ax.discovery import _ax_element_get_window_id
        ax_windows = _get_attr(ax_app, kAXWindowsAttribute) or []
        for ax_win in ax_windows:
            if _ax_element_get_window_id(ax_win) == window_id:
                target_window = ax_win
                break
                
        if not target_window:
            raise RuntimeError(f"Window not found for window_id {window_id}")
            
        # 1. 대상 윈도우를 최상단으로 강제 활성화 (NSApplicationActivateIgnoringOtherApps 적용)
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app and not app.isActive():
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            wait_until(lambda: app.isActive(), timeout=5)
            
        AXUIElementPerformAction(target_window, "AXRaise")
        AXUIElementSetAttributeValue(target_window, kAXMainAttribute, True)
        
        def is_main():
            val = _get_attr(target_window, kAXMainAttribute)
            return val == True
        wait_until(is_main, timeout=3)
        
        # 2. 메시지 입력창 찾기 및 명시적 포커스 설정
        message_input = find_message_input(target_window)
        if not message_input:
            raise RuntimeError("Message input (AXTextArea) not found in window.")
            
        # 3. 클립보드 백업 및 텍스트 할당
        backup = _get_clipboard()
        _set_clipboard(text)
        
        # 원래 값 측정 (미리 입력된 텍스트가 있을 수 있으므로 길이 기반 검증)
        from ApplicationServices import kAXFocusedAttribute, kAXValueAttribute
        old_val = _get_attr(message_input, kAXValueAttribute) or ""
        # \r \n 차이를 감안하여 여유 길이 설정 (최소 90% 반영)
        expected_min_len = len(old_val) + int(len(text) * 0.9)
        
        # 4. 최대 3번 재시도 하며 (Focus & Cmd+V)
        success = False
        for i in range(3):
            # 확실히 포커스 고정 (팝업 등에 뺏기는 것 방지)
            AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
            time.sleep(0.2)
            
            simulate_keypress(9, cmd=True)  # Cmd + V
            
            def check_pasted():
                cur_val = _get_attr(message_input, kAXValueAttribute) or ""
                return len(cur_val) >= expected_min_len
                
            if wait_until(check_pasted, timeout=3.0, tick=0.1):
                success = True
                break
            
            # 실패한 경우 팝업/모달이 키패치를 뺏었을 확률이 높으므로 ESC로 취소 후 재시도
            if i < 2:
                simulate_keypress(53) # ESC 키 입력 (모달 닫기)
                time.sleep(0.5)
                
        if not success:
            # 복구 전 예외 발생
            if backup:
                _set_clipboard(backup)
            raise RuntimeError("Paste verification failed: Input field did not receive the payload.")
        
        # 5. 클립보드 원상 복구
        if backup:
            _set_clipboard(backup)
        else:
            from AppKit import NSPasteboard
            NSPasteboard.generalPasteboard().clearContents()
            
        # 6. Cmd+Enter 전송 (확실한 검증 후 전송이므로 딜레이 최소화 가능)
        time.sleep(0.1)
        simulate_keypress(36, cmd=True)
        time.sleep(0.1)

if __name__ == "__main__":
    daemon = InputDaemon()
    daemon.start()
