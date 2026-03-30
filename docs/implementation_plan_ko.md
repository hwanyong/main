# 🏗️ Antigravity 서브에이전트 오케스트레이터 — 구현 기획서

> 작성일: 2026-03-29 | 버전: v1.0

---

## 📌 한 줄 요약

> **Antigravity IDE의 Agent Panel을 AX(Accessibility) API로 자동 제어하여,  
> 여러 서브에이전트가 각자의 대화를 찾고, 입력하고, 응답을 수집하는 CLI 도구**

---

## 1. 현재 → 목표

### 현재 (ask_and_wait.py — 284줄 단일 파일)

```
사용법:  python3 ask_and_wait.py "질문"

동작:    앱 찾기 → 첫 번째 윈도우 → Message Input에 붙여넣기 → 응답 대기

한계:
  ❌ 어떤 대화에 보내는지 선택 불가
  ❌ 새 대화 생성 불가
  ❌ 이전 대화로 복귀 불가
  ❌ 세션/이력 관리 없음
  ❌ 동시에 여러 에이전트 실행 불가
  ❌ 설정 파일 없음 (모든 값 하드코딩)
```

### 목표

```
사용법:  ag-agent ask "질문"                     # 현재 대화에 질문
         ag-agent ask "질문" --session my-task    # 특정 세션에 질문
         ag-agent ask "질문" --new                # 새 대화 생성 후 질문
         ag-agent session list                    # 세션 목록
         ag-agent session connect my-task         # 이전 대화에 연결

동작:    서브에이전트가 자동으로...
  ✅ 원하는 대화를 검색해서 찾아감
  ✅ 없으면 새 대화를 생성
  ✅ 메시지를 입력하고 응답을 수집
  ✅ 세션 이력을 파일로 저장
  ✅ 다음 실행 시 이전 대화에 자동 복귀

여러 서브에이전트가 각각 다른 윈도우에서 동시에 실행 가능
```

---

## 2. 핵심 전제 (사전 조사에서 확인된 사실)

### 2.1 Agent Panel이 전부다 (Manager 제외)

```
Agent Panel (에디터 윈도우 내장) 하나로 모든 것이 가능:

  ┌─────────────────────────────────────────┐
  │ 대화 타이틀  │  [+]  │  [⏰]  │  [⋯]   │  ← 헤더 (depth=12)
  ├─────────────────────────────────────────┤
  │                                         │
  │  대화 내용 영역                           │
  │                                         │
  ├─────────────────────────────────────────┤
  │ [모드▾] [모델▾] │ 입력창... │ [전송]    │  ← 입력 영역
  └─────────────────────────────────────────┘

  [+] = links[0] = 새 대화 생성
  [⏰] = links[1] = Past Conversations (오버랩 패널)
```

### 2.2 Past Conversations 오버랩

```
[⏰] 클릭 시 열리는 오버랩:

  ┌─────────────────────────────────────┐
  │ 🔍 Select a conversation...         │  ← 검색 필드 (AXValue 직접 쓰기 ✅)
  ├─────────────────────────────────────┤
  │ Running in integrate_antigravity    │
  │   ⊘ Analyzing Antigravity... 10m   │  ← 클릭하면 해당 대화로 전환
  ├─────────────────────────────────────┤
  │ Recent in integrate_antigravity     │
  │   Analyzing Project Struct... 3h    │
  │   Analyzing Project Codeba... 11h   │
  ├─────────────────────────────────────┤
  │ Other Conversations                 │
  │   Verifying System... test 12h      │
  │   Show 7 more...                    │
  └─────────────────────────────────────┘

  ※ Escape로 닫힘
```

### 2.3 입력 방식 분기 (사전 조사 결과)

