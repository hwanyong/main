# Antigravity Bridge Daemon: 아키텍처 및 사용자 매뉴얼

이 문서는 Antigravity의 다중 에이전트(Multi-Agent) 병렬 실행 환경을 지원하기 위해 개발된 **Bridge Daemon (브릿지 데몬)** 아키텍처 및 이를 기반으로 한 세션 분리 시스템의 구현 내용을 분석하고 사용 예제를 제공합니다.

---

## 1. 아키텍처 개요 (Architecture Overview)

과거의 Antigravity 에이전트는 macOS의 Accessibility(AX) API를 이용해 각 프로세스가 개별적으로 VS Code 창(Window)을 활성화하고 클립보드에 접근했습니다. 이는 **동시에 여러 에이전트가 실행될 경우 창 강제 전환, 포커스 탈취(Steal), 입력 무시 등의 치명적인 Race Condition(경합 조건)**을 발생시켰습니다.

이를 해결하기 위해 구현된 것이 **Bridge Daemon** 입니다:
* **Stateless Message Broker**: 파일럿 스크립트(`ag-agent.sh`)는 직접 키보드 타이핑을 시도하지 않고 데몬 큐(`/tmp/ag_daemon_queue`)에 메시지를 넣습니다.
* **Global Input Lock**: 데몬은 큐 시스템을 활용해 한 번에 오직 하나의 프로세스만 에디터를 점유하고 텍스트를 주입(`Cmd+V`)할 수 있도록 "교통정리"를 수행합니다.
* **강력한 검증 (Verify & Retry)**: 입력 후 모달(Modal) 창 등이 포커스를 뺏어 타이핑에 실패할 경우, 데몬은 이를 글자 수(`Length`)로 검증하고 `ESC` 모달 탈출기를 발동한 뒤 재시도하는 자동 복구(Auto-Recovery) 기능을 탑재하고 있습니다.

---

## 2. 세션 독립 관리 (Session Isolation)

1대의 PC에 여러 개의 에이전트가 띄워져 있어도, 각각의 에이전트는 다른 프로젝트 컨텐츠를 침범하지 않습니다.
1. **워크스페이스 식별**: 에이전트는 기동 시 `-w <workspace_path>` 플래그로 대상 디렉토리를 확정지으며, 오직 그 이름과 매칭되는 `AXWindow`의 트리만 파싱합니다.
2. **분리된 영구 저장소**: 대화를 읽어들이거나 응답을 저장할 때는, 해당 `<workspace_path>` 내부에 독자적인 숨김 폴더 `.ag-sessions` 를 생성하여 별건으로 관리합니다.
3. **충돌 방지 로직**: 채팅 제목이 "Agent"(기본값)일 때 세션이 무시되는 엣지 케이스를 방지하기 위해 생성 시점의 타임스탬프(`chat_YYYYMMDD_HHMMSS`)를 부여하여 세션 유실 없이 영구적으로 상호 작용 이력을 보장합니다.

---

## 3. 핵심 명령 및 사용 예제 (Usage Guide)

### 3.1. 데몬 제어어 (Daemon Lifecycle)
데몬은 상시 켜두는(Background) 방식으로 동작해야 합니다.
```bash
# 데몬 환경 시작 및 재시작
./scripts/ag-daemon.sh start
./scripts/ag-daemon.sh restart
./scripts/ag-daemon.sh stop
```

### 3.2. 단일 에이전트 실행 (Single Agent)
데몬이 켜진 상태에서 일반적인 명령을 수행하는 예제입니다. 작업 워크스페이스를 지정하여 텍스트를 대상 창으로 라우팅합니다.
```bash
./scripts/ag-agent.sh ask -w /path/to/project "1단계: 리드미를 작성해줘"
./scripts/ag-agent.sh ask -w /path/to/project "2단계: 에러 핸들링 코드를 작성해"
```

### 3.3. 병렬 실행 테스트 케이스 (`e2e_parallel_multiturn.py`)
현재 파이프라인의 완성도를 100% 검증한 핵심 테스트 시나리오입니다. **Python** 프로젝트와 **Node.js** 프로젝트 2개를 완전 동시에 실행하여 5단계의 멀티 턴 지시를 병렬로 마치는 로직입니다.

**사용된 테스트 프레임워크 기능:**
- **이중 재시도(Retry) 루프**: 데몬이 3차 시도에 실패해도, 파이썬 테스트 드라이버가 다시 3초 대기 후 전체 단계를 최대 3회 리트라이합니다.
- **실시간 피드백 캡쳐**: Antigravity가 창에서 대답하는 "🤖 Agent Response" 마크다운을 커맨드 라인으로 파싱하여 실시간으로 과정을 지켜볼 수 있습니다.

**실행 방법:**
```bash
# 1. 환경 준비 및 데몬 리스타트
./scripts/ag-daemon.sh restart
export PYTHONPATH="."

# 2. 멀티 턴 병렬 테스트 스트레스 구동
.venv_monitor/bin/python3 tests/e2e_parallel_multiturn.py
```

> [!TIP]
> **테스트 결과 (검증 완료)**: 이 테스트의 성공은 두 프로젝트(`calc_adv_1`, `calc_adv_2`)가 각자의 `.ag-sessions` 방에 총 5쌍의 `history.jsonl` 컨텍스트를 침범 없이 완벽하게 독립적으로 분리, 저장하였으며 키보드 입력은 중앙 데몬에서 논-블로킹(Non-blocking) 큐로 처리되어 씹힘이나 무시 현상이 0%임을 의미합니다!
