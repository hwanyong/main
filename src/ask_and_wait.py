#!/usr/bin/env python3
import time
import sys
try:
    from AppKit import NSWorkspace, NSPasteboard, NSStringPboardType
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        AXUIElementPerformAction,
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
        kCGHIDEventTap,
        kCGEventFlagMaskCommand
    )
except ImportError:
    print("Error: Required pyobjc libraries are not installed.")
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"

def find_app_pid():
    workspace = NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()
    for app in apps:
        if app.bundleIdentifier() in ("com.microsoft.VSCode", "com.microsoft.VSCodeInsiders", "com.google.antigravity"):
            return app.processIdentifier(), app.localizedName()
    return None, None

def get_ax_attribute(element, attribute):
    error, value = AXUIElementCopyAttributeValue(element, attribute, None)
    if error == 0:
        return value
    return None

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
    if children:
        for child in children:
            found = find_element(child, target_role, target_desc, depth + 1, max_depth)
            if found:
                return found
    return None

def extract_all_text(element, depth=0, max_depth=30):
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

def set_clipboard(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSStringPboardType)

def simulate_keypress(keycode, use_cmd=False):
    event_down = CGEventCreateKeyboardEvent(None, keycode, True)
    event_up = CGEventCreateKeyboardEvent(None, keycode, False)
    
    if use_cmd:
        from Quartz import CGEventSetFlags
        CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
        CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
        
    CGEventPost(kCGHIDEventTap, event_down)
    time.sleep(0.05)
    CGEventPost(kCGHIDEventTap, event_up)

import json
import re
import os

def main():
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = "파이썬 코드를 분석해"
        
    response_file = ".agent_response.json"
    
    # Instruct the agent to save the complex JSON directly to a file
    file_instruction = f"""
[SYSTEM INSTRUCTION: I need your complete response formatted as a strict JSON object.
Because UI rendering breaks markdown and JSON escaping, you MUST NOT output the JSON in this chat window.
Instead, you MUST write the JSON object to a file named `{response_file}` in the current directory.

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
    text_to_send = user_input + "\n" + file_instruction
        
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
            
    ax_app = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(ax_app, kAXManualAccessibility, True)
    time.sleep(1.0)
    
    windows = get_ax_attribute(ax_app, kAXWindowsAttribute)
    if not windows:
        print("No windows found.")
        sys.exit(1)
        
    target_window = None
    message_input = None
    send_button = None
    
    for window in windows:
        message_input = find_element(window, 'AXTextArea', 'Message input')
        if message_input:
            target_window = window
            send_button = find_element(window, 'AXButton', 'Send message')
            break
            
    if not message_input or not target_window:
        print("❌ Could not find the Agent 'Message input' area.")
        sys.exit(1)
        
    print("[*] Recording current chat state...")
    initial_texts = extract_all_text(target_window)
    initial_text_count = len(initial_texts)
    
    print(f"[*] Setting focus and pasting: (Length: {len(text_to_send)} chars)")
    AXUIElementSetAttributeValue(message_input, kAXFocusedAttribute, True)
    time.sleep(0.5)
    set_clipboard(text_to_send)
    simulate_keypress(9, use_cmd=True) # Cmd+V
    time.sleep(1.0) # Wait for paste to complete
    
    print("[*] Submitting via Cmd+Enter...")
    simulate_keypress(36, use_cmd=True) # Cmd+Enter
    time.sleep(1.0)
        
    print("[*] Message sent! Waiting for response to start...")
    
    # Wait for the 'Send message' button to disappear (indicates generation started)
    disappeared = False
    for _ in range(20): # 20 * 0.25 = 5 seconds timeout for UI to update
        time.sleep(0.25)
        btn = find_element(target_window, 'AXButton', 'Send message')
        if not btn:
            disappeared = True
            break
            
    if not disappeared:
        print("[!] Warning: 'Send message' button never changed state. It might be a very fast response or an error.")
    else:
        print("[*] Generation in progress... (Waiting for 'Send message' button to reappear)")
        # Wait for the 'Send message' button to reappear (indicates generation finished)
        appeared = False
        for _ in range(240): # 240 * 0.5 = 120 seconds max wait
            time.sleep(0.5)
            btn = find_element(target_window, 'AXButton', 'Send message')
            if btn:
                appeared = True
                break
            sys.stdout.write(".")
            sys.stdout.flush()
            
        if not appeared:
            print("\n[!] Warning: Timeout waiting for generation to finish.")
        else:
            print("\n[*] Response completed.")
            
    # Give UI a tiny moment to render the final text
    time.sleep(0.5)
                
    print("\n" + "="*50)
    print("🤖 Agent Response (Extracted via JSON Bridge):")
    print("="*50)
    
    response_file = ".agent_response.json"
    
    if os.path.exists(response_file):
        try:
            with open(response_file, 'r', encoding='utf-8') as f:
                parsed = json.load(f)
                
            print(f"🧠 Thought Process:\n{parsed.get('thought', 'N/A')}\n")
            
            if parsed.get('actions'):
                print(f"🛠️ Actions:\n- " + "\n- ".join(parsed['actions']) + "\n")
                
            print(f"📝 Markdown Answer (Uncorrupted):\n{parsed.get('markdown_answer', 'N/A')}\n")
            
            if parsed.get('images'):
                print(f"🖼️ Generated Images:\n- " + "\n- ".join(parsed['images']) + "\n")
            
            # Clean up the file
            os.remove(response_file)
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse the JSON file: {e}")
            with open(response_file, 'r', encoding='utf-8') as f:
                print(f.read())
    else:
        print(f"⚠️  Error: The agent did not create the `{response_file}` file.")
        print("UI texts captured just in case:")
        current_texts = extract_all_text(target_window)
        for line in current_texts[-10:]:
            print(line)
            
    print("\n" + "="*50)

if __name__ == "__main__":
    main()
