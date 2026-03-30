# 구현 기획서 보완 보고 — 3가지 누락/우려 대응

> 보고일: 2026-03-29 | 구현 기획서 v1.0 보완

---

## 질문 1: 워크스페이스에 저장되는 세션 데이터 상세 설계

기획서에서 `session/storage.py`와 `.ag-sessions/` 디렉토리를 언급했지만, 
**무엇이 저장되고, 어떤 데이터로 대화를 식별하는지** 구체적이지 않았습니다.

### 1.1 저장 구조

```
{워크스페이스 루트}/
└── .ag-sessions/
    ├── config.yaml                           ← 워크스페이스 설정
    ├── active_session                        ← 마지막 사용한 세션 ID (1줄 텍스트)
    └── sessions/
        └── {session-id}/
            ├── metadata.json                 ← 세션 식별 정보
            └── history.jsonl                 ← 대화 이력 (줄 단위)
```

### 1.2 metadata.json — 세션 식별 파일

```json
{
  "id": "analyze-arch-20260329",
  "title": "Analyzing Antigravity Project Architecture",
  "panel_title": "Analyzing Antigravity Project Architecture",
  "workspace": "/Users/uhd/.../integrate_antigravity",
  "window_title_pattern": "integrate_antigravity",
  "created_at": "2026-03-29T05:16:32Z",
  "updated_at": "2026-03-29T09:30:00Z",
  "status": "active",
  "total_turns": 15,
  "tags": ["architecture", "analysis"],
  "description": "프로젝트 아키텍처 분석 및 모듈 분리 계획"
}
```

각 필드의 역할:

| 필드 | 용도 | 어디서 쓰이나 |
|:---|:---|:---|
| `id` | 세션 고유 식별자 (CLI에서 `--session` 인자로 사용) | CLI, 세션 매니저 |
| `title` | 사람이 읽는 세션 이름 | `session list` 출력 |
| `panel_title` | Agent Panel에 표시되는 대화 타이틀 | **대화 찾기/전환에 사용** ★ |
| `workspace` | 워크스페이스 절대 경로 | 윈도우 매칭 |
| `window_title_pattern` | AX 윈도우 타이틀에서 매칭할 패턴 | 윈도우 탐색 |
| `status` | `active` / `idle` / `archived` | 목록 필터링 |
| `tags` | 검색/분류용 태그 | 서브에이전트가 세션을 찾을 때 |
| `description` | 세션 설명 | 서브에이전트가 판단할 때 참고 |

### 1.3 history.jsonl — 대화 이력

```jsonl
{"turn":1,"ts":"2026-03-29T05:16:32Z","role":"user","content":"프로젝트 아키텍처를 분석해","prompt_length":1234}
{"turn":1,"ts":"2026-03-29T05:17:45Z","role":"assistant","summary":"5개 모듈 구조 제안","response_file":"responses/001.json","duration_sec":73}
{"turn":2,"ts":"2026-03-29T05:20:00Z","role":"user","content":"세션 관리 기능도 추가해","prompt_length":890}
{"turn":2,"ts":"2026-03-29T05:21:30Z","role":"assistant","summary":"세션 매니저 설계 완료","response_file":"responses/002.json","duration_sec":90}
```

각 턴마다:
- `turn`: 턴 번호 (질문+응답 = 같은 번호)
- `role`: `user` 또는 `assistant`
- `content`: user 턴은 원문, assistant 턴은 요약
- `response_file`: 전체 응답이 담긴 JSON 파일 경로 (선택적)
- `duration_sec`: 응답 생성에 걸린 시간

### 1.4 대화 찾기 알고리즘

```
서브에이전트가 "--session analyze-arch"로 실행될 때:

1. .ag-sessions/sessions/ 에서 metadata.json 검색
   → id가 "analyze-arch"를 포함하는 세션 찾기

2. metadata.json에서 panel_title 추출
   → "Analyzing Antigravity Project Architecture"

3. 현재 Agent Panel 타이틀 확인
   → 같으면 → 바로 질문 전송
   → 다르면 → Past Conversations 열기

4. Past Conversations에서 검색
   → 검색 필드에 panel_title 입력 (AXValue 직접 쓰기)
   → 결과에서 타이틀 매칭 → 클릭하여 전환

5. 전환 후 타이틀 재확인 → 매칭되면 질문 전송
```

### 1.5 active_session — 자동 복귀

```
# 마지막으로 사용한 세션 ID를 기록
# 다음 실행 시 --session 미지정이면 이 세션에 자동 연결
echo "analyze-arch-20260329" > .ag-sessions/active_session
```

---

## 질문 2: ask_and_wait.py의 상호작용 방식 벤치마킹

### 2.1 현재 상호작용 패턴 (JSON Bridge)

