# 이벤트 기반 아키텍처 설계 — 시간 의존성 제거

> 보고일: 2026-03-29 | 기획서 보완 #2  
> 핵심 원칙: **"시간을 기다리지 않는다. 조건이 충족될 때까지 감시한다."**

---

## 1. 현재 코드의 시간 의존성 전수 조사

### ask_and_wait.py에서 발견된 모든 `time.sleep()` (10곳)

```
줄   │ 코드                         │ 의도                   │ 문제
─────┼──────────────────────────────┼────────────────────────┼──────────────────────
L128 │ time.sleep(0.05)              │ keydown↔keyup 간격     │ ⚠️ 최소한의 HW 딜레이
L234 │ time.sleep(0.5)               │ 앱 활성화 대기          │ ❌ "0.5초면 되겠지"
L241 │ time.sleep(1.0)               │ AX 초기화 대기          │ ❌ "1초면 되겠지"
L265 │ time.sleep(0.5)               │ 포커스 설정 후 안정화    │ ❌ "0.5초면 되겠지"
L268 │ time.sleep(1.0)               │ 붙여넣기 후 안정화      │ ❌ "1초면 되겠지"
L272 │ time.sleep(1.0)               │ 전송 후 안정화          │ ❌ "1초면 되겠지"
L158 │ time.sleep(0.25)              │ Send 소멸 폴링 간격     │ ⚠️ 폴링인데 횟수 제한
L169 │ time.sleep(0.5)               │ Send 재출현 폴링 간격   │ ⚠️ 폴링인데 횟수 제한
L278 │ time.sleep(0.5)               │ 응답 수집 전 안정화     │ ❌ "0.5초면 되겠지"
```

### 분류

```
❌ "N초면 되겠지" (Hope-Based Wait) — 6곳
   → 조건이 충족되었는지 확인조차 안 함
   → 느린 환경에서는 부족, 빠른 환경에서는 낭비

⚠️ 타임아웃 캡이 걸린 폴링 (Bounded Polling) — 3곳
   → 조건 감지는 이벤트적이지만, 횟수 제한(=타임아웃 변형)이 있음
   → L157: 20회 = 5초 캡
   → L168: 240회 = 120초 캡

🟢 HW 딜레이 (Hardware Timing) — 1곳
   → L128: keydown↔keyup 50ms는 물리적으로 필요한 최소 간격
   → 이것은 유지해도 됨 (이벤트가 아닌 하드웨어 프로토콜)
```

---

## 2. 이벤트 기반 대체 설계

### 원칙

```
"time.sleep(N)으로 기다린다" → 금지

"조건 X가 참이 될 때까지 감시한다" → 올바름

감시 = 최소 간격(0.01~0.05초)으로 조건 확인
     = time.sleep이 아님
     = "CPU를 양보하면서 조건이 변할 때까지 루프"
     = 타임아웃 없음 (조건이 충족될 때까지 영원히)
```

### 2.1 기본 빌딩 블록: `wait_until()`

```python
def wait_until(condition_fn, tick=0.05):
    """
    조건이 참이 될 때까지 감시.
    
    tick은 "대기 시간"이 아니라 "CPU 양보 간격".
    루프 탈출 조건은 오직 condition_fn() == True.
    타임아웃 없음.
    """
    while not condition_fn():
        time.sleep(tick)  # CPU 양보 (조건 확인 주기)
```

> `time.sleep(0.05)`은 "0.05초 기다린다"가 아니라  
> "0.05초 후에 조건을 다시 확인한다"입니다.  
> 이것은 OS 스케줄러에 CPU를 양보하는 협력적 멀티태스킹입니다.

---

### 2.2 모든 단계의 이벤트 전환표

