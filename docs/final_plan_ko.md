# 🏗️ AG-Agent: 최종 구현 기획서 (Final)

> 작성일: 2026-03-29 | 버전: v2.0 (최종)  
> 이전 문서 통합: implementation_plan + supplement + event_driven_design

---

## 📌 한 줄 요약

> **Antigravity IDE의 Agent Panel을 AX API로 자동 제어하여,  
> 서브에이전트가 대화를 찾고, 입력하고, 응답을 수집하는 이벤트 기반 CLI 도구**

---

## 1. 현재 → 목표

### 현재 (ask_and_wait.py — 284줄 단일 파일)
```
python3 ask_and_wait.py "질문"

❌ 대화 선택 불가 (첫 번째 윈도우만)
❌ 새 대화/이전 대화 전환 불가
❌ 세션/이력 관리 없음
❌ 동시 실행 불가
❌ 모든 값 하드코딩
❌ time.sleep() 기반 (이벤트 없음)
```

### 목표
```
ag-agent ask "질문"                      # 현재 대화에 질문
ag-agent ask "질문" --session my-task     # 특정 세션에 질문
ag-agent ask "질문" --new                 # 새 대화 생성 후 질문
ag-agent session list                     # 세션 목록
ag-agent session connect my-task          # 이전 대화에 연결
ag-agent status                           # 전체 상태 표시

✅ 이벤트 기반 (조건 감시, 타임아웃 없음)
✅ 클립보드 FIFO 큐 (멀티에이전트 안전)
✅ 세션별 이력 보존
✅ Agent Panel ONLY (Manager 제외)
```

---

## 2. 설계 전제 (사전 조사로 확정)

### 2.1 Agent Panel 구조

```
┌──────────────────────────────────────────┐
│ 타이틀   │ [+새대화] │ [⏰이전] │ [⋯]     │  ← 헤더 (depth=12)
├──────────────────────────────────────────┤
│ 대화 내용                                 │
├──────────────────────────────────────────┤
│ [모드▾] [모델▾] │ 입력창...  │ [전송]     │  ← 입력 (DOM ID: antigravity.agentSidePanelInputBox)
└──────────────────────────────────────────┘

[+새대화] = links[0] AXPress → 빈 대화 생성 (타이틀 "Agent")
[⏰이전]  = links[1] AXPress → Past Conversations 오버랩
```

### 2.2 Past Conversations 오버랩

```
┌──────────────────────────────────────┐
│ 🔍 Select a conversation...          │  ← AXTextField (AXValue 직접 쓰기 ✅)
├──────────────────────────────────────┤
│ Running in integrate_antigravity     │
│   ⊘ Analyzing Antigravity...   10m  │  ← depth=13 AXPress로 전환
├──────────────────────────────────────┤
│ Recent / Other 대화들...              │
└──────────────────────────────────────┘
```

### 2.3 입력 방식

| 대상 | 방식 | 이유 |
|:---|:---|:---|
| 검색 필드 (AXTextField) | AXValue 직접 쓰기 | 표준 필드, 클립보드 불필요 |
| 메시지 입력 (AXTextArea) | 클립보드 + Cmd+V | Electron 제한 (AXValue 무시, Unicode 이벤트 무시) |

### 2.4 상태 전이 (응답 감지)

```
Send 있음 ──→ Send 사라짐 ──→ Cancel 나타남 ──→ Send 다시 나타남
(idle)        (전송 확인)      (생성 중)          (완료)
```

---

## 3. 핵심 원칙

### 3.1 이벤트 기반 — 시간을 기다리지 않는다

```python
# ❌ 금지
time.sleep(1.0)  # "1초면 되겠지"

# ✅ 올바름
wait_until(lambda: condition == True)  # 조건이 충족될 때까지 감시
```

`wait_until()` 내부의 `time.sleep(0.05)`는 "대기"가 아니라 **CPU 양보**입니다.

### 3.2 타임아웃 없음

| ❌ 제거 | 이유 |
|:---|:---|
| `config.yaml timing:` 섹션 | 시간 기반 설정 자체 불필요 |
| `range(240)` 120초 캡 | 조건 감시에 캡이 없어야 함 |
| poll_timeout, poll_interval 등 | 전부 불필요 |

### 3.3 유일하게 남는 sleep

