# Agent Panel vs Agent Manager — 완전 비교 분석 (수정판 v2)

> **수정 이력**: v1에서 두 가지 오류 수정
> 1. ~~Agent Manager에 Message Input 없음~~ → ✅ **있음** (대화 진입 시 depth=15)
> 2. ~~Agent Panel에서 대화 전환 불가~~ → ✅ **가능** (Past Conversations 오버랩 패널)

---

## 1. 기능 비교표

| 기능 | Agent Panel | Agent Manager |
|:---|:---|:---|
| **인스턴스** | 윈도우마다 독립 ✅ | 앱 전체 1개 (싱글톤) ⚠️ |
| **동시 접근** | 안전 — 완전 격리 | 위험 — 뮤텍스 필요 |
| **Message Input** | ✅ depth≈17 | ✅ depth=15 (대화 진입 후) |
| **Send Button** | ✅ `"Send message"` (depth=16) | ✅ (입력 시 나타남) |
| **현재 대화 타이틀** | ✅ `AXStaticText` depth=12 | ✅ Button title에 포함 |
| **대화 전환** | ✅ Past Conversations 오버랩 | ✅ 대화 목록 직접 클릭 |
| **대화 생성** | ✅ `AXLink[0]` (+ 버튼) | ✅ `"add New Conversation"` 버튼 |
| **대화 검색** | ✅ 오버랩 내 검색 필드 | ✅ `"Conversation History"` 버튼 |
| **워크스페이스별 분류** | ✅ 오버랩에서 그룹화 | ✅ Workspaces 폴더 뷰 |
| **모드 선택** | ✅ Planning/Code 전환 | ❌ 없음 |
| **모델 선택** | ✅ Claude Opus 등 | ❌ 없음 |

---

## 2. AX 트리 매핑

### 2.1 Agent Panel (에디터 윈도우 내장)

```
[depth=12] AXGroup (Agent Panel 헤더)
├── AXStaticText value="<대화 타이틀>"     ← 현재 대화 제목
├── AXLink ─────── + 새 대화               ← links[0]
├── AXLink ─────── ⏰ Past Conversations   ← links[1] ★
├── AXPopUpButton ─ ⋯ 더보기 메뉴
├── AXLink ─────── 기타
└── AXGroup id="conversation" ── 대화 영역
    └── AXGroup id="antigravity.agentSidePanelInputBox"
        ├── AXPopUpButton "Add context"
        ├── AXPopUpButton "Select conversation mode, current: Planning"
        ├── AXPopUpButton "Select model, current: Claude Opus 4.6 (Thinking)"
        ├── AXButton "Record voice memo"
        └── AXButton "Send message"
```

> **주의**: AXLink 버튼들은 title/desc가 **모두 비어있음**. 순서(index)로만 식별 가능.

#### Past Conversations 오버랩 (links[1] AXPress 후 열림)

```
[depth=14] 오버랩 내 대화 항목 (AXStaticText)
├── "Running in <워크스페이스>"
│   └── "<대화 타이틀>" + "<시간>"
├── "Recent in <워크스페이스>"
│   ├── "<대화 타이틀 1>" + "<시간>"
│   └── "<대화 타이틀 2>" + "<시간>"
├── "Other Conversations"
│   ├── "<대화 타이틀>" + "<워크스페이스>" + "<시간>"
│   └── ...
└── "Show <N> more..."
```

- 대화 항목은 **depth=13에서 AXPress 가능** (클릭하면 해당 대화로 전환)
- **Escape로 닫힘**

---

### 2.2 Agent Manager (싱글톤 윈도우, Cmd+E)

#### 대화 목록 뷰 (기본)
```
[depth=10] 네비게이션 버튼
├── "arrow_back" / "arrow_forward"
├── "add New Conversation"
├── "history Conversation History"
├── "import_contacts Knowledge"
├── "settings Settings"
└── "lightbulb Provide Feedback"

[depth=11] 대화 항목 (AXButton)
├── "progress_activity <타이틀> now"   ← 현재 실행 중
├── "<타이틀> <시간>"                    ← 완료됨
├── "Open Workspace"
└── "See all (<N>)"
```

