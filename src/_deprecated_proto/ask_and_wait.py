#!/usr/bin/env python3
import json
import os
import sys
import time

try:
    from AppKit import NSWorkspace, NSPasteboard, NSPasteboardTypeString
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        kAXWindowsAttribute,
        kAXChildrenAttribute,
        kAXRoleAttribute,
        kAXDescriptionAttribute,
        kAXFocusedAttribute,
        kAXValueAttribute
    )
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGHIDEventTap,
        kCGEventFlagMaskCommand
    )
except ImportError:
    print("Error: Required pyobjc libraries are not installed.")
    print("Please run: pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa")
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"

RESPONSE_FILE = ".agent_response.json"

BUNDLE_IDS = (
    "com.microsoft.VSCode",
    "com.microsoft.VSCodeInsiders",
    "com.google.antigravity",
)


# ── AX Utilities ─────────────────────────────────────────────

def find_app_pid():
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.bundleIdentifier() in BUNDLE_IDS:
            return app.processIdentifier(), app.localizedName()
    return None, None


def get_ax_attribute(element, attribute):
    error, value = AXUIElementCopyAttributeValue(element, attribute, None)
    if error == 0:
        return value
    return None


def enable_manual_accessibility(ax_app):
    error = AXUIElementSetAttributeValue(ax_app, kAXManualAccessibility, True)
    if error != 0:
        print(f"❌ Failed to set AXManualAccessibility (Error code: {error}).")
        return False
    return True


def find_element(element, target_role, target_desc=None, depth=0, max_depth=30):
    if depth > max_depth:
        return None

    role = get_ax_attribute(element, kAXRoleAttribute)
    if role == target_role:
        if target_desc is None:
            return element
        desc = get_ax_attribute(element, kAXDescriptionAttribute)
        if desc == target_desc:
            return element

    children = get_ax_attribute(element, kAXChildrenAttribute)
    if not children:
        return None

    for child in children:
        found = find_element(child, target_role, target_desc, depth + 1, max_depth)
        if found:
            return found
    return None


def extract_all_text(element, depth=0, max_depth=30):
    """Fallback: AX 트리에서 텍스트를 직접 추출. JSON Bridge 실패 시에만 사용."""
    texts = []
    if depth > max_depth:
        return texts

    role = get_ax_attribute(element, kAXRoleAttribute)
    if role in ('AXStaticText', 'AXTextArea'):
        val = get_ax_attribute(element, kAXValueAttribute)
        if val and isinstance(val, str) and val.strip():
            texts.append(val.strip())

    children = get_ax_attribute(element, kAXChildrenAttribute)
    if children:
        for child in children:
            texts.extend(extract_all_text(child, depth + 1, max_depth))

    return texts


# ── Input Simulation ─────────────────────────────────────────

def set_clipboard(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def simulate_keypress(keycode, use_cmd=False):
    event_down = CGEventCreateKeyboardEvent(None, keycode, True)
    event_up = CGEventCreateKeyboardEvent(None, keycode, False)

    if use_cmd:
        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)

    CGEventPost(kCGHIDEventTap, event_down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, event_up)


# ── Response Handling ────────────────────────────────────────

def build_prompt(user_input):
    file_instruction = f"""
[SYSTEM INSTRUCTION: I need your complete response formatted as a strict JSON object.
Because UI rendering breaks markdown and JSON escaping, you MUST NOT output the JSON in this chat window.
Instead, you MUST write the JSON object to a file named `{RESPONSE_FILE}` in the current directory.

If your task involves generating or modifying images, you MUST include the absolute path to those images in your markdown and in a separate "images" array in the JSON.

The JSON schema must be exactly:
{{
  "thought": "your thinking process",
  "markdown_answer": "your main answer, containing FULL rich markdown (headings, bold, lists, code blocks, mermaid diagrams, image links). Preserve all raw markdown characters.",
  "actions": ["list of actions taken"],
  "images": ["/absolute/path/to/generated_image1.png"]
}}
Write the file and simply reply 'Done' in the chat.]
"""
    return user_input + "\n" + file_instruction