```python
# 1. wait_until() 내 CPU 양보 tick (0.05초)
# 2. keydown↔keyup HW 간격 (0.01초) — 물리적 제약
```

---

## 4. 모듈 구조

```
main/src/
├── __init__.py
├── __main__.py                    ← python -m src
├── cli.py                         ← CLI 명령 파싱 (argparse)
│
├── ax/                            ← macOS Accessibility 계층
│   ├── __init__.py
│   ├── discovery.py               ← 앱/윈도우 탐색
│   ├── panel.py                   ← Agent Panel 조작 (헤더, 타이틀, 버튼)
│   ├── conversations.py           ← Past Conversations (검색, 선택, 전환)
│   └── input.py                   ← 키보드 시뮬레이션 + ClipboardQueue
│
├── session/                       ← 세션 관리 계층
│   ├── __init__.py
│   ├── manager.py                 ← 세션 CRUD + 자동 연결
│   ├── storage.py                 ← .ag-sessions/ 파일시스템
│   └── lock.py                    ← 윈도우 단위 배타적 잠금
│
├── core/                          ← 비즈니스 로직 계층
│   ├── __init__.py
│   ├── orchestrator.py            ← 메인 이벤트 체인
│   ├── events.py                  ← wait_until() + 이벤트 카탈로그
│   ├── prompt.py                  ← JSON Bridge 프롬프트 빌더
│   └── response.py                ← 응답 수집 + 세션 보존
│
└── config/                        ← 설정 계층
    ├── __init__.py
    ├── loader.py                  ← YAML 로딩 + 기본값
    └── defaults.py                ← 기본 설정값
```

### 의존성 흐름 (단방향)

```
CLI → Orchestrator → Panel → Discovery
                │       └→ Conversations
                │       └→ Input (ClipboardQueue)
                └→ Session Manager → Storage
                │                  └→ Lock
                └→ Events
                └→ Response
                └→ Config (모든 모듈이 읽음)
```

---

## 5. 각 모듈 상세

### 5.1 core/events.py — 이벤트 시스템

```python
def wait_until(condition_fn, tick=0.05):
    """조건이 참이 될 때까지 감시. 타임아웃 없음."""
    while not condition_fn():
        time.sleep(tick)
```

17개 이벤트 카탈로그:

| ID | 이벤트 | 감시 조건 |
|:---|:---|:---|
| E1 | APP_ACTIVE | `app.isActive() == True` |
| E2 | AX_READY | `AXWindows != None` |
| E3 | WINDOW_FOUND | 윈도우 타이틀에 워크스페이스 포함 |
| E4 | PANEL_TITLE_READABLE | depth=12 AXStaticText + AXLink 형제 |
| E5 | INPUT_FOUND | `AXTextArea desc="Message input"` |
| E6 | INPUT_FOCUSED | `input.focused == True` |
| E7 | TEXT_PASTED | `input.value != ""` |
| E8 | SEND_DISAPPEARED | Send 버튼 사라짐 |
| E9 | CANCEL_APPEARED | Cancel 버튼 나타남 |
| E10 | SEND_REAPPEARED | Send 버튼 다시 나타남 |
| E11 | RESPONSE_FILE_EXISTS | 응답 파일 생성됨 |
| E12 | OVERLAY_OPENED | 검색 필드 나타남 |
| E13 | SEARCH_FILTERED | 대화 항목 수 변화 |
| E14 | CONV_SWITCHED | Panel 타이틀 == 목표 |
| E15 | OVERLAY_CLOSED | 검색 필드 사라짐 |
| E16 | CLIPBOARD_TURN | 내 티켓이 큐 최선두 |
| E17 | NEW_CHAT_CREATED | Panel 타이틀 == "Agent" |

---

### 5.2 ax/input.py — ClipboardQueue

```
/tmp/.ag-clipboard-queue/
├── tickets/
│   ├── 0001_pid12345          ← 에이전트 A (먼저 도착)
│   ├── 0002_pid67890          ← 에이전트 B
│   └── 0003_pid11111          ← 에이전트 C
└── processing.lock            ← 실행 중 잠금

동작:
  1. 티켓 발급 (번호표)
  2. wait_until(내 티켓이 맨 앞) ← 이벤트 E16
  3. flock 획득
  4. 클립보드 백업 → 텍스트 설정 → Cmd+V
  5. wait_until(input.value != "") ← 이벤트 E7
  6. 클립보드 복원
  7. flock 해제
  8. 티켓 삭제 → 다음 에이전트 진행
```

