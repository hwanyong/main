#!/bin/bash
# ag-daemon.sh - AG-Agent Input Bridge Daemon 관리 스크립트
# Usage: ./scripts/ag-daemon.sh [install|uninstall|start|stop|restart|status]

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)
VENV=".venv_monitor/bin/python3"
PLIST_NAME="com.antigravity.inputbridge"
PLIST_FILE="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
ALIAS_CMD="alias agbridge=\"$PROJECT_ROOT/scripts/ag-agent.sh\""
ZSHRC="$HOME/.zshrc"

if [ ! -f "$VENV" ]; then
    echo "Error: Virtual environment not found at .venv_monitor."
    exit 1
fi

function check_status() {
    $VENV -c "from src.ax.client import ping_daemon; import sys; sys.exit(0 if ping_daemon() else 1)" 2>/dev/null
    return $?
}

function install_daemon() {
    echo "Installing Daemon as LaunchAgent..."
    # 1. plist 생성
    sed "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" scripts/com.antigravity.inputbridge.plist.template > "$PLIST_FILE"
    chmod 644 "$PLIST_FILE"
    
    # 2. 로드 및 실행
    launchctl unload "$PLIST_FILE" 2>/dev/null
    launchctl load "$PLIST_FILE"
    
    # 3. Alias 등록 (agbridge)
    if ! grep -q "alias agbridge=" "$ZSHRC" 2>/dev/null; then
        echo "" >> "$ZSHRC"
        echo "# Added by Antigravity Bridge Daemon Setup" >> "$ZSHRC"
        echo "$ALIAS_CMD" >> "$ZSHRC"
        echo "✅ Added 'agbridge' alias to $ZSHRC."
    else
        sed -i '' "s|alias agbridge=.*|$ALIAS_CMD|g" "$ZSHRC"
        echo "♻️ Updated 'agbridge' alias in $ZSHRC."
    fi
    
    # 4. Global Skills 설치 (agbridge-parallel-analyzer 등)
    GEMINI_SKILLS_DIR="$HOME/.gemini/antigravity/skills"
    AGENTS_SKILLS_DIR="$HOME/.agents/skills"
    if [ -d "$PROJECT_ROOT/skills" ]; then
        mkdir -p "$GEMINI_SKILLS_DIR"
        cp -R "$PROJECT_ROOT/skills/"* "$GEMINI_SKILLS_DIR/" 2>/dev/null || true
        echo "✅ Installed global skills (e.g., agbridge-parallel-analyzer) to $GEMINI_SKILLS_DIR."

        mkdir -p "$AGENTS_SKILLS_DIR"
        cp -R "$PROJECT_ROOT/skills/"* "$AGENTS_SKILLS_DIR/" 2>/dev/null || true
        echo "✅ Installed global skills (e.g., agbridge-parallel-analyzer) to $AGENTS_SKILLS_DIR."
    fi
    
    echo "======================================================"
    echo "✅ Installation complete."
    echo "⚠️  [중요] 처음 실행 시 macOS [시스템 설정 > 개인정보 보호 및 보안 > 손쉬운 사용(Accessibility)]에"
    echo "   다음 경로의 프로세스를 반드시 추가/허용해야 합니다:"
    echo "   ▶ $PROJECT_ROOT/.venv_monitor/bin/python3"
    echo ""
    echo "   터미널을 재시작하시거나 'source ~/.zshrc'를 입력하시면"
    echo "   어디서든 'agbridge' 전역 명령어를 사용할 수 있습니다."
    echo "======================================================"
}

function uninstall_daemon() {
    echo "Uninstalling Daemon..."
    if [ -f "$PLIST_FILE" ]; then
        launchctl unload "$PLIST_FILE" 2>/dev/null
        rm -f "$PLIST_FILE"
        echo "✅ Removed LaunchAgent configuration."
    fi
    
    # Alias 제거
    if [ -f "$ZSHRC" ]; then
        sed -i '' '/# Added by Antigravity Bridge Daemon Setup/d' "$ZSHRC"
        sed -i '' '/alias agbridge=/d' "$ZSHRC"
        echo "✅ Removed 'agbridge' alias from $ZSHRC."
    fi
    
    # 소켓 및 로그 정리
    rm -f /tmp/.ag-input-bridge.sock /tmp/.ag-input-bridge.log

    # Global Skills 정리
    if [ -d "$HOME/.gemini/antigravity/skills/agbridge-parallel-analyzer" ]; then
        rm -rf "$HOME/.gemini/antigravity/skills/agbridge-parallel-analyzer"
        echo "✅ Removed global skill 'agbridge-parallel-analyzer' from .gemini."
    fi
    if [ -d "$HOME/.gemini/antigravity/skills/agbridge" ]; then
        rm -rf "$HOME/.gemini/antigravity/skills/agbridge"
    fi
    if [ -d "$HOME/.gemini/antigravity/skills/analyzer" ]; then
        rm -rf "$HOME/.gemini/antigravity/skills/analyzer"
    fi
    if [ -d "$HOME/.agents/skills/agbridge-parallel-analyzer" ]; then
        rm -rf "$HOME/.agents/skills/agbridge-parallel-analyzer"
        echo "✅ Removed global skill 'agbridge-parallel-analyzer' from .agents."
    fi
    if [ -d "$HOME/.agents/skills/agbridge" ]; then
        rm -rf "$HOME/.agents/skills/agbridge"
    fi

    echo "Daemon uninstalled."
}

function start() {
    if check_status; then
        echo "Daemon is already running."
    else
        echo "Starting Daemon..."
        if [ -f "$PLIST_FILE" ]; then
            launchctl start $PLIST_NAME
        else
            echo "Error: Daemon is not installed. Run './scripts/ag-daemon.sh install' first."
            exit 1
        fi
        sleep 2
        if check_status; then
            echo "Daemon started successfully."
        else
            echo "Failed to start Daemon. Check /tmp/.ag-input-bridge.log"
            exit 1
        fi
    fi
}

function stop() {
    echo "Stopping Daemon..."
    if [ -f "$PLIST_FILE" ]; then
        launchctl stop $PLIST_NAME 2>/dev/null
    fi
    $VENV -c "from src.ax.client import stop_daemon; stop_daemon()" 2>/dev/null
    sleep 1
    echo "Daemon stopped."
}

function status() {
    if check_status; then
        echo "Daemon is running (Connected via Payload Socket)."
    else
        echo "Daemon is stopped or disconnected."
        if [ -f "$PLIST_FILE" ]; then
            if ! launchctl list | grep -q $PLIST_NAME; then
                echo "LaunchAgent is NOT loaded."
            fi
        fi
    fi
}

case "$1" in
    install)
        install_daemon
        ;;
    uninstall)
        uninstall_daemon
        ;;
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
        status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|start|stop|restart|status}"
        exit 1
        ;;
esac
