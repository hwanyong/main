"""
config/loader.py — YAML 설정 로더

워크스페이스별 config.yaml을 로드하고 기본값과 병합한다.
"""

import copy
import os

from src.config.defaults import DEFAULTS


def _deep_merge(base, override):
    """base 위에 override를 재귀적으로 병합. override가 우선."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(workspace_path):
    """
    워크스페이스의 .ag-sessions/config.yaml을 로드하고 기본값과 병합.

    Args:
        workspace_path: 워크스페이스 루트 경로

    Returns:
        dict: 병합된 설정
    """
    config_path = os.path.join(
        workspace_path,
        DEFAULTS["session"]["dir_name"],
        "config.yaml",
    )

    if not os.path.exists(config_path):
        return copy.deepcopy(DEFAULTS)

    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
    except ImportError:
        # yaml이 없으면 기본값만 사용
        return copy.deepcopy(DEFAULTS)

    return _deep_merge(DEFAULTS, user_config)


def get_config_value(config, path, fallback=None):
    """
    dot-path로 설정값 조회.
    get_config_value(config, "ax.send_button_desc") → "Send message"
    """
    keys = path.split(".")
    val = config
    for k in keys:
        if not isinstance(val, dict):
            return fallback
        val = val.get(k)
        if val is None:
            return fallback
    return val