def wait_for_generation(target_window):
    """Send 버튼의 출현/소멸을 감지하여 응답 생성 완료를 대기."""
    # Phase 1: 'Send message' 버튼 소멸 대기 (생성 시작 신호)
    for _ in range(20):  # 최대 5초
        time.sleep(0.25)
        if not find_element(target_window, 'AXButton', 'Send message'):
            break
    else:
        print("[!] Warning: 'Send message' button never changed state.")
        return

    print("[*] Generation in progress...")

    # Phase 2: 'Send message' 버튼 재출현 대기 (생성 완료 신호)
    for _ in range(240):  # 최대 120초
        time.sleep(0.5)
        if find_element(target_window, 'AXButton', 'Send message'):
            print("\n[*] Response completed.")
            return
        sys.stdout.write(".")
        sys.stdout.flush()

    print("\n[!] Warning: Timeout waiting for generation to finish.")


def collect_response(target_window):
    """JSON Bridge로 응답 수집. 실패 시 AX 텍스트 추출로 폴백."""
    print("\n" + "=" * 50)
    print("🤖 Agent Response (Extracted via JSON Bridge):")
    print("=" * 50)

    if not os.path.exists(RESPONSE_FILE):
        print(f"⚠️  Error: The agent did not create the `{RESPONSE_FILE}` file.")
        print("UI texts captured as fallback:")
        for line in extract_all_text(target_window)[-10:]:
            print(line)
        print("\n" + "=" * 50)
        return

    try:
        with open(RESPONSE_FILE, 'r', encoding='utf-8') as f:
            parsed = json.load(f)
    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse the JSON file: {e}")
        with open(RESPONSE_FILE, 'r', encoding='utf-8') as f:
            print(f.read())
        print("\n" + "=" * 50)
        return

    print(f"🧠 Thought Process:\n{parsed.get('thought', 'N/A')}\n")

    if parsed.get('actions'):
        print("🛠️ Actions:\n- " + "\n- ".join(parsed['actions']) + "\n")

    print(f"📝 Markdown Answer (Uncorrupted):\n{parsed.get('markdown_answer', 'N/A')}\n")

    if parsed.get('images'):
        print("🖼️ Generated Images:\n- " + "\n- ".join(parsed['images']) + "\n")

    os.remove(RESPONSE_FILE)
    print("\n" + "=" * 50)


# ── Main ─────────────────────────────────────────────────────

def main():
    user_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "파이썬 코드를 분석해"
    text_to_send = build_prompt(user_input)

    # 1. 앱 탐색 및 활성화
    pid, app_name = find_app_pid()
    if not pid:
        print("Antigravity is not running.")
        sys.exit(1)

    print(f"[*] Found {app_name} (PID: {pid}). Activating app...")
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.processIdentifier() == pid:
            app.activateWithOptions_(0)
            time.sleep(0.5)
            break

    # 2. AX 초기화
    ax_app = AXUIElementCreateApplication(pid)
    if not enable_manual_accessibility(ax_app):
        sys.exit(1)
    time.sleep(1.0)

    # 3. 메시지 입력 영역 탐색
    windows = get_ax_attribute(ax_app, kAXWindowsAttribute)
    if not windows:
        print("No windows found.")
        sys.exit(1)

    target_window = None
    message_input = None

    for window in windows:
        message_input = find_element(window, 'AXTextArea', 'Message input')
        if message_input:
            target_window = window
            break

    if not message_input or not target_window:
        print("❌ Could not find the Agent 'Message input' area.")
        sys.exit(1)

    # 4. 텍스트 주입 및 전송
    print(f"[*] Setting focus and pasting: (Length: {len(text_to_send)} chars)")
    AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
    time.sleep(0.5)
    set_clipboard(text_to_send)
    simulate_keypress(9, use_cmd=True)   # Cmd+V
    time.sleep(1.0)

    print("[*] Submitting via Cmd+Enter...")
    simulate_keypress(36, use_cmd=True)  # Cmd+Enter
    time.sleep(1.0)

    print("[*] Message sent! Waiting for response...")

    # 5. 응답 대기 및 수집
    wait_for_generation(target_window)
    time.sleep(0.5)
    collect_response(target_window)


if __name__ == "__main__":
    main()