```
┌─────────────────────────────────────────────────────────────┐
│ ask_and_wait.py의 핵심 아이디어: "JSON Bridge"               │
│                                                             │
│ 문제: Agent의 응답을 AX로 읽으면 마크다운이 깨진다              │
│ 해법: Agent에게 "응답을 파일에 써라"고 지시한다                 │
│                                                             │
│  사용자 질문 ──→ 시스템 인스트럭션 추가 ──→ Agent에 전송        │
│                   │                                         │
│                   ▼                                         │
│  "너의 응답을 .agent_response.json 파일에 써.                 │
│   채팅에는 'Done'만 출력해."                                  │
│                   │                                         │
│                   ▼                                         │
│  Agent가 파일 생성 ──→ 스크립트가 파일 읽기 ──→ 깨끗한 응답    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 현재 코드의 구체적 플로우

```
build_prompt(user_input):
  ┌─────────────────────────────────────────────────────────┐
  │ 원래 질문                                                │
  │ +                                                       │
  │ [SYSTEM INSTRUCTION]                                    │
  │  - 응답을 .agent_response.json에 쓸 것                   │
  │  - JSON 스키마: {thought, markdown_answer, actions, images} │
  │  - 채팅에는 'Done'만 출력                                 │
  └─────────────────────────────────────────────────────────┘
                       ↓
wait_for_generation(target_window):
  ┌─────────────────────────────────────────────────────────┐
  │ Phase 1: Send 버튼 소멸 감지 (최대 5초)                   │
  │   → Send가 사라지면 = 생성 시작                           │
  │                                                         │
  │ Phase 2: Send 버튼 재출현 감지 (최대 120초)                │
  │   → Send가 다시 나타나면 = 생성 완료                       │
  │   → 0.5초 간격 폴링, "..." 진행 표시                      │
  └─────────────────────────────────────────────────────────┘
                       ↓
collect_response(target_window):
  ┌─────────────────────────────────────────────────────────┐
  │ .agent_response.json 파일 존재?                          │
  │   → Yes: JSON 파싱 → thought, markdown_answer 등 출력    │
  │          → 파일 삭제 (os.remove)                         │
  │   → No:  AX tree에서 텍스트 추출 (폴백)                   │
  │          → extract_all_text() 마지막 10줄                │
  └─────────────────────────────────────────────────────────┘
```

### 2.3 이 패턴의 장점과 한계

| 항목 | 장점 | 한계 |
|:---|:---|:---|
| **JSON Bridge** | 마크다운이 깨지지 않음 | Agent가 시스템 인스트럭션을 무시하면 실패 |
| | 구조화된 데이터 수집 | 파일 경로가 CWD 기준 (세션 격리 안됨) |
| | thought/actions 분리 | Agent가 파일 대신 채팅에 JSON을 쓰면 깨짐 |
| **Send 버튼 감지** | 구현이 단순 | 최대 120초 타임아웃 (고정) |
| | AX 폴링만으로 동작 | Cancel 가능 여부 무시 |
| **AX 텍스트 폴백** | Bridge 실패 시 최소 복구 | 마크다운이 깨진 상태로 출력 |

### 2.4 업그레이드에서 반영할 개선

```
1. 응답 파일 경로를 세션별 절대 경로로 변경
   기존: CWD/.agent_response.json
   개선: {workspace}/.ag-sessions/sessions/{session-id}/responses/{turn}.json

2. 프롬프트에 세션 컨텍스트 포함
   기존: 질문 + 시스템 인스트럭션
   개선: 질문 + 시스템 인스트럭션 + (선택적)이전 대화 요약

3. 타임아웃을 config에서 설정 가능하게
   기존: 하드코딩 120초
   개선: config.yaml의 timing.poll_timeout

4. Cancel 감지 추가
   기존: Send 버튼만 감시
   개선: Send + Cancel + "Running" 텍스트 3중 감시

5. 응답 파일을 삭제하지 않고 보존 (이력용)
   기존: os.remove(RESPONSE_FILE)
   개선: sessions/{id}/responses/{turn}.json에 이동 보관
```

---

## 질문 3: 클립보드 경쟁 문제 — 근본적 해결 분석

### 3.1 문제 상황

```
서브에이전트 A (윈도우1)          서브에이전트 B (윈도우2)
─────────────────────          ─────────────────────
1. 클립보드 백업                  
2. "질문A"를 클립보드에 설정       
                                1. 클립보드 백업       ← A의 "질문A"를 백업?!
3. Cmd+V (A가 붙여넣기)          
                                2. "질문B"를 클립보드에 설정
4. 클립보드 복원                  
                                3. Cmd+V (B도 붙여넣기)  ← 뭐가 붙여넣어질지 불확실
                                4. 클립보드 복원
