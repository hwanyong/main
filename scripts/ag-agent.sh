#!/bin/bash
# AG-Agent CLI 실행 스크립트
cd "$(dirname "$0")/.."

if [ ! -d ".venv_monitor" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv .venv_monitor
    .venv_monitor/bin/pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa pyobjc-framework-Quartz pyyaml
fi

# 데몬 상태 점검 및 자동 시작
./scripts/ag-daemon.sh status | grep -q 'is running' || ./scripts/ag-daemon.sh start

export PYTHONPATH="."
exec .venv_monitor/bin/python3 -m src "$@"
