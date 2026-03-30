"""
core/workflows.py — 워크플로우 탐색기

로컬(워크스페이스) 및 글로벌 환경에서 사용 가능한 워크플로우 목록을 추출한다.
"""

import os
import glob

def get_workflows(workspace=None):
    """
    사용 가능한 워크플로우(.md) 파일들을 수집하여 반환한다.
    
    Returns:
        A dictionary with "global" and "workspace" keys, each containing a list of workflow names (without .md).
    """
    workspace_path = workspace or os.getcwd()
    
    global_dir = os.path.expanduser("~/.gemini/antigravity/global_workflows")
    local_dir = os.path.join(workspace_path, ".agents", "workflows")
    
    workflows = {
        "global": [],
        "workspace": []
    }
    
    if os.path.isdir(global_dir):
        for f in glob.glob(os.path.join(global_dir, "*.md")):
            name = os.path.basename(f)[:-3]
            workflows["global"].append(name)
            
    if os.path.isdir(local_dir):
        for f in glob.glob(os.path.join(local_dir, "*.md")):
            name = os.path.basename(f)[:-3]
            workflows["workspace"].append(name)
            
    # 정렬
    workflows["global"].sort()
    workflows["workspace"].sort()
    
    return workflows