```

**macOS 클립보드는 시스템 전역 공유 자원**입니다. 
서브에이전트 A가 클립보드에 "질문A"를 넣는 순간, 
서브에이전트 B가 백업하면 "질문A"가 B의 백업이 됩니다.

### 3.2 대안 분석

| 대안 | 가능 여부 | 설명 |
|:---|:---|:---|
| **① AXValue 직접 쓰기** | ❌ 불가 | Electron AXTextArea가 무시함 (조사 3에서 확인) |
| **② CGEventKeyboardSetUnicodeString** | ❌ 불가 | Electron이 유니코드 이벤트 무시 (이번 테스트 확인) |
| **③ 클립보드 뮤텍스** | ⚠️ 가능하지만 직렬화 | 파일 기반 뮤텍스로 한 번에 하나만 붙여넣기 |
| **④ xdotool/xclip 대안** | ❌ macOS 없음 | Linux 전용 |
| **⑤ AppleScript 직접 실행** | ❌ 불가 | Electron 앱에 직접 텍스트 주입 API 없음 |

### 3.3 유일한 현실적 해법: 클립보드 직렬화 (Clipboard Semaphore)

```
클립보드는 시스템 전역이므로, 
"클립보드를 사용하는 순간"만 배타적으로 잠그고 즉시 해제합니다.

```

#### 동작 방식

```
┌──────────────────────────────────────────────────────────────┐
│ 잠금 파일: /tmp/.ag-clipboard.lock                           │
│ 잠금 방식: fcntl.flock(LOCK_EX)                              │
│ 잠금 범위: 클립보드 설정 → 붙여넣기 → 클립보드 복원 (최소 구간)  │
└──────────────────────────────────────────────────────────────┘

서브에이전트 A                     서브에이전트 B
───────────────                   ───────────────
🔒 flock 획득                      
  ├ 클립보드 백업                   🔒 flock 시도 → ⏳ 대기
  ├ "질문A" 설정                    
  ├ Cmd+V                         
  ├ sleep(0.5)                    
  ├ 클립보드 복원                   
🔓 flock 해제                      
                                   🔒 flock 획득
                                     ├ 클립보드 백업
                                     ├ "질문B" 설정
                                     ├ Cmd+V
                                     ├ sleep(0.5)
                                     ├ 클립보드 복원
                                   🔓 flock 해제
```

#### 잠금 시간 분석

```
잠금 구간:
  - 클립보드 백업:     ~1ms
  - 텍스트 설정:       ~1ms
  - Cmd+V:            ~50ms
  - 안정화 대기:       ~500ms
  - 클립보드 복원:     ~1ms
  ─────────────────────────
  합계:               ~550ms

→ 잠금 시간이 0.5초 정도로 매우 짧음
→ 다른 에이전트가 기다리는 시간도 최대 0.5초
→ 실질적 사용자 체감 영향 없음
```

#### 핵심: 잠금 범위를 최소화

```
❌ 잘못된 방식: 전체 ask 동작을 잠금 (수십 초~수 분)
    flock → 입력 → 전송 → 응답 대기(120초) → 수집 → unlock

✅ 올바른 방식: 클립보드 사용 구간만 잠금 (0.5초)
    입력 준비 → flock → paste → unlock → 전송 → 응답 대기(120초) → 수집
```

### 3.4 사용자가 수동 복사/붙여넣기 할 때

```
서브에이전트가 paste 중 (0.5초 잠금)일 때
사용자가 Cmd+C → Cmd+V를 하면?

→ 서브에이전트가 원래 클립보드를 복원하므로
  사용자의 Cmd+C 내용이 사라졌다가 0.5초 후 복구됨
→ 실질적으로 거의 감지 불가 (0.5초 미만)
→ 서브에이전트 실행 중이 아닌 시간에는 아무 영향 없음
```

### 3.5 미래 개선 가능성

```
현재:  클립보드 직렬화 (0.5초 잠금) — 실용적이고 안정적

미래:  Antigravity에 API가 추가되면
       - Extension API: webview.postMessage() 같은 인터페이스
       - LSP 확장: 텍스트 주입 프로토콜
       - CLI 지원: antigravity --send-message "텍스트"
       → 클립보드 완전히 우회 가능

       또는 InputMethodKit (IMK) 기반 가상 입력기
       → 시스템 레벨에서 직접 텍스트 주입
       → 매우 복잡하지만 근본적 해결
```

---

## 종합: 기획서 v1.0 보완 사항

| # | 보완 항목 | 내용 |
|:---|:---|:---|
| 1 | **세션 데이터 상세** | metadata.json 10개 필드 + history.jsonl 스키마 + active_session |
| 2 | **JSON Bridge 벤치마킹** | 현재 3단계 패턴 분석 + 5개 개선점 도출 |
| 3 | **클립보드 경쟁 해결** | Clipboard Semaphore (0.5초 flock) — 성능 무영향 |

### 기획서에 추가/변경할 부분

- `session/storage.py`: metadata.json 필드를 위 스키마대로 확정
- `ax/input.py`: `safe_paste()`에 **Clipboard Semaphore** 내장
  - 잠금 파일: `/tmp/.ag-clipboard.lock`
  - 잠금 범위: 클립보드 설정 → paste → 복원 (최소)
- `core/prompt.py`: 응답 파일 경로를 `{session_dir}/responses/{turn}.json`으로
- `core/response.py`: 응답 파일 삭제 대신 세션 디렉토리에 보존
