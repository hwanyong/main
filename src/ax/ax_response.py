"""
ax/ax_response.py — AX Tree 기반 응답 추출

Agent Panel의 대화 영역에서 AXDOMClassList/AXSubrole 패턴을 분석하여
에이전트 응답을 구조화된 마크다운으로 복원한다.

JSON Bridge(에이전트에게 파일로 쓰라고 지시)를 대체한다.
에이전트 협조 없이, 렌더링된 UI에서 직접 응답을 읽는 방식.
"""

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    kAXChildrenAttribute,
    kAXRoleAttribute,
    kAXDescriptionAttribute,
    kAXValueAttribute,
)


def _get_attr(el, attr):
    err, val = AXUIElementCopyAttributeValue(el, attr, None)
    if err == 0:
        return val
    return None


# ── 응답 영역 탐지 ──────────────────────────────────────────


def _find_conversation_container(window):
    """
    대화 스레드 컨테이너를 찾는다.

    Antigravity Agent Panel 구조:
      ... → AXGroup cls=[gap-y-3, px-4]  ← 이것
              ├── [0] 사용자 메시지 (sticky)
              ├── [1] 에이전트 응답 루트 (relative)
              ├── [2~N] 응답 본문, 테이블, 액션 등
              └── Files Modified + Accept/Reject

    Returns:
        AXUIElementRef or None
    """
    result = [None]

    def scan(el, depth=0):
        if depth > 18 or result[0]:
            return
        classes = _get_class_list(el)
        if "gap-y-3" in classes and "px-4" in classes:
            result[0] = el
            return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def _find_last_response_group(window):
    """
    Agent Panel 내 마지막 에이전트 응답 영역을 찾는다.

    대화 스레드 컨테이너(gap-y-3,px-4)를 찾고
    그 자체를 반환한다. 파싱 단계에서 사용자 메시지를 건너뛴다.

    Returns:
        AXUIElementRef or None: 대화 스레드 컨테이너
    """
    return _find_conversation_container(window)


def _find_response_markers(window):
    """
    에이전트 응답의 고유 마커("Worked for" / "Thought for")를 찾는다.
    이 텍스트는 에이전트 응답에만 존재한다.
    """
    markers = []

    def scan(el, depth=0):
        if depth > 25:
            return
        role = str(_get_attr(el, kAXRoleAttribute) or "")
        if role == "AXStaticText":
            val = str(_get_attr(el, kAXValueAttribute) or "")
            if val.startswith("Worked for") or val.startswith("Thought for"):
                markers.append(el)
                return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return markers


def _find_response_root_from_marker(marker_el):
    """
    마커 요소에서 위로 올라가 응답 루트 그룹을 찾는다.

    응답 구조:
      응답 루트 (AXGroup, class=['overflow-hidden', 'relative'])
        ├── Thinking 섹션 (class=['pl-3'])
        ├── 본문 텍스트
        ├── 액션 카드 (Edited, Ran command)
        └── Files Modified 요약

    마커 → 부모 → 조부모 → ... 로 올라가면서
    자식 수가 3개 이상이고 'overflow-hidden'을 포함하는 AXGroup을 찾는다.
    """
    ancestor = marker_el
    for _ in range(10):
        parent = _get_attr(ancestor, "AXParent")
        if not parent:
            break
        role = str(_get_attr(parent, kAXRoleAttribute) or "")
        if role != "AXGroup":
            ancestor = parent
            continue
        classes = _get_class_list(parent)
        children = _get_attr(parent, kAXChildrenAttribute)
        child_count = len(children) if children else 0
        # 응답 루트: 자식이 3개 이상이고 다양한 요소를 포함
        if child_count >= 3 and "overflow-hidden" in classes:
            return parent
        # 또 다른 패턴: 자식이 많고 text-ide 클래스 포함
        if child_count >= 3 and any("text-ide" in c for c in classes):
            return parent
        ancestor = parent

    # fallback: 마커에서 5~7단계 위 조상을 반환
    ancestor = marker_el
    for i in range(7):
        parent = _get_attr(ancestor, "AXParent")
        if not parent:
            break
        ancestor = parent
        if i >= 4:
            children = _get_attr(ancestor, kAXChildrenAttribute)
            if children and len(children) >= 3:
                return ancestor

    return ancestor


