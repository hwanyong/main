"""
core/registry.py — 데몬 전용 AI 모델 레지스트리

단발성 스크래핑이 아닌, 영구적인 모델 데이터를 관리하는 기능.
사용자의 로컬 홈 디렉토리에 숨김 폴더(~/.ag-daemon)를 구성하여 데이터를 저장한다.
"""

import os
import json
import subprocess
from datetime import datetime, timezone

REGISTRY_DIR = os.path.expanduser("~/.ag-daemon")
REGISTRY_FILE = os.path.join(REGISTRY_DIR, "registry.json")

class ModelRegistry:
    def __init__(self):
        if not os.path.exists(REGISTRY_DIR):
            os.makedirs(REGISTRY_DIR, exist_ok=True)
            
    def load(self):
        """저장된 레지스트리 데이터를 불러온다."""
        if not os.path.exists(REGISTRY_FILE):
            return None
            
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load registry: {e}")
            return None
            
    def save(self, models, modes, version):
        """스크래핑한 데이터를 레지스트리에 저장한다."""
        data = {
            "antigravity_version": version,
            "last_initialized_at_utc": datetime.now(timezone.utc).isoformat(),
            "models": models,
            "modes": modes
        }
        
        with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return data

    def get_ag_version(self):
        """현재 설치된 antigravity CLI의 버전을 가져온다."""
        try:
            result = subprocess.run(["antigravity", "--version"], capture_output=True, text=True, check=True)
            # 첫 줄이 버전 번호 (e.g., 1.107.0)
            return result.stdout.splitlines()[0].strip()
        except:
            return "unknown"

    def needs_initialization(self):
        """레지스트리 초기화가 필요한지 확인한다 (항목이 비었거나 파일이 없으면 True)."""
        data = self.load()
        if not data:
            return True
            
        if not data.get("models") and not data.get("modes"):
            return True
            
        return False
