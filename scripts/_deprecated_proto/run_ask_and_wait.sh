#!/bin/bash
cd "$(dirname "$0")/.."

if [ ! -d ".venv_monitor" ]; then
    echo "Virtual environment not found. Please run scripts/run_monitor.sh first."
    exit 1
fi

source .venv_monitor/bin/activate
echo "Running ask_and_wait.py..."
python3 src/ask_and_wait.py "$@"
