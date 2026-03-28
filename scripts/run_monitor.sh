#!/bin/bash
cd "$(dirname "$0")/.."

if [ ! -d ".venv_monitor" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv_monitor
    source .venv_monitor/bin/activate
    echo "Installing pyobjc..."
    pip install --upgrade pip
    pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa
else
    source .venv_monitor/bin/activate
fi

echo "Running vscode_monitor.py..."
python3 src/vscode_monitor.py