```
┌──────────────────┬────────────────────┬────────────────────┐
│ 대상              │ 방법               │ 이유               │
├──────────────────┼────────────────────┼────────────────────┤
│ 검색 필드          │ AXValue 직접 쓰기  │ 표준 AXTextField    │
│ (AXTextField)    │ → 클립보드 불필요   │                    │
├──────────────────┼────────────────────┼────────────────────┤
│ 메시지 입력        │ 클립보드 + Cmd+V   │ Electron 제한      │
│ (AXTextArea)     │ → 백업/복원 필수    │ AXValue 무시됨     │
└──────────────────┴────────────────────┴────────────────────┘
```

### 2.4 응답 상태 감지

```
┌──────────┬──────────────┬──────────────┬──────────────────┐
│ 상태      │ Send 버튼     │ Cancel 버튼   │ 텍스트           │
├──────────┼──────────────┼──────────────┼──────────────────┤
│ 대기      │ ✅ 있음       │ ❌ 없음       │ —               │
│ 생성 중   │ ❌ 사라짐     │ ✅ 나타남      │ "Running"       │
│ 사고 중   │ ❌ 사라짐     │ ✅ 나타남      │ "Thought for Ns" │
│ 완료      │ ✅ 다시 나타남 │ ❌ 사라짐      │ —               │
└──────────┴──────────────┴──────────────┴──────────────────┘
```

---

## 3. 모듈 구조

### 3.1 디렉토리 설계

```
main/src/
├── __init__.py
├── __main__.py              ← python -m src 엔트리포인트
│
├── cli.py                   ← CLI 명령 파싱 (argparse)
│
├── ax/                      ← macOS Accessibility 계층
│   ├── __init__.py
│   ├── discovery.py         ← 앱/윈도우 탐색
│   ├── panel.py             ← Agent Panel 조작 (핵심!)
│   ├── conversations.py     ← Past Conversations 오버랩
│   └── input.py             ← 키보드/클립보드 입력
│
├── session/                 ← 세션 관리 계층
│   ├── __init__.py
│   ├── manager.py           ← 세션 생성/조회/연결
│   ├── storage.py           ← 파일시스템 저장
│   └── lock.py              ← 배타적 잠금 (윈도우 단위)
│
├── core/                    ← 비즈니스 로직 계층
│   ├── __init__.py
│   ├── orchestrator.py      ← 메인 워크플로우
│   ├── prompt.py            ← 프롬프트 빌더
│   └── response.py          ← 응답 수집/파싱
│
└── config/                  ← 설정 계층
    ├── __init__.py
    ├── loader.py            ← YAML 로딩 + 기본값
    └── defaults.py          ← 기본 설정값
```

### 3.2 의존성 흐름 (단방향)

```
  CLI ──→ Orchestrator ──→ Panel ──→ Discovery
                │              │
                │              └──→ Conversations
                │              │
                │              └──→ Input
                │
                └──→ Session Manager
                │         │
                │         └──→ Storage
                │         │
                │         └──→ Lock
                │
                └──→ Response
                │
                └──→ Config (모든 모듈이 읽음)
```

---

## 4. 각 모듈 상세 설계

### 4.1 ax/discovery.py — 앱/윈도우 탐색

**역할**: Antigravity 프로세스를 찾고, 윈도우 목록을 반환

```python
# 제공하는 기능:
find_antigravity()        → (pid, ax_app) or None
list_windows(ax_app)      → [{title, ax_ref, workspace_path}]
find_window_by_workspace(ax_app, path)  → ax_window or None
activate_window(ax_window) → bool
```

**핵심 로직**:
```
1. NSWorkspace.runningApplications() 순회
2. bundleIdentifier == "com.google.antigravity" 매칭
3. kAXWindowsAttribute → 윈도우 목록
4. kAXTitleAttribute → 윈도우 타이틀 파싱
   포맷: "{파일명} — {폴더명} — Antigravity"
   →  워크스페이스 경로 추출
```

---

### 4.2 ax/panel.py — Agent Panel 조작 (★ 핵심 모듈)