FIFO 순서 보장. 기아(starvation) 불가능.

---

### 5.3 session/storage.py — 세션 파일 구조

```
{워크스페이스 루트}/
└── .ag-sessions/
    ├── config.yaml                  ← 워크스페이스별 설정
    ├── active_session               ← 마지막 사용한 세션 ID
    └── sessions/
        └── {session-id}/
            ├── metadata.json        ← 세션 식별 정보
            ├── history.jsonl        ← 대화 이력 (턴 단위)
            └── responses/
                ├── 001.json         ← 턴 1 응답 전문
                └── 002.json         ← 턴 2 응답 전문
```

**metadata.json 필드:**

| 필드 | 용도 |
|:---|:---|
| `id` | 세션 고유 식별자 (CLI `--session` 인자) |
| `title` | 사람이 읽는 세션 이름 |
| `panel_title` | Agent Panel 대화 타이틀 (**대화 찾기에 사용**) |
| `workspace` | 워크스페이스 절대 경로 |
| `window_title_pattern` | 윈도우 타이틀 매칭 패턴 |
| `created_at` / `updated_at` | 생성/수정 시각 |
| `status` | `active` / `idle` / `archived` |
| `total_turns` | 누적 턴 수 |
| `tags` | 검색/분류 태그 |
| `description` | 세션 설명 |

**history.jsonl 스키마:**

```jsonl
{"turn":1,"ts":"...","role":"user","content":"질문 원문","prompt_length":1234}
{"turn":1,"ts":"...","role":"assistant","summary":"응답 요약","response_file":"responses/001.json","duration_sec":73}
```

---

### 5.4 core/orchestrator.py — 메인 이벤트 체인

```
ag-agent ask "질문" --session my-task

[E1] APP_ACTIVE
  └→ [E2] AX_READY
       └→ [E3] WINDOW_FOUND
            └→ [E4] PANEL_TITLE_READABLE
                 │
                 ├─ title == session.panel_title? → Yes → 진행
                 └─ No →
                      links[1] AXPress
                      └→ [E12] OVERLAY_OPENED
                           └→ 검색어 AXValue 쓰기
                                └→ [E13] SEARCH_FILTERED
                                     └→ 대화 AXPress
                                          └→ [E14] CONV_SWITCHED

[E5] INPUT_FOUND
  └→ [E6] INPUT_FOCUSED
       └→ [E16] CLIPBOARD_TURN (큐 대기)
            └→ Cmd+V
                 └→ [E7] TEXT_PASTED
                      └→ 큐 해제
                           └→ Cmd+Enter
                                └→ [E8] SEND_DISAPPEARED
                                     └→ [E10] SEND_REAPPEARED
                                          └→ [E11] RESPONSE_FILE_EXISTS
                                               └→ 파일 읽기 + 세션 기록
```

---

### 5.5 core/prompt.py — JSON Bridge (기존 패턴 개선)

```
기존: CWD/.agent_response.json
개선: {workspace}/.ag-sessions/sessions/{session-id}/responses/{turn}.json

기존: 응답 파일 삭제 (os.remove)
개선: 세션 디렉토리에 보존 (이력용)
```

---

### 5.6 config/loader.py — config.yaml

```yaml
# .ag-sessions/config.yaml

# 타겟 프로세스
process:
  bundle_id: "com.google.antigravity"

# AX 요소 식별자 (UI 변경 시 여기만 수정)
ax:
  input_box_dom_id: "antigravity.agentSidePanelInputBox"
  send_button_desc: "Send message"
  cancel_button_desc: "Cancel"
  search_placeholder: "Select a conversation"

# 응답
response:
  use_json_bridge: true
```

> **`timing:` 섹션 없음** — 이벤트 기반이므로 시간 설정이 필요 없음

---

## 6. 구현 단계

### Phase 1: 뼈대 — 이벤트 시스템 + 모듈 분리 + 기본 ask