```
┌────────────────────────────────────────────────────────────────┐
│ 단계          │ 기존 (시간)           │ 개선 (이벤트)           │
├────────────────────────────────────────────────────────────────┤
│               │                       │                         │
│ ① 앱 활성화   │ sleep(0.5)            │ wait_until(              │
│               │ "0.5초 후 활성화됐겠지" │   app.isActive           │
│               │                       │ )                        │
│               │                       │                         │
│ ② AX 초기화   │ sleep(1.0)            │ wait_until(              │
│               │ "1초면 AX 되겠지"      │   ax_windows_exist       │
│               │                       │ )                        │
│               │                       │                         │
│ ③ 포커스      │ sleep(0.5)            │ wait_until(              │
│               │ "0.5초면 포커스됐겠지"  │   input.focused == True  │
│               │                       │ )                        │
│               │                       │                         │
│ ④ 붙여넣기    │ sleep(1.0)            │ wait_until(              │
│               │ "1초면 붙여졌겠지"      │   input.value != ""      │
│               │                       │ )                        │
│               │                       │                         │
│ ⑤ 전송       │ sleep(1.0)            │ wait_until(              │
│               │ "1초면 전송됐겠지"      │   send_btn NOT found     │
│               │                       │ )                        │
│               │                       │ = Send 버튼 소멸 감지     │
│               │                       │                         │
│ ⑥ 생성 시작   │ for _ in range(20)    │ wait_until(              │
│               │ "최대 5초 기다려"       │   send_btn NOT found     │
│               │                       │ )                        │
│               │                       │ 타임아웃 없음 ★           │
│               │                       │                         │
│ ⑦ 생성 완료   │ for _ in range(240)   │ wait_until(              │
│               │ "최대 120초 기다려"     │   send_btn FOUND         │
│               │                       │ )                        │
│               │                       │ 타임아웃 없음 ★           │
│               │                       │                         │
│ ⑧ 응답 수집   │ sleep(0.5)            │ wait_until(              │
│               │ "0.5초 후 파일 생겼겠지"│   response_file_exists   │
│               │                       │ )                        │
│               │                       │                         │
│ ⑨ 대화 전환   │ sleep(2.0)            │ wait_until(              │
│               │ (사전 조사 시 사용)     │   panel_title_changed    │
│               │                       │ )                        │
│               │                       │                         │
│ ⑩ 오버랩 열기 │ sleep(2.0)            │ wait_until(              │
│               │ (사전 조사 시 사용)     │   search_field_visible   │
│               │                       │ )                        │
│               │                       │                         │
│ ⑪ 검색 필터링 │ sleep(1.0)            │ wait_until(              │
│               │ (사전 조사 시 사용)     │   conv_count_changed     │
│               │                       │ )                        │
└────────────────────────────────────────────────────────────────┘
```

### 2.3 상태 전이 다이어그램 (응답 대기)

```
기존: "120초 타임아웃" ← 이것은 타이머지, 이벤트가 아님

개선: 상태 전이 감지

  Send 있음 ──→ Send 사라짐 ──→ Cancel 나타남 ──→ Send 다시 나타남
  (idle)        (전송됨)         (생성 중)          (완료!)
     │              │                │                  │
     ▼              ▼                ▼                  ▼
  입력 가능     전송 확인됨      진행 상태 로깅       응답 수집 가능

  각 전이 = wait_until(조건) — 타임아웃 없음
```

```python
def wait_for_generation(window):
    """이벤트 기반 응답 대기 — 상태 전이 감시"""
    
    # 전이 1: Send → 사라짐 (전송 확인)
    wait_until(lambda: not find_send_button(window))
    
    # 전이 2: Cancel 나타남 (생성 시작 확인, 선택적)
    # → Cancel이 나타나면 생성이 시작된 것
    # → 나타나지 않고 Send가 바로 돌아올 수도 있음 (매우 빠른 응답)
    
    # 전이 3: Send → 다시 나타남 (완료)
    wait_until(lambda: find_send_button(window) is not None)
```

---

## 3. 클립보드 대기 큐 설계

### 3.1 기존 "잠금" vs 새 "큐" 비교

```
❌ 잠금 (Lock) — 기존 제안
   ┌─────────────────────┐
   │ flock 시도           │ ← 먼저 온 놈이 선점
   │ 실패하면 대기         │ ← OS가 적당히 깨워줌
   │ 성공하면 실행         │
   │ 해제                 │
   └─────────────────────┘
   문제: 순서 보장 없음, 기아(starvation) 가능

✅ 큐 (Queue) — 명시적 순서 보장
   ┌─────────────────────┐
   │ 1. 요청 등록 (ticket) │ ← 번호표 발급
   │ 2. 내 순서 대기       │ ← 앞 사람이 끝날 때까지
   │ 3. 내 차례 실행       │ ← 번호표 순서대로
   │ 4. 완료 신호          │ ← 다음 사람에게 알림
   └─────────────────────┘
   보장: FIFO 순서, 기아 없음
```

### 3.2 큐 구현: 파일 기반 티켓 시스템