**역할**: 에디터 윈도우 내 Agent Panel의 모든 요소를 찾고 조작

```python
# 제공하는 기능:
get_panel_title(window)             → str ("Agent" | "대화 제목")
get_header_links(window)            → [ax_link_0, ax_link_1, ...]
click_new_conversation(window)      → bool
click_past_conversations(window)    → bool (오버랩 열기)
find_message_input(window)          → ax_textarea or None
find_send_button(window)            → ax_button or None
find_cancel_button(window)          → ax_button or None
get_conversation_state(window)      → "idle" | "generating" | "thinking"
```

**헤더 식별 알고리즘**:
```
1. depth=12에서 AXStaticText 탐색
2. 같은 부모의 형제 중 AXLink가 있으면 → 대화 타이틀 그룹
3. 형제 중 AXLink를 순서대로 수집:
   links[0] = [+] 새 대화
   links[1] = [⏰] Past Conversations
```

**Input Box 식별**:
```
1. AXDOMIdentifier == "antigravity.agentSidePanelInputBox" 로 직접 탐색
2. 자식에서:
   - AXButton desc="Send message" → 전송 버튼
   - AXButton desc="Cancel"       → 취소 버튼
   - AXPopUpButton "Select conversation mode..." → 모드 선택
   - AXPopUpButton "Select model..."             → 모델 선택
```

---

### 4.3 ax/conversations.py — Past Conversations 오버랩

**역할**: 오버랩에서 대화 검색, 선택, 닫기

```python
# 제공하는 기능:
search_conversation(window, query)      → [{title, time, el}]
select_conversation(window, title)      → bool
list_conversations(window)              → [{title, workspace, time, el}]
close_overlay()                         → None (Escape)
```

**검색 알고리즘**:
```
1. panel.click_past_conversations(window)  → 오버랩 열기
2. 검색 필드 찾기: AXTextField placeholder="Select a conversation"
3. AXValue 직접 쓰기로 검색어 입력 (클립보드 불필요!)
4. depth=13에서 AXPress 가능한 요소 수집 → 대화 항목
5. 자식 텍스트에서 대화 타이틀, 시간, 워크스페이스 추출
6. 배제 목록: Running in, Recent in, Other Conversations, Show, AI may make...
```

---

### 4.4 ax/input.py — 키보드/클립보드 입력

**역할**: Message Input에 안전하게 텍스트 입력

```python
# 제공하는 기능:
safe_paste(text)              → bool (클립보드 백업/복원 포함)
simulate_keypress(keycode, cmd=False, shift=False) → None
press_escape()                → None
clear_input(textarea)         → bool (Cmd+A + Delete)
```

**클립보드 보존 패턴**:
```
1. 현재 클립보드 내용 백업
2. 새 텍스트를 클립보드에 설정
3. Cmd+V 시뮬레이션
4. 잠시 대기 (0.5초)
5. 원래 클립보드 내용 복원
```

---

### 4.5 session/manager.py — 세션 관리

**역할**: 대화 세션의 생성, 조회, 연결, 이력 관리

```python
# 제공하는 기능:
create_session(workspace, title)          → session_id
find_session(workspace, title_or_id)      → Session
list_sessions(workspace)                  → [Session]
connect_session(session_id)               → Session
record_turn(session, question, response)  → None
```

**Session 데이터 모델**:
```python
Session:
  id:          str         # 고유 식별자 (uuid 또는 slug)
  title:       str         # Agent Panel 대화 타이틀
  workspace:   str         # 워크스페이스 경로
  created_at:  datetime
  updated_at:  datetime
  status:      str         # "active" | "idle" | "archived"
  turns:       int         # 질의-응답 횟수
```

---

### 4.6 session/storage.py — 파일시스템 저장

**역할**: 세션 데이터를 워크스페이스별 숨김 폴더에 저장

