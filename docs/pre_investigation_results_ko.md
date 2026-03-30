# 사전 조사 결과 보고서

> 조사일: 2026-03-29 | 대상: Agent Panel (Agent Manager 제외)
> 모든 항목 실동작 검증 완료

---

## 조사 1: Past Conversations 검색 필드 동작 ✅

| 항목 | 결과 |
|:---|:---|
| **검색 필드** | `AXTextField placeholder="Select a conversation"` (depth=14) |
| **AXValue 직접 쓰기** | ✅ `err=0`, 실제 값 변경됨 |
| **필터링 동작** | ✅ `"Verifying"` 입력 → 10개 → 2개로 필터링 |
| **클립보드 필요 여부** | ❌ 불필요 — AXValue 직접 쓰기로 충분 |

### 검색 사용 코드 패턴

```python
# 1. 검색 필드 찾기
search_field = find_by_role_placeholder("AXTextField", "Select a conversation")

# 2. 검색어 입력 (클립보드 불필요!)
AXUIElementSetAttributeValue(search_field, kAXFocusedAttribute, True)
AXUIElementSetAttributeValue(search_field, kAXValueAttribute, "검색어")

# 3. 필터링된 결과에서 대화 선택 (depth=13, AXPress)
```

---

## 조사 2: 새 대화 생성 (links[0] AXPress) ✅

| 항목 | 결과 |
|:---|:---|
| **생성 트리거** | `links[0]` (헤더의 첫 번째 AXLink) AXPress |
| **타이틀 변화** | `"Analyzing Antigravity..."` → `"Agent"` (빈 새 대화) |
| **헤더 구조** | 동일 (6개 요소: StaticText, Link×3, PopUpButton, Group) |
| **Message Input** | ✅ 존재 (depth=18) |
| **Input Box DOM ID** | ✅ `antigravity.agentSidePanelInputBox` |
| **Input Box 자식** | 7개: AXGroup×2, Add context, Mode, Model, Voice, Send |
| **복귀** | ✅ Past Conversations → 원래 대화 클릭으로 정상 복귀 |

### 새 대화 식별 방법

```python
# 빈 새 대화의 타이틀은 항상 "Agent"
title = get_panel_title(editor)
is_new_empty_chat = (title == "Agent")
```

---

## 조사 3: Message Input AXValue 직접 쓰기 ❌

| 항목 | 결과 |
|:---|:---|
| **AXValue 직접 쓰기** | ❌ err=0 반환하지만 실제 값 안 바뀜 |
| **원인** | Electron/Chromium의 AXTextArea는 AXValue 쓰기 미지원 |
| **클립보드 붙여넣기** | ✅ Cmd+V로 정상 입력됨 |
| **지우기** | ✅ Cmd+A + Delete로 가능 |

### 결론: 입력 방식 분기

| 요소 | 입력 방식 | 이유 |
|:---|:---|:---|
| **검색 필드** (AXTextField) | AXValue 직접 쓰기 ✅ | 표준 텍스트 필드 |
| **Message Input** (AXTextArea) | 클립보드 + Cmd+V ☑️ | Electron 제한 |

> **클립보드 오염 문제**: 사용자의 클립보드를 덮어쓰므로, 
> 입력 전 클립보드 백업 → 입력 → 클립보드 복원 패턴 필요

```python
# 클립보드 보존 패턴
def safe_paste(text):
    pb = NSPasteboard.generalPasteboard()
    backup = pb.stringForType_(NSPasteboardTypeString)  # 백업
    
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    simulate_keypress(9, use_cmd=True)  # Cmd+V
    time.sleep(0.5)
    
    # 원래 클립보드 복원
    pb.clearContents()
    if backup:
        pb.setString_forType_(backup, NSPasteboardTypeString)
```

---

## 조사 4: 응답 완료 감지 방법 ✅

### 현재 대화 상태별 AX 요소 변화 (검증됨)

| 상태 | Send message 버튼 | Cancel 버튼 | 상태 텍스트 |
|:---|:---|:---|:---|
| **idle** (대기) | ✅ 존재 | ❌ 없음 | 없음 |
| **generating** (생성 중) | ❌ 사라짐 | ✅ 나타남 (depth=16) | `"Running"` (depth=16) |
| **thinking** (사고 중) | ❌ 사라짐 | ✅ 나타남 | `"Thought for Ns"` (depth=18) |

### 감지 전략 (기존 + 보강)

```python
def wait_for_generation(editor):
    """3단계 감지 전략"""
    
    # Phase 1: Send 버튼 사라짐 확인 (생성 시작 감지)
    for _ in range(20):  # 최대 5초
        time.sleep(0.25)
        if not find_send_button(editor):
            break
    
    # Phase 2: Cancel 버튼 또는 "Running" 텍스트 감시 (생성 진행 중)
    # (선택적 — 진행 상태 로깅용)
    
    # Phase 3: Send 버튼 재출현 확인 (생성 완료)
    for _ in range(240):  # 최대 120초
        time.sleep(0.5)
        if find_send_button(editor):
            return True
    
    return False  # 타임아웃
```

### 추가 발견: Cancel 버튼

- **depth=16**: `desc="Cancel"` — Agent Panel 레벨의 취소
- **depth=20**: `t="Cancel"` — 개별 명령(background command) 취소

> 서브에이전트가 **응답이 너무 오래 걸릴 때 취소**하는 기능도 구현 가능

---

## 종합 요약

| # | 조사 항목 | 결과 | 구현 영향 |
|:---|:---|:---|:---|
| 1 | 검색 필드 필터링 | ✅ AXValue 직접 쓰기 가능 | 클립보드 불필요, 안정적 검색 가능 |
| 2 | 새 대화 생성 | ✅ links[0] AXPress | 타이틀 "Agent"로 식별, 구조 동일 |
| 3 | Message Input 직접 쓰기 | ❌ Electron 제한 | 클립보드 방식 필수 (백업/복원 패턴) |
| 4 | 응답 완료 감지 | ✅ Send 사라짐/재출현 | 기존 방식 유효 + Cancel 보강 가능 |

### 구현 시 핵심 설계 결정

1. **입력 방식 이원화**: 검색 = AXValue, 메시지 = 클립보드
2. **클립보드 보존**: 입력 전후 백업/복원 필수
3. **상태 감지 3원소**: Send 버튼(idle), Cancel 버튼(생성 중), Running 텍스트(진행 중)
4. **새 대화 식별**: 타이틀 == "Agent" → 빈 새 대화
