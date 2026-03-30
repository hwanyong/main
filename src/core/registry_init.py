"""
core/registry_init.py — 데몬 레지스트리 초기화 스크립트

사용 가능한 모델/모드 정보를 수집하여 레지스트리에 저장한다.
현재 열려있는 Antigravity 윈도우가 없다면 자동으로 열고, 종료하는 로직도 포함한다.
"""

import time
import subprocess
import os

from src.core.registry import ModelRegistry
from src.ax.discovery import find_antigravity, wait_for_windows
from src.ax.settings import list_models, list_modes

def initialize_registry(force=False):
    """
    레지스트리 초기화를 진행한다.
    
    Args:
        force (bool): 강제로 새로고침 할 것인지.
    """
    registry = ModelRegistry()
    
    if not force and not registry.needs_initialization():
        return registry.load()
        
    print("▶ 레지스트리가 비어있거나 초기화가 필요합니다. 스크래핑을 시작합니다...")
    version = registry.get_ag_version()
    
    # 1. Antigravity가 현재 켜져 있는지 확인
    app, pid, ax_app = find_antigravity()
    temp_window_opened = False
    
    if not app:
        print("  - 백그라운드에서 Antigravity 에디터를 임시로 엽니다...")
        # 빈 워크스페이스(-n 옵션은 새 창 열기)로 실행
        subprocess.run(["antigravity", "-n"], check=False)
        time.sleep(3) # 에디터 로드 대기
        
        # 다시 탐색
        app, pid, ax_app = find_antigravity()
        if not app:
            raise RuntimeError("Antigravity 런칭 후 앱을 찾을 수 없습니다.")
            
        temp_window_opened = True

    # 2. 윈도우 탐색
    # 여러 윈도우 중 채팅 패널을 열 수 있는 실제 윈도우를 찾는다
    windows = wait_for_windows(ax_app)
    if not windows:
        if temp_window_opened:
            app.terminate()
        raise RuntimeError("Antigravity 윈도우 목록을 가져올 수 없습니다.")
        
    models = []
    modes = []

    print("  - 채팅 패널을 활성화하고 메타데이터 스크래핑을 시도합니다...")
    for w in windows:
        from src.ax.discovery import raise_window
        from src.ax.panel import click_new_conversation, wait_for_message_input
        
        try:
            raise_window(app, w)
            click_new_conversation(w)
            wait_for_message_input(w)
        except Exception as e:
            continue
            
        try:
            m = list_models(w)
            d = list_modes(w)
            if m and len(m) > 0:
                models = m
                modes = d
                break
        except Exception:
            continue
            
    if not models:
        print("❌ 스크래핑 중 오류 발생: 활성 창에서 모델 데이터를 찾지 못했습니다.")
        data = None
    else:
        # 4. 저장
        data = registry.save(models, modes, version)
        print(f"✅ 모델 {len(models)}개, 모드 {len(modes)}개 스크래핑 및 저장 완료")
        
    # 5. 우리가 임시로 열었던 창이라면 종료
    if temp_window_opened:
        print("  - 임시로 연 Antigravity를 종료합니다...")
        app.terminate()
        
    return data