```
{워크스페이스 루트}/
└── .ag-sessions/
    ├── config.yaml                  ← 워크스페이스별 설정
    └── sessions/
        ├── {session-1}/
        │   ├── metadata.json        ← 세션 메타데이터
        │   └── history.jsonl        ← 대화 이력 (줄 단위 JSON)
        └── {session-2}/
            ├── metadata.json
            └── history.jsonl
```

**metadata.json 예시**:
```json
{
  "id": "analyze-architecture",
  "title": "Analyzing Antigravity Project Architecture",
  "workspace": "/Users/uhd/.../integrate_antigravity",
  "created_at": "2026-03-29T05:16:32Z",
  "updated_at": "2026-03-29T09:30:00Z",
  "status": "active",
  "turns": 15
}
```

**history.jsonl 예시** (한 줄 = 한 턴):
```json
{"turn":1,"timestamp":"...","role":"user","content":"파이썬 코드를 분석해"}
{"turn":1,"timestamp":"...","role":"assistant","summary":"분석 완료","file":"responses/001.json"}
```

---

### 4.7 session/lock.py — 배타적 잠금

**역할**: 같은 윈도우에 두 에이전트가 동시 접근 방지

```
잠금 단위: 윈도우 (워크스페이스 경로 기준)

잠금 파일: .ag-sessions/.locks/{workspace_hash}.lock
잠금 방식: fcntl.flock (LOCK_EX | LOCK_NB)
타임아웃:  30초 대기 후 실패

※ Agent Panel은 윈도우별 독립이므로,
  다른 윈도우에서는 동시 실행 가능!
```

---

### 4.8 core/orchestrator.py — 메인 워크플로우

**역할**: 전체 동작을 조율하는 메인 파이프라인

```
"ask" 명령의 전체 플로우:

  ┌──────────────────────────────────────────────────────────┐
  │  1. 앱 탐색  (discovery)                                  │
  │     Antigravity PID 찾기 → 윈도우 목록                     │
  ├──────────────────────────────────────────────────────────┤
  │  2. 윈도우 선택  (discovery)                               │
  │     --workspace 지정 시 → 해당 윈도우 찾기                  │
  │     미지정 시 → 현재 활성 윈도우                             │
  ├──────────────────────────────────────────────────────────┤
  │  3. 대화 라우팅  (panel + conversations)                   │
  │                                                          │
  │     --new 지정?                                           │
  │       → Yes: links[0] 클릭 → 새 대화 생성                  │
  │       → No:                                               │
  │                                                          │
  │     --session 지정?                                       │
  │       → Yes: 세션 매니저에서 title 가져오기                  │
  │              현재 Panel 타이틀과 비교                        │
  │              다르면 → Past Conversations에서 검색 + 선택    │
  │       → No:  현재 열린 대화 그대로 사용                      │
  ├──────────────────────────────────────────────────────────┤
  │  4. 잠금 획득  (lock)                                     │
  │     윈도우 단위 fcntl.flock                                │
  ├──────────────────────────────────────────────────────────┤
  │  5. 메시지 입력  (input)                                   │
  │     클립보드 백업 → 붙여넣기 → 클립보드 복원                  │
  ├──────────────────────────────────────────────────────────┤
  │  6. 전송  (panel)                                         │
  │     Cmd+Enter 또는 Send 버튼 AXPress                      │
  ├──────────────────────────────────────────────────────────┤
  │  7. 응답 대기  (panel + response)                          │
  │     Send 사라짐 감지 → 폴링 → Send 재출현 감지              │
  ├──────────────────────────────────────────────────────────┤
  │  8. 응답 수집  (response)                                  │
  │     .agent_response.json 파일 읽기 → 파싱                   │
  ├──────────────────────────────────────────────────────────┤
  │  9. 세션 기록  (session)                                   │
  │     history.jsonl에 현재 턴 추가                            │
  ├──────────────────────────────────────────────────────────┤
  │  10. 잠금 해제  (lock)                                     │
  │      finally에서 반드시 해제                                │
  └──────────────────────────────────────────────────────────┘
```