```
/tmp/.ag-clipboard-queue/
├── tickets/
│   ├── 0001_pid12345          ← 에이전트 A의 티켓 (생성 시간순 번호)
│   ├── 0002_pid67890          ← 에이전트 B의 티켓
│   └── 0003_pid11111          ← 에이전트 C의 티켓
├── serving                    ← 현재 서비스 중인 티켓 번호 (1줄 텍스트)
└── processing.lock            ← 실행 중 잠금 (flock)
```

### 3.3 동작 시퀀스

```
에이전트 A                   에이전트 B                   에이전트 C
──────────                  ──────────                  ──────────

1. 티켓 발급               
   0001_pidA 생성            
   
2. 내 차례? 확인             1. 티켓 발급
   tickets/ 최소 = 0001         0002_pidB 생성
   내 번호 = 0001
   → 내 차례! ✅              2. 내 차례? 확인
                                최소 = 0001
3. flock 획득                    내 번호 = 0002              1. 티켓 발급
                                → 대기 ⏳                      0003_pidC 생성
4. 클립보드 백업             
5. 텍스트 설정                                              2. 내 차례? 확인
6. Cmd+V                                                       최소 = 0001
7. 입력 확인 (이벤트!)                                          → 대기 ⏳
8. 클립보드 복원             
9. 티켓 삭제 (0001 제거)     
10. flock 해제               

                              3. 내 차례? 확인  
                                 최소 = 0002
                                 내 번호 = 0002
                                 → 내 차례! ✅
                                 
                              4~10. (동일 과정)
                              
                                                           3. 내 차례? 확인
                                                              최소 = 0003
                                                              → 내 차례! ✅
```

### 3.4 "내 차례?" 감시 — 이벤트 기반

```python
def wait_for_my_turn(my_ticket_number):
    """
    내 티켓이 큐의 맨 앞이 될 때까지 감시.
    감시 방법: tickets/ 디렉토리의 파일 목록이 변할 때 확인.
    """
    def is_my_turn():
        tickets = sorted(os.listdir(TICKETS_DIR))
        if not tickets:
            return False
        front = tickets[0]  # 가장 작은 번호 = 맨 앞
        return front.startswith(f"{my_ticket_number:04d}_")
    
    wait_until(is_my_turn)
```

> 이벤트 포인트: 앞 에이전트가 티켓을 삭제하면,  
> `is_my_turn()`이 True로 바뀜 → 조건 충족 → 루프 탈출

### 3.5 전체 paste 함수

```python
class ClipboardQueue:
    QUEUE_DIR = "/tmp/.ag-clipboard-queue"
    TICKETS_DIR = f"{QUEUE_DIR}/tickets"
    LOCK_FILE = f"{QUEUE_DIR}/processing.lock"
    
    def paste(self, text, message_input):
        """
        클립보드 큐에 등록 → 내 차례 대기 → 붙여넣기 → 완료
        """
        # 1. 티켓 발급
        ticket = self._take_ticket()
        
        # 2. 내 차례 대기 (이벤트 감시)
        wait_until(lambda: self._is_my_turn(ticket))
        
        # 3. 실행 잠금 획득 (혹시 모를 경쟁 방지)
        with open(self.LOCK_FILE, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            
            # 4. 클립보드 백업
            backup = get_clipboard_content()
            
            # 5. 붙여넣기
            set_clipboard(text)
            simulate_cmd_v()
            
            # 6. 입력 확인 (이벤트!)
            wait_until(lambda: get_ax_value(message_input) != "")
            
            # 7. 클립보드 복원
            restore_clipboard(backup)
        
        # 8. 티켓 삭제 (다음 에이전트에게 차례 넘김)
        self._destroy_ticket(ticket)
```

---

## 4. 전체 이벤트 카탈로그

프로그램의 모든 단계에서 사용하는 이벤트(=감시 가능한 조건):

