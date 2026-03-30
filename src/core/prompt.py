"""
core/prompt.py — 프롬프트 빌더

사용자 입력을 정리하여 Agent Panel에 전달할 프롬프트를 생성한다.
JSON Bridge 시스템 인스트럭션은 사용하지 않는다 (에이전트가 무시하므로).
응답은 AX Tree에서 직접 추출한다.
"""


def build_prompt(user_input):
    """
    사용자 입력을 정리하여 프롬프트를 생성한다.

    Args:
        user_input: 원래 사용자 질문

    Returns:
        str: 정리된 프롬프트
    """
    return user_input.strip()
