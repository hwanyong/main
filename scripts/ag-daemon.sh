#!/bin/bash
# ag-daemon.sh - AG-Agent Input Bridge Daemon 관리 스크립트
# Usage: ./scripts/ag-daemon.sh [start|stop|restart|status]

cd "$(dirname "$0")/.."

DAEMON_SCRIPT="src/ax/daemon.py"
PID_FILE="/tmp/.ag-input-bridge.pid"
VENV=".venv_monitor/bin/python3"

if [ ! -f "$VENV" ]; then
    echo "Error: Virtual environment not found at .venv_monitor."
    exit 1
fi

function check_status() {
    $VENV -c "from src.ax.client import ping_daemon; import sys; sys.exit(0 if ping_daemon() else 1)" 2>/dev/null
    return $?
}

function start() {
    if check_status; then
        echo "Daemon is already running."
    else
        echo "Starting Daemon..."
        PYTHONPATH="." nohup $VENV -m src.ax.daemon > /tmp/.ag-input-bridge.log 2>&1 &
        echo $! > $PID_FILE
        sleep 1
        if check_status; then
            echo "Daemon started successfully."
        else
            echo "Failed to start Daemon. Check /tmp/.ag-input-bridge.log"
            exit 1
        fi
    fi
}

function stop() {
    if check_status; then
        echo "Stopping Daemon..."
        $VENV -c "from src.ax.client import stop_daemon; stop_daemon()" 2>/dev/null
        sleep 1
        if [ -f "$PID_FILE" ]; then
            kill -9 $(cat $PID_FILE 2>/dev/null) 2>/dev/null || true
            rm -f $PID_FILE
        fi
        echo "Daemon stopped."
    else
        echo "Daemon is not running."
        if [ -f "$PID_FILE" ]; then
            rm -f $PID_FILE
        fi
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        start
        ;;
    status)
        if check_status; then
            PID=$(cat $PID_FILE 2>/dev/null || echo "Unknown")
            echo "Daemon is running (PID: $PID)."
        else
            echo "Daemon is stopped."
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