```
□ src/ 디렉토리 구조 생성
□ core/events.py — wait_until() + 이벤트 카탈로그
□ ax/discovery.py — find_antigravity, list_windows
□ ax/panel.py — get_panel_title, find_input, find_send, get_state
□ ax/input.py — simulate_keypress (ClipboardQueue 없이 단순 paste)
□ core/orchestrator.py — 기본 ask 이벤트 체인
□ core/prompt.py — JSON Bridge 프롬프트
□ core/response.py — 응답 파일 수집
□ config/defaults.py — 기본값
□ cli.py — ask 명령만
□ __main__.py — 엔트리포인트

검증: python -m src ask "안녕"
  → 이벤트 체인으로 동작
  → time.sleep()이 wait_until() 내부에만 존재
```

### Phase 2: 대화 라우팅 — 검색 + 전환 + 생성

```
□ ax/panel.py — click_new_conversation, click_past_conversations
□ ax/conversations.py — search, select, list, close_overlay
□ core/orchestrator.py — --new, --session 옵션 통합
□ 이벤트: E12~E15, E17 구현

검증:
  → "ask 질문 --new" → 새 대화에서 질문
  → "ask 질문 --session X" → Past Conversations에서 검색 → 전환 → 질문
```

### Phase 3: 세션 관리 — 이력 + 자동 연결

```
□ session/storage.py — .ag-sessions/ 디렉토리 CRUD
□ session/manager.py — 세션 생성/조회/연결 + active_session
□ session/lock.py — fcntl.flock (윈도우 단위)
□ config/loader.py — config.yaml 로딩
□ core/prompt.py — 응답 경로를 세션별로 변경
□ core/response.py — 응답 파일 보존 (삭제 대신 이동)
□ cli.py — session list, session connect, session show

검증:
  → "session list" → 세션 목록
  → 질문 후 history.jsonl에 기록 확인
  → 재실행 시 active_session으로 자동 연결
```

### Phase 4: 클립보드 큐 + 안정화

```
□ ax/input.py — ClipboardQueue (티켓 기반 FIFO)
□ 이벤트 E16 (CLIPBOARD_TURN) 구현
□ 에러 복구: AX 요소 미발견 시 재감시 (wait_until, 타임아웃 없음)
□ Cancel 버튼으로 생성 중단 기능
□ 프로세스 크래시 감지 (PID 생존 확인)
□ cli.py — status, debug tree 서브커맨드

검증:
  → 2개 에이전트 동시 실행 → 클립보드 충돌 없음
  → 한 에이전트가 paste 중 다른 에이전트가 큐에서 대기 후 순차 실행
```

---

## 7. 파일 목록 및 규모

| 파일 | 역할 | 예상 줄수 |
|:---|:---|:---|
| `core/events.py` | wait_until + 이벤트 카탈로그 | ~80 |
| `core/orchestrator.py` | 메인 이벤트 체인 | ~200 |
| `core/prompt.py` | JSON Bridge 프롬프트 | ~40 |
| `core/response.py` | 응답 수집/보존 | ~60 |
| `ax/discovery.py` | 앱/윈도우 탐색 | ~80 |
| `ax/panel.py` | Panel 조작 (헤더, 버튼, 상태) | ~150 |
| `ax/conversations.py` | Past Conversations (검색, 선택) | ~120 |
| `ax/input.py` | 키보드 + ClipboardQueue | ~120 |
| `session/manager.py` | 세션 CRUD | ~100 |
| `session/storage.py` | 파일시스템 저장 | ~80 |
| `session/lock.py` | 윈도우 잠금 | ~40 |
| `config/loader.py` | YAML 로딩 | ~60 |
| `config/defaults.py` | 기본 설정값 | ~30 |
| `cli.py` | CLI 인터페이스 | ~100 |
| `__main__.py` | 엔트리포인트 | ~5 |
| `__init__.py ×5` | 패키지 초기화 | ~5 |
| **합계** | | **~1,270** |

---

## 8. 참조 문서 (이 문서에 통합됨)

| 문서 | 내용 | 상태 |
|:---|:---|:---|
| `agent_panel_vs_manager_ko.md` | Panel vs Manager 비교 | → Manager 제외 확정 |
| `pre_investigation_results_ko.md` | 사전 조사 4건 | → 본 문서에 반영 |
| `implementation_plan_ko.md` | 기획서 v1.0 | → 본 문서로 대체 |
| `implementation_supplement_ko.md` | 보완 #1 (세션, JSON Bridge, 클립보드) | → 본 문서에 통합 |
| `event_driven_design_ko.md` | 보완 #2 (이벤트 기반 설계) | → 본 문서에 통합 |
