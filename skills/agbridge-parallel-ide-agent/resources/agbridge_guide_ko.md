# Agbridge 데몬 제어 가이드 (Antigravity Bridge)

본 문서는 **Antigravity Bridge Daemon (`agbridge`)**을 백그라운드에서 제어하고 병렬 워크플로우를 실행하는 방법을 안내합니다. 데몬 및 메시지 큐 시스템을 활용하여 개발 중단 없이 읽기 전용 코드 분석이나 자동화 작업을 안전하게 병렬로 지시할 수 있습니다.

## ⚠️ 핵심 제약 사항 (Constraints)
- **읽기 전용 (Read-Only)**: Analyzer는 절대로 프로젝트 소스 코드를 편집, 생성, 삭제해서는 안 됩니다.
- **웹 검색 의존성**: 최신 라이브러리, 의존성 업데이트 내역, 베스트 프랙티스 등은 반드시 웹 검색(Web Context Discovery)을 통해 보완 분석해야 합니다.

---

## 🚀 `agbridge` 명령어 활용 방법

`agbridge` CLI를 사용하면 현재 워크스페이스의 에이전트에게 백그라운드에서 분석 명령을 내릴 수 있습니다.

### 1. 분석 요청하기 (`ask`)
가장 기본이 되는 명령어로, 자연어를 통해 분석 범위를 에이전트에게 전송합니다.

- **기본 분석 요청**
  ```bash
  agbridge ask "현재 코드베이스의 아키텍처와 주요 의존성을 읽어보고 분석해 줘. 코드는 수정하지 마."
  ```
- **새로운 분석 세션 시작** (`--new` 플래그)
  이전 대화 맥락과 분리하여 독립적인 보안 취약점 분석 등을 진행할 때 사용합니다.
  ```bash
  agbridge ask --new "package.json과 보안 관련 설정을 분석해서 취약점 리포트를 작성해 줘."
  ```
- **특정 세션(대화방)에 이어서 요청** (`--session` / `-s`)
  ```bash
  agbridge ask --session <session_id> "아까 분석했던 데이터베이스 레이어에 대해서 더 깊이 있게 설명해 줘."
  ```
- **특정 워크스페이스 타겟팅** (`--workspace` / `-w`)
  현재 폴더가 아니더라도 백그라운드에 띄워진 다른 VS Code 창의 에이전트에게 분석을 지시합니다.
  ```bash
  agbridge ask --workspace /path/to/project "이 프로젝트의 라우팅 흐름을 파악해 줘."
  ```
- **대기열 무시 (직접 타이핑)** (`--no-queue` 플래그)
  메시지 큐 대기 시간 없이 즉시 챗 패널에 입력합니다 (단일 에이전트 환경 전용).
  ```bash
  agbridge ask --no-queue "README.md 파일을 읽고 프로젝트 요약을 출력해."
  ```

### 2. 분석 세션 관리 (`session`)
이전에 진행했던 분석 세션들을 조회하거나 해당 컨텍스트로 복귀합니다.

- **전체 세션 목록 요약 조회**
  ```bash
  agbridge session list
  ```
- **특정 세션 컨텍스트 활성화하기**
  다음번 `ask` 명령 시 연결된 세션에서 이어서 대화하도록 설정합니다.
  ```bash
  agbridge session connect <session_id>
  ```
- **세션의 전체 분석 결과(History) 덤프 출력**
  ```bash
  agbridge session show <session_id>
  ```

### 3. 백그라운드 상태 및 런타임 모니터링 (`status` & `info`)
복잡한 분석을 요청하기 전, 데몬 상태를 점검합니다.

- **연결 상태(Status) 확인**
  ```bash
  agbridge status
  # 특정 경로: agbridge status --workspace /path/to/project
  ```
- **AI 레지스트리 (캐시) 조회**
  현재 에이전트의 워크플로우 종류와 캐싱된 모델 정보를 봅니다.
  ```bash
  agbridge info
  # UI 상태 갱신 필요 시: agbridge info --refresh
  ```

### 4. 로우레벨 디버깅 (`debug`)
에이전트가 화면(DOM) 상태를 제대로 읽지 못하여 분석에 차질이 생길 경우, macOS Accessibility 트리 구조를 개발자 모드로 출력합니다.

- **AXUIElement 덤프 출력**
  ```bash
  agbridge debug tree
  # 깊이 조절: agbridge debug tree --depth 20
  ```

### 5. 대화 내역(Session History) 추적하기
`agbridge`를 통해 진행되는 백그라운드 에이전트와의 대화 및 분석 상태를 직접 파일로 확인하고 싶다면, 대상 워크스페이스의 루트 경로에 생성되는 `.ag-sessions` 폴더를 확인하세요.

- **경로 위치**: `<대상_워크스페이스_경로>/.ag-sessions/`
- **폴더 내부 구조**:
  - `history_<session_id>.json`: 특정 배경 세션에서 오고 간 사용자의 Prompt 문장과 모델의 분석 Result(결과)가 JSON 배열 형식으로 누적 기록됩니다.
  - `active_session.txt`: 현재 해당 워크스페이스에 연결되어 기본적으로 입출력을 주고받는 최신 세션 ID 값을 저장합니다.
에이전트가 코드를 어떻게 분석하여 답변했는지 상세한 JSON 컨텍스트가 필요할 때 해당 폴더의 내역을 추적(Auditing)하는 것을 권장합니다.