def _find_message_input(window):
    """Message Input (AXTextArea, desc='Message input')을 찾는다."""
    result = [None]

    def scan(el, depth=0):
        if depth > 20 or result[0]:
            return
        role = str(_get_attr(el, kAXRoleAttribute) or "")
        desc = str(_get_attr(el, kAXDescriptionAttribute) or "")
        if role == "AXTextArea" and desc == "Message input":
            result[0] = el
            return
        children = _get_attr(el, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(window)
    return result[0]


def _climb_to_gap8_container(message_input):
    """
    Message Input에서 위로 올라가 class=['gap-8']을 포함하는
    대화 컨테이너를 찾는다.
    """
    ancestor = message_input
    for _ in range(8):
        parent = _get_attr(ancestor, "AXParent")
        if not parent:
            break
        classes = _get_class_list(parent)
        if "gap-8" in classes:
            return parent
        ancestor = parent
    return None


# ── 응답 내용 파싱 ──────────────────────────────────────────


def _parse_response_group(container):
    """
    대화 스레드 컨테이너를 탐색하여 구조화된 응답을 생성한다.

    컨테이너 구조 (gap-y-3, px-4):
      [0] 사용자 메시지 (sticky) → 건너뜀
      [1] 에이전트 응답 루트 (relative) → 내부에 Thinking + 본문 + 액션
      [2~N] 추가 본문, 테이블, 액션 등 → 평탄화되어 있음
      Files Modified / Accept/Reject → 메타 영역

    Returns:
        dict: {thinking, markdown_answer, actions, files_modified}
    """
    result = {
        "thinking": "",
        "markdown_answer": "",
        "actions": [],
        "files_modified": [],
    }

    children = _get_attr(container, kAXChildrenAttribute)
    if not children:
        return result

    md_parts = []
    files_modified = []
    actions = []
    thinking_parts = []

    for child in children:
        role = str(_get_attr(child, kAXRoleAttribute) or "")
        classes = _get_class_list(child)

        # 사용자 메시지 건너뜀 (sticky 클래스)
        if "sticky" in classes:
            continue

        # Accept/Reject 버튼 영역 건너뜀
        if _is_accept_reject_area(child):
            continue

        # Files Modified 라벨
        val = str(_get_attr(child, kAXValueAttribute) or "")
        if val == "Files Modified":
            files_modified = _extract_file_list(container, child)
            continue

        # 숫자만 있는 요소 (파일 수 카운트)
        if val.strip().isdigit():
            continue

        # 파일 목록 영역 (Files Modified 이후)
        if files_modified and "min-w-0" in classes:
            # 이미 추출 완료
            continue

        # 에이전트 응답 루트 (relative + 내부에 Thinking/액션 포함)
        # 이 그룹의 자식을 재귀 파싱
        if "relative" in classes:
            _parse_response_subtree(
                child, md_parts, thinking_parts, actions
            )
            continue

        # AXTable (마크다운 표 렌더링)
        if role == "AXTable":
            table_md = _extract_table(child)
            if table_md:
                md_parts.append(table_md)
            continue

        # 일반 응답 본문
        text = _extract_markdown_from_element(child, depth=0)
        if text and text.strip():
            md_parts.append(text)

    result["thinking"] = "\n".join(thinking_parts)
    result["markdown_answer"] = "\n".join(md_parts)
    result["actions"] = actions
    result["files_modified"] = files_modified

    return result


def _parse_response_subtree(group, md_parts, thinking_parts, actions):
    """
    에이전트 응답 루트(relative) 그룹의 자식을 분류하여 파싱한다.

    이 그룹 안에 Thinking, 액션 카드, 본문 텍스트가 혼재한다.
    overflow-hidden 중첩 그룹이 있으면 재귀적으로 파고든다.
    """
    children = _get_attr(group, kAXChildrenAttribute)
    if not children:
        return

    for child in children:
        classes = _get_class_list(child)

        # Thinking 영역
        if _is_thinking_section(child, classes):
            thinking_text = _extract_thinking(child)
            if thinking_text:
                thinking_parts.append(thinking_text)
            continue

        # 액션 카드 (자체가 relative이고 내부에 Edited/Explored 버튼)
        if _is_action_section(child, classes):
            action = _extract_action(child)
            if action:
                actions.append(action)
            continue

        # overflow-hidden 중첩 응답 그룹 — 재귀 파싱
        # 응답 컨텐츠가 overflow-hidden,relative 안에 한 레벨 더 감싸져 있음
        if "overflow-hidden" in classes:
            _parse_response_subtree(
                child, md_parts, thinking_parts, actions
            )
            continue

        # 일반 본문
        text = _extract_markdown_from_element(child, depth=0)
        if text and text.strip():
            md_parts.append(text)


def _extract_table(table_el):
    """
    AXTable에서 마크다운 표를 복원한다.
    """
    rows = _get_attr(table_el, kAXChildrenAttribute)
    if not rows:
        return ""

    md_rows = []
    for ri, row in enumerate(rows):
        role = str(_get_attr(row, kAXRoleAttribute) or "")
        if role != "AXRow":
            continue
        cells = _get_attr(row, kAXChildrenAttribute) or []
        cell_texts = []
        for cell in cells:
            inner = _collect_inner_text(cell).strip()
            cell_texts.append(inner)
        md_rows.append("| " + " | ".join(cell_texts) + " |")
        # 헤더 행 뒤에 구분선 삽입
        if ri == 0:
            sep = "| " + " | ".join(["---"] * len(cell_texts)) + " |"
            md_rows.append(sep)

    return "\n".join(md_rows)


# ── 유틸리티: DOM 클래스 / 서브롤 기반 분류 ──────────────────


def _get_class_list(el):
    """요소의 AXDOMClassList를 리스트로 반환한다."""
    raw = _get_attr(el, "AXDOMClassList")
    if raw:
        return list(raw)
    return []


def _get_subrole(el):
    """요소의 AXSubrole을 반환한다."""
    return str(_get_attr(el, "AXSubrole") or "")


def _is_thinking_section(el, classes):
    """Thinking 영역인지 확인한다."""
    # Thinking은 접힌 영역: class에 'overflow-hidden', 'pl-3' 포함
    if "pl-3" in classes and "overflow-hidden" in classes:
        return True
    return False


def _is_action_section(el, classes):
    """액션 카드(Edited, Explored 등)인지 확인한다."""
    if "relative" not in classes:
        return False
    # 자식 중 AXButton에 Edited/Explored/Created 텍스트가 있는지 확인
    children = _get_attr(el, kAXChildrenAttribute)
    if not children:
        return False
    for child in children:
        role = str(_get_attr(child, kAXRoleAttribute) or "")
        if role == "AXButton":
            btn_texts = _collect_static_texts(child)
            if any(kw in btn_texts for kw in
                   ["Edited", "Explored", "Created", "Ran"]):
                return True
    return False


def _is_accept_reject_area(el):
    """Accept/Reject 버튼 영역인지 확인한다."""
    classes = _get_class_list(el)
    texts = _collect_static_texts(el)
    if "Reject all" in texts or "Accept all" in texts:
        return True
    # cursor-pointer + opacity 클래스 조합
    if "cursor-pointer" in classes and "transition-[opacity,transform]" in classes:
        return True
    return False


# ── Thinking 추출 ───────────────────────────────────────────


def _extract_thinking(el):
    """Thinking 영역에서 추론 텍스트를 추출한다."""
    texts = []

    def scan(node, depth=0):
        if depth > 10:
            return
        role = str(_get_attr(node, kAXRoleAttribute) or "")
        if role == "AXStaticText":
            val = str(_get_attr(node, kAXValueAttribute) or "").strip()
            # thinking 헤더 건너뜀
            if val and val not in ("Thought for", "undo"):
                texts.append(val)
        children = _get_attr(node, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(el)
    return " ".join(texts) if texts else ""


# ── 액션 카드 추출 ──────────────────────────────────────────


def _extract_action(el):
    """액션 카드에서 구조화된 정보를 추출한다."""
    all_texts = _collect_static_texts_with_class(el)

    action = {"type": "", "detail": ""}

    # 타입 결정
    text_values = [t["text"] for t in all_texts]
    if "Edited" in text_values or "Created" in text_values:
        action["type"] = "file_edit"
        # 파일명 추출
        for t in all_texts:
            if t.get("subrole") == "AXCodeStyleGroup" or _has_class(t, "font-medium"):
                action["file"] = t["text"]
                break
        # diff 정보
        plus_idx = _find_text_idx(text_values, "+")
        minus_idx = _find_text_idx(text_values, "-")
        if plus_idx >= 0 and plus_idx + 1 < len(text_values):
            action["additions"] = text_values[plus_idx + 1]
        if minus_idx >= 0 and minus_idx + 1 < len(text_values):
            action["deletions"] = text_values[minus_idx + 1]

    elif "Ran command" in text_values or "Explored" in text_values:
        action["type"] = "command"
        # 커맨드 추출 (font-mono 클래스)
        for t in all_texts:
            if _has_class(t, "font-mono") and t["text"] not in ("$", " "):
                if "cmd" not in action:
                    action["cmd"] = t["text"]
                else:
                    action["cmd"] += t["text"]
        # 출력 추출
        output_parts = []
        in_output = False
        for t in all_texts:
            if t["text"] == "Exit code":
                in_output = False
            if in_output:
                output_parts.append(t["text"])
            if t["text"] == "$" and _has_class(t, "font-mono"):
                in_output = True
        if output_parts:
            action["output"] = " ".join(output_parts).strip()
        # exit code
        exit_idx = _find_text_idx(text_values, "Exit code")
        if exit_idx >= 0 and exit_idx + 1 < len(text_values):
            action["exit_code"] = text_values[exit_idx + 1]

    else:
        action["type"] = "unknown"
        action["detail"] = " ".join(text_values[:5])

    return action


def _find_text_idx(texts, target):
    """텍스트 리스트에서 target의 인덱스를 반환한다."""
    for i, t in enumerate(texts):
        if t == target:
            return i
    return -1


def _has_class(text_info, class_fragment):
    """text_info의 classes에 class_fragment가 포함되는지 확인한다."""
    return any(class_fragment in c for c in text_info.get("classes", []))


# ── 마크다운 복원 ───────────────────────────────────────────


def _extract_markdown_from_element(el, depth=0):
    """
    요소와 자식을 탐색하여 마크다운 텍스트를 복원한다.

    AXSubrole과 AXDOMClassList로 요소 타입을 식별:
      - sub=AXCodeStyleGroup → `inline code`
      - class에 font-mono → 코드 블록
      - AXStaticText → 일반 텍스트
    """
    if depth > 15:
        return ""

    role = str(_get_attr(el, kAXRoleAttribute) or "")
    subrole = _get_subrole(el)
    classes = _get_class_list(el)

    # AXStaticText: 평문
    if role == "AXStaticText":
        val = str(_get_attr(el, kAXValueAttribute) or "")
        return val

    # AXCodeStyleGroup: 인라인 코드
    if subrole == "AXCodeStyleGroup":
        inner = _collect_inner_text(el)
        return f"`{inner}`"

    # font-mono 코드 영역
    if "font-mono" in classes:
        inner = _collect_inner_text(el)
        return f"`{inner}`"

    # 일반 AXGroup: 자식 연결
    children = _get_attr(el, kAXChildrenAttribute)
    if not children:
        return ""

    parts = []
    for child in children:
        text = _extract_markdown_from_element(child, depth + 1)
        if text:
            parts.append(text)

    return "".join(parts)


# ── 텍스트 수집 유틸리티 ────────────────────────────────────


def _collect_inner_text(el):
    """요소의 모든 자손 텍스트를 연결한다."""
    texts = []

    def scan(node, depth=0):
        if depth > 10:
            return
        role = str(_get_attr(node, kAXRoleAttribute) or "")
        if role == "AXStaticText":
            val = str(_get_attr(node, kAXValueAttribute) or "")
            texts.append(val)
        children = _get_attr(node, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(el)
    return "".join(texts)


def _collect_static_texts(el):
    """요소의 모든 AXStaticText 값을 리스트로 반환한다."""
    result = []

    def scan(node, depth=0):
        if depth > 10:
            return
        role = str(_get_attr(node, kAXRoleAttribute) or "")
        if role == "AXStaticText":
            val = str(_get_attr(node, kAXValueAttribute) or "").strip()
            if val:
                result.append(val)
        children = _get_attr(node, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(el)
    return result


def _collect_static_texts_with_class(el):
    """AXStaticText를 CSS 클래스와 Subrole 정보와 함께 수집한다."""
    result = []

    def scan(node, depth=0):
        if depth > 10:
            return
        role = str(_get_attr(node, kAXRoleAttribute) or "")
        if role == "AXStaticText":
            val = str(_get_attr(node, kAXValueAttribute) or "").strip()
            if val:
                parent = _get_attr(node, "AXParent")
                parent_classes = _get_class_list(parent) if parent else []
                parent_subrole = _get_subrole(parent) if parent else ""
                result.append({
                    "text": val,
                    "classes": parent_classes,
                    "subrole": parent_subrole,
                })
        children = _get_attr(node, kAXChildrenAttribute)
        if children:
            for c in children:
                scan(c, depth + 1)

    scan(el)
    return result


def _extract_file_list(group, files_modified_el):
    """Files Modified 섹션에서 파일 목록을 추출한다."""
    files = []
    # Files Modified 이후의 요소에서 파일명 수집
    children = _get_attr(group, kAXChildrenAttribute)
    if not children:
        return files

    found_marker = False
    for child in children:
        if child == files_modified_el:
            found_marker = True
            continue
        if found_marker:
            texts = _collect_static_texts(child)
            for t in texts:
                if t.endswith(".py") or t.endswith(".js") or \
                   t.endswith(".ts") or t.endswith(".md") or "." in t:
                    files.append(t)

    return files


# ── 공개 API ────────────────────────────────────────────────


def extract_response(window):
    """
    Agent Panel에서 마지막 에이전트 응답을 추출한다.

    Args:
        window: AX 윈도우 레퍼런스

    Returns:
        dict or None: 구조화된 응답
            {
                "thinking": str,
                "markdown_answer": str,
                "actions": list[dict],
                "files_modified": list[str],
            }
    """
    group = _find_last_response_group(window)
    if not group:
        return None

    return _parse_response_group(group)