---

### 4.9 config/loader.py — 설정 관리

**역할**: YAML config 파일 로딩, 기본값 병합

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

# 타이밍 (초)
timing:
  app_activate_delay: 0.5
  paste_delay: 0.5
  poll_interval: 0.5
  poll_timeout: 120
  overlay_wait: 2.0

# 응답
response:
  file_name: ".agent_response.json"
  use_json_bridge: true
```

---

### 4.10 cli.py — CLI 인터페이스

**역할**: 사용자 명령을 파싱하여 orchestrator로 전달

```
ag-agent <command> [options]

Commands:
  ask <message>              질문 전송
    --new                    새 대화 생성 후 전송
    --session <id>           특정 세션에 전송
    --workspace <path>       특정 워크스페이스 지정
    --mode <planning|code>   대화 모드 설정
    --model <model_name>     모델 선택

  session list               세션 목록
  session connect <id>       이전 대화에 연결
  session show <id>          세션 이력 보기

  status                     현재 상태 표시
    - 열린 윈도우 목록
    - 각 Panel의 대화 타이틀
    - 응답 상태 (idle/generating)

  debug tree                 현재 윈도우의 AX 트리 덤프
```

---

## 5. 구현 단계 (Phase)

### Phase 1: 뼈대 (Foundation) — 모듈 분리 + 기본 동작

```
목표: 기존 ask_and_wait.py의 기능을 모듈 구조로 이전
      + 윈도우 선택 기능 추가

작업 목록:
  □ src/ 디렉토리 구조 생성 (__init__.py 등)
  □ ax/discovery.py — find_antigravity, list_windows
  □ ax/panel.py — get_panel_title, find_message_input, find_send_button
  □ ax/input.py — safe_paste, simulate_keypress
  □ core/orchestrator.py — 기본 ask 파이프라인
  □ core/response.py — 응답 파일 수집
  □ core/prompt.py — JSON Bridge 프롬프트
  □ config/defaults.py — 기본값
  □ cli.py — ask 명령만

검증: python -m src ask "안녕" 이 기존과 동일하게 동작
```

### Phase 2: 대화 라우팅 — 검색 + 전환 + 생성

```
목표: 원하는 대화를 찾아가거나 새로 만드는 기능

작업 목록:
  □ ax/panel.py — click_new_conversation, click_past_conversations
  □ ax/conversations.py — search, select, list, close
  □ core/orchestrator.py — --new, --session 옵션 연동
  □ 대화 라우팅 로직:
      현재 대화 확인 → 다르면 Past Conversations에서 검색 → 선택/전환

검증:
  - "ag-agent ask 질문 --new" → 새 대화에서 질문
  - "ag-agent ask 질문 --session analyze" → 해당 대화로 전환 후 질문
```

### Phase 3: 세션 관리 — 이력 보존 + 자동 연결

```
목표: 대화 이력을 파일로 관리하고, 다음 실행 시 자동 연결

작업 목록:
  □ session/storage.py — .ag-sessions/ 디렉토리 관리
  □ session/manager.py — CRUD + 자동 연결
  □ session/lock.py — fcntl.flock 기반 잠금
  □ config/loader.py — config.yaml 로딩
  □ cli.py — session 서브커맨드

검증:
  - "ag-agent session list" → 세션 목록 출력
  - 질문 전송 후 history.jsonl에 기록 확인
  - 두 번째 실행 시 이전 대화에 자동 연결
```

### Phase 4: 안정화 — 에러 복구 + 상태 감지

```
목표: 실 운영 수준의 안정성 확보

작업 목록:
  □ AX 요소 미발견 시 재시도 (최대 3회, 백오프)
  □ 응답 타임아웃 처리 (Cancel 버튼으로 중단 옵션)
  □ 프로세스 크래시 감지 (PID 생존 확인)
  □ 상태 머신: INIT → CONNECTING → READY → SENDING → WAITING → DONE
  □ cli.py — status, debug tree 서브커맨드