```
┌────┬──────────────────────────┬──────────────────────────────────┐
│ #  │ 이벤트 이름               │ 감시 조건 (condition_fn)          │
├────┼──────────────────────────┼──────────────────────────────────┤
│ E1 │ APP_ACTIVE               │ app.isActive() == True           │
│ E2 │ AX_READY                 │ AXUIElement.windows != None      │
│ E3 │ WINDOW_FOUND             │ window with workspace in title   │
│ E4 │ PANEL_TITLE_READABLE     │ depth=12 AXStaticText + siblings │
│ E5 │ INPUT_FOUND              │ AXTextArea desc="Message input"  │
│ E6 │ INPUT_FOCUSED            │ input.focused == True            │
│ E7 │ TEXT_PASTED              │ input.value != ""                │
│ E8 │ SEND_DISAPPEARED         │ AXButton "Send message" 없음     │
│ E9 │ CANCEL_APPEARED          │ AXButton desc="Cancel" 나타남     │
│ E10│ SEND_REAPPEARED          │ AXButton "Send message" 나타남    │
│ E11│ RESPONSE_FILE_CREATED    │ os.path.exists(response_path)    │
│ E12│ OVERLAY_OPENED           │ AXTextField placeholder=... 존재  │
│ E13│ SEARCH_FILTERED          │ 대화 항목 수 변화                  │
│ E14│ CONVERSATION_SWITCHED    │ panel_title == target_title      │
│ E15│ OVERLAY_CLOSED           │ AXTextField placeholder=... 없음  │
│ E16│ CLIPBOARD_TURN           │ 내 티켓이 큐 최선두                │
│ E17│ NEW_CHAT_CREATED         │ panel_title == "Agent"            │
└────┴──────────────────────────┴──────────────────────────────────┘
```

---

## 5. 전체 ask 플로우: 이벤트 체인

```
ag-agent ask "질문" --session my-task

───────── 이벤트 체인 ─────────

[E1] APP_ACTIVE
  └→ [E2] AX_READY
       └→ [E3] WINDOW_FOUND
            └→ [E4] PANEL_TITLE_READABLE
                 │
                 ├─ title == session.panel_title? → Yes → 바로 진행
                 └─ No →
                      [오버랩 열기]
                      └→ [E12] OVERLAY_OPENED
                           └→ [검색어 입력]
                                └→ [E13] SEARCH_FILTERED
                                     └→ [대화 클릭]
                                          └→ [E14] CONVERSATION_SWITCHED
                                               └→ [E15] OVERLAY_CLOSED (자동)

[E5] INPUT_FOUND
  └→ [E6] INPUT_FOCUSED
       └→ [E16] CLIPBOARD_TURN (큐 대기)
            └→ [붙여넣기]
                 └→ [E7] TEXT_PASTED
                      └→ [클립보드 복원 + 큐 해제]
                           └→ [Cmd+Enter]
                                └→ [E8] SEND_DISAPPEARED (전송 확인)
                                     └→ [E9] CANCEL_APPEARED (생성 시작, 선택적)
                                          └→ [E10] SEND_REAPPEARED (완료!)
                                               └→ [E11] RESPONSE_FILE_CREATED
                                                    └→ [파일 읽기 + 세션 기록]
```

---

## 6. 유일하게 남는 `time.sleep()` 사용처

```python
def wait_until(condition_fn, tick=0.05):
    while not condition_fn():
        time.sleep(tick)  # ← 이것만 남음
```

이 `time.sleep(0.05)`은:
- ❌ "0.05초 기다리고 끝" 이 아님
- ✅ "0.05초간 CPU를 양보하고 다시 조건 확인" 임
- OS 스케줄러에 대한 협력적 양보 (cooperative yield)
- 이것 없이 while True를 돌면 CPU 100% 점유 → 시스템 전체 성능 저하
- 50ms tick = 초당 20회 확인 → 사람 반응 속도(200ms)보다 4배 빠름

### 유일한 예외: keydown↔keyup 간격

```python
CGEventPost(kCGHIDEventTap, event_down)
time.sleep(0.01)  # HW 프로토콜: 키 누름→뗌 최소 간격
CGEventPost(kCGHIDEventTap, event_up)
```

이것은 이벤트로 대체할 수 없는 **물리적 제약**입니다.  
키보드 HID 프로토콜에서 key-down과 key-up 사이에  
최소 간격이 없으면 OS가 이벤트를 무시합니다.

---

## 7. 기획서 수정 사항 요약

| 항목 | 기존 기획서 | 수정 |
|:---|:---|:---|
| **타이밍 설정** | config.yaml에 `timing:` 섹션 | ❌ **삭제** — 타이밍 설정 자체가 불필요 |
| **응답 대기** | 120초 타임아웃 | ❌ **삭제** — `wait_until(send_reappeared)` 무한 대기 |
| **클립보드 보호** | flock 직접 잠금 | → **ClipboardQueue** 티켓 큐 |
| **sleep 용도** | "N초 기다리기" | → `wait_until(조건)` 내부의 CPU 양보 tick만 |
| **상태 감지** | Send 버튼만 감시 | → Send + Cancel + "Running" 3중 상태 전이 |
| **config.yaml** | `timing:` 섹션 포함 | `timing:` 섹션 완전 제거 |
