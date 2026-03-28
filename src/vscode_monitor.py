#!/usr/bin/env python3
import time
import sys
import json
try:
    from AppKit import NSWorkspace
    from ApplicationServices import (
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXUIElementCopyAttributeValue,
        kAXWindowsAttribute,
        kAXChildrenAttribute,
        kAXRoleAttribute,
        kAXValueAttribute,
        kAXTitleAttribute,
        kAXDescriptionAttribute,
        kAXIdentifierAttribute,
        AXError
    )
except ImportError:
    print("Error: Required pyobjc libraries are not installed.")
    print("Please run: pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa")
    sys.exit(1)

kAXManualAccessibility = "AXManualAccessibility"

def find_vscode_pid():
    workspace = NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()
    for app in apps:
        if app.bundleIdentifier() in ("com.microsoft.VSCode", "com.microsoft.VSCodeInsiders", "com.google.antigravity"):
            return app.processIdentifier(), app.localizedName()
    return None, None

def enable_manual_accessibility(ax_app):
    error = AXUIElementSetAttributeValue(ax_app, kAXManualAccessibility, True)
    if error != 0:
        print(f"Warning: Failed to set AXManualAccessibility (Error code: {error}).")
        return False
    return True

def get_ax_attribute(element, attribute):
    error, value = AXUIElementCopyAttributeValue(element, attribute, None)
    if error == 0:
        return value
    return None

def dump_tree(element, file, depth=0, max_depth=30):
    if depth > max_depth:
        return
        
    indent = "  " * depth
    
    role = get_ax_attribute(element, kAXRoleAttribute)
    title = get_ax_attribute(element, kAXTitleAttribute)
    desc = get_ax_attribute(element, kAXDescriptionAttribute)
    identifier = get_ax_attribute(element, kAXIdentifierAttribute)
    value = get_ax_attribute(element, kAXValueAttribute)
    
    # Format the element's information
    info = []
    if role: info.append(f"Role: {role}")
    if identifier: info.append(f"Identifier: '{identifier}'")
    if title: info.append(f"Title: '{title}'")
    if desc: info.append(f"Desc: '{desc}'")
    
    line = f"{indent}- [{' | '.join(info)}]"
    
    if value:
        # If value is too long or contains newlines, format it nicely
        val_str = str(value)
        if len(val_str) > 100 or '\n' in val_str:
            line += "\n" + indent + "  Value:\n"
            for v_line in val_str.split('\n'):
                line += indent + f"    {v_line}\n"
            line = line.rstrip()
        else:
            line += f" Value: '{val_str}'"
            
    file.write(line + "\n")
    
    children = get_ax_attribute(element, kAXChildrenAttribute)
    if children:
        for child in children:
            dump_tree(child, file, depth + 1, max_depth)

def main():
    print("Searching for VS Code / Antigravity process...")
    pid, app_name = find_vscode_pid()
    
    if not pid:
        print("Application is not running. Please start it first.")
        sys.exit(1)
        
    print(f"Found {app_name} (PID: {pid}).")
    
    ax_app = AXUIElementCreateApplication(pid)
    
    print("Enabling AXManualAccessibility...")
    success = enable_manual_accessibility(ax_app)
    
    if not success:
        sys.exit(1)
        
    print("Accessibility enabled. Sleeping briefly (1.5s) to let the accessibility tree populate...")
    time.sleep(1.5)
    
    output_file = "accessibility_tree_dump.txt"
    print(f"Extracting raw accessibility data and saving to {output_file}...")
    
    windows = get_ax_attribute(ax_app, kAXWindowsAttribute)
    if not windows:
        print("No windows found. Is the application minimized or hidden?")
        sys.exit(1)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Accessibility Tree Dump for {app_name} (PID {pid})\n")
        f.write("=" * 80 + "\n\n")
        
        for window in windows:
            title = get_ax_attribute(window, kAXTitleAttribute)
            f.write(f"--- Window: '{title}' ---\n")
            dump_tree(window, f)
            f.write("\n")
            
    print(f"✅ Dump complete! You can view the raw data in '{output_file}'.")

if __name__ == "__main__":
    main()