검증:
  - AX 요소가 늦게 나타나는 경우에도 정상 동작
  - 응답 생성 취소 후 재질문 가능
```

---

## 6. 기술 패턴 요약

### 6.1 AX 요소 탐색 패턴

```python
# 1. DOM ID 기반 (가장 안정적)
find_by_domid(editor, "antigravity.agentSidePanelInputBox")

# 2. Role + Description (표준)
find_by_role_desc(editor, "AXButton", "Send message")

# 3. 형제 순서 기반 (title/desc가 비어있을 때)
title_group = find_title_group(editor)   # depth=12
links = get_sibling_links(title_group)   # AXLink만 추출
links[0] = NEW_CONVERSATION
links[1] = PAST_CONVERSATIONS
```

### 6.2 동시성 모델

```
                  ┌──── 윈도우 A (워크스페이스1) ────┐
서브에이전트 A ───→│  Agent Panel A (독립)            │
                  │  잠금: workspace1.lock            │
                  └──────────────────────────────────┘

                  ┌──── 윈도우 B (워크스페이스2) ────┐
서브에이전트 B ───→│  Agent Panel B (독립)            │
                  │  잠금: workspace2.lock            │
                  └──────────────────────────────────┘

→ 서로 다른 윈도우이므로 동시 실행 안전 ✅
→ 같은 윈도우 접근 시에만 잠금으로 직렬화
```

### 6.3 의존성 (추가 설치 불필요)

```
필수 (이미 .venv_monitor에 설치됨):
  - pyobjc-framework-ApplicationServices
  - pyobjc-framework-Cocoa
  - pyobjc-framework-Quartz

추가 설치 필요:
  - pyyaml (config 파싱용)

표준 라이브러리만 사용:
  - argparse (CLI)
  - fcntl (잠금)
  - json, os, time, uuid, pathlib 등
```

---

## 7. 파일 수 및 규모 예상

| 모듈 | 파일 수 | 예상 줄 수 | 난이도 |
|:---|:---|:---|:---|
| ax/discovery | 1 | ~80 | 🟢 쉬움 |
| ax/panel | 1 | ~150 | 🟠 중간 |
| ax/conversations | 1 | ~120 | 🟠 중간 |
| ax/input | 1 | ~60 | 🟢 쉬움 |
| session/manager | 1 | ~100 | 🟢 쉬움 |
| session/storage | 1 | ~80 | 🟢 쉬움 |
| session/lock | 1 | ~40 | 🟢 쉬움 |
| core/orchestrator | 1 | ~200 | 🔴 복잡 |
| core/prompt | 1 | ~40 | 🟢 쉬움 |
| core/response | 1 | ~60 | 🟢 쉬움 |
| config/loader | 1 | ~60 | 🟢 쉬움 |
| config/defaults | 1 | ~30 | 🟢 쉬움 |
| cli | 1 | ~100 | 🟢 쉬움 |
| **합계** | **~15** | **~1,120** | — |

기존 284줄 → 약 1,120줄 (4배) — 하지만 모듈화되어 유지보수 용이

---

## 8. 리스크 및 대응

| 리스크 | 영향 | 대응 |
|:---|:---|:---|
| Antigravity UI 업데이트로 AX 구조 변경 | AX 셀렉터 깨짐 | config.yaml에 식별자 외부화 |
| 검색 필드에서 대화를 못 찾음 | 대화 전환 실패 | "Show N more..." 클릭 → 재검색 |
| 클립보드 경쟁 조건 | 다른 앱이 클립보드를 덮어쓸 수 있음 | 잠금 구간을 최소화 (paste 직후 복원) |
| 새 대화가 "Agent" 아닌 다른 타이틀로 시작 | 빈 대화 식별 실패 | Panel 타이틀 + 대화 내용 유무 이중 확인 |