#### 대화 진입 뷰 (대화 클릭 후)
```
[depth=15] AXTextArea desc="Message input"   ← 메시지 입력 가능!
[depth=15+] 대화 내용, 되돌리기 버튼 등
```

- **나가기**: `arrow_back` 버튼 (depth=10)

---

## 3. 실동작 검증 결과

### 3.1 Past Conversations 전체 플로우 (✅ 검증 완료)

| 단계 | 동작 | 결과 |
|:---|:---|:---|
| 1 | 현재 타이틀 확인 | `"Agent"` (빈 새 대화) |
| 2 | links[1] AXPress → 오버랩 열림 | ✅ 6개 대화 표시됨 |
| 3 | 대화 항목 AXPress (depth=13) | ✅ 클릭 성공 |
| 4 | 전환 후 타이틀 확인 | `"Analyzing Antigravity..."` ✅ |
| 5 | Past Conversations 재오픈 | ✅ 동일 오버랩 |
| 6 | 원래 대화 클릭 → 복귀 | ✅ 타이틀 일치 |

### 3.2 Agent Manager 진입 후 Message Input (✅ 검증 완료)

```
대화 버튼 AXPress → 진입 뷰 전환 → AXTextArea desc="Message input" 확인 (depth=15)
```

---

## 4. 동시성 분석 (멀티 서브에이전트)

### Agent Panel — 안전 ✅

| 시나리오 | 결과 |
|:---|:---|
| 서브에이전트 A(윈도우1) + B(윈도우2) 동시 접근 | 독립 Panel → **격리 완벽** |
| A가 메시지 입력 중, B도 동시 입력 | 각각 다른 AXTextArea → **충돌 없음** |
| A가 Past Conversations 열기, B도 열기 | 각각 다른 오버랩 → **충돌 없음** |

### Agent Manager — 위험 ⚠️

| 시나리오 | 결과 |
|:---|:---|
| A가 Manager에서 대화 검색 중 B가 접근 | **같은 윈도우** → 상태 오염 |
| A가 대화1 진입, B가 대화2로 전환 시도 | A의 컨텍스트 **파괴** |

---

## 5. 최종 아키텍처 권고

### 우선 경로: Agent Panel ONLY

**Agent Panel만으로 모든 핵심 작업이 가능합니다:**

1. **현재 대화 확인**: depth=12 AXStaticText (AXLink 형제 존재 여부로 식별)
2. **대화 전환**: links[1] AXPress → 오버랩에서 대화 선택
3. **새 대화 생성**: links[0] AXPress
4. **메시지 입력/전송**: `id="antigravity.agentSidePanelInputBox"` 내부
5. **모드/모델 설정**: 동일 AXGroup 내 AXPopUpButton

### 보조 경로: Agent Manager (뮤텍스 보호 하에)

다음 경우에만 사용:
- Past Conversations에서 원하는 대화를 찾을 수 없을 때
- 워크스페이스 전체에 걸친 대화 검색이 필요할 때
- Agent Panel의 UI 버그 발생 시 (예: workflow 항목 미노출)

---

## 6. 식별자 참조

### 헤더 버튼 (title/desc 비어있음 → 순서로 식별)

```python
siblings = parent_of_title.children
links = [s for s in siblings if s.role == "AXLink"]
NEW_CONVERSATION = links[0]      # + 버튼
PAST_CONVERSATIONS = links[1]    # ⏰ 시계 아이콘
```

### Input Box (DOM ID로 안정적 접근)

```python
input_box = find_by_domid("antigravity.agentSidePanelInputBox")
send_btn = find_child(input_box, role="AXButton", title="Send message")
mode_btn = find_child(input_box, role="AXPopUpButton", title_contains="conversation mode")
model_btn = find_child(input_box, role="AXPopUpButton", title_contains="Select model")
```

### Past Conversations 대화 항목

```python
# depth=13에서 AXPress 가능한 요소 → 자식 텍스트로 대화 타이틀 추출
# 제외 목록: 'Running in', 'Recent in', 'Other Conversations', 'Show ', 'AI may make mistakes'
```
