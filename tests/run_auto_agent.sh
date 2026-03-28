#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ".venv_monitor" ]; then
    echo "Virtual environment not found. Please run run_monitor.sh first."
    exit 1
fi

source .venv_monitor/bin/activate
echo "Running auto_agent.py..."
python3 auto_agent.py
