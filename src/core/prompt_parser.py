"""
core/prompt_parser.py — 프롬프트 파서

호출 AI가 전달한 프롬프트 문자열에서 지시어(directives)를 추출한다.
순수 함수 — AX, GUI 의존성 없음.

지시어 포맷:
  @[/code]         → workflow = "code"
  @[src/cli.py]    → mentions = ["src/cli.py"]
  [model: Gemini 3 Flash]  → model = "Gemini 3 Flash"
  [mode: fast]     → mode = "fast"
"""

import re


_RE_WORKFLOW = re.compile(r"@\[/(\w+)\]")
_RE_MENTION = re.compile(r"@\[([^\]]+)\]")
_RE_MODEL = re.compile(r"\[model:\s*(.+?)\]", re.IGNORECASE)
_RE_MODE = re.compile(r"\[mode:\s*(\w+)\]", re.IGNORECASE)


class ParsedPrompt:
    """프롬프트 파싱 결과."""

    __slots__ = ("workflow", "mentions", "model", "mode", "clean_text")

    def __init__(self, workflow=None, mentions=None, model=None,
                 mode=None, clean_text=""):
        self.workflow = workflow
        self.mentions = mentions or []
        self.model = model
        self.mode = mode
        self.clean_text = clean_text

    def has_directives(self):
        return bool(
            self.workflow or self.mentions or self.model or self.mode
        )

    def __repr__(self):
        parts = []
        if self.workflow:
            parts.append(f"workflow={self.workflow}")
        if self.mentions:
            parts.append(f"mentions={self.mentions}")
        if self.model:
            parts.append(f"model={self.model}")
        if self.mode:
            parts.append(f"mode={self.mode}")
        parts.append(f"clean_text={self.clean_text!r:.60}")
        return f"ParsedPrompt({', '.join(parts)})"


def parse_prompt(raw):
    """
    프롬프트 문자열을 파싱하여 지시어를 추출한다.

    Args:
        raw: 원본 프롬프트 문자열

    Returns:
        ParsedPrompt
    """
    if not raw:
        return ParsedPrompt()

    text = raw

    # 1. workflow 추출 (@[/xxx] — 첫 번째만)
    workflow = None
    wf_match = _RE_WORKFLOW.search(text)
    if wf_match:
        workflow = wf_match.group(1)
    text = _RE_WORKFLOW.sub("", text)

    # 2. mentions 추출 (@[xxx] — 복수 가능)
    mentions = [m.group(1).strip() for m in _RE_MENTION.finditer(text)]
    text = _RE_MENTION.sub("", text)

    # 3. model 추출
    model = None
    model_match = _RE_MODEL.search(text)
    if model_match:
        model = model_match.group(1).strip()
    text = _RE_MODEL.sub("", text)

    # 4. mode 추출
    mode = None
    mode_match = _RE_MODE.search(text)
    if mode_match:
        mode = mode_match.group(1).strip().lower()
    text = _RE_MODE.sub("", text)

    # 5. clean_text: 남은 텍스트 정리
    clean_text = " ".join(text.split()).strip()

    return ParsedPrompt(
        workflow=workflow,
        mentions=mentions,
        model=model,
        mode=mode,
        clean_text=clean_text,
    )
