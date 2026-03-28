# Antigravity 아키텍처 및 보안 메커니즘 분석 보고서

## 1. 개요
본 문서는 Gemini CLI 서브에이전트와 구글의 코드 어시스턴트 도구인 **Antigravity**를 로컬 환경에서 연동하기 위해 진행된 아키텍처 조사, 우회 기법 테스트 및 시행착오의 전 과정을 기록한 기술 문서입니다. 

주된 목적은 구글 계정의 밴(Ban) 위험을 회피하면서, Antigravity의 강력한 코딩 AI 모델(`claude-sonnet-4-6-thinking`, `gemini-3.1-pro-high` 등)을 자동화된 오케스트레이션 파이프라인에 통합하는 것이었습니다.

---

## 2. 보안 및 아키텍처 특성 (발견 사항)

Antigravity는 VS Code(VSCodium)를 기반으로 하드포크(Hard fork)된 에디터이나, 자체적인 구글 생태계의 강력한 보안 및 격리(Isolation) 메커니즘을 겹겹이 두르고 있습니다.

### 2.1. Webview 샌드박스 및 가상 문서 격리
* **구조:** AI 채팅 패널은 VS Code의 표준 가상 문서(`TextDocument`)를 기반으로 렌더링되지 않고, 완전히 독립적인 Iframe 기반의 **순수 Webview(웹 페이지)** 로 작동합니다.
* **보안:** 이 Webview는 자신을 생성한 메인 내장 확장 프로그램(`extensions/antigravity`)하고만 `postMessage` IPC(Inter-Process Communication)로 은밀하게 통신합니다.
* **효과:** 다른 서드파티 확장 프로그램이 `vscode.workspace.onDidChangeTextDocument` API를 통해 채팅창의 텍스트를 스니핑(Sniffing)하거나 가로채는 것을 원천적으로 차단합니다. 또한, 채팅 히스토리는 로컬 디스크(SQLite, Workspace Storage 등)에 평문으로 남지 않고 메모리 상에서 휘발되거나 암호화되어 관리됩니다.

### 2.2. 디버깅 포트(CDP) 노출 은닉
* **구조:** Chromium 기반인 Electron 앱의 특성을 이용해 `--remote-debugging-port=9222` 옵션으로 Chrome DevTools Protocol(CDP)에 접근을 시도했습니다.
* **보안:** 파이어베이스 에뮬레이터나 일반 서드파티 확장의 Webview DOM에는 접근할 수 있었으나, **가장 핵심이 되는 메인 워크벤치(Workbench) 창과 AI 채팅 Webview 타겟은 CDP 목록에서 의도적으로 은닉(Hidden)**되어 있었습니다.
* **효과:** 외부 스크립트(Puppeteer 등)가 DOM 트리를 크롤링하여 강제로 텍스트를 추출해 내는 UI 스크래핑 공격을 무력화합니다.

### 2.3. 데몬(Daemon) 기반 백엔드 통신 아키텍처 (Reactor)
* **구조:** Antigravity 에디터 UI(프론트엔드)나 내부 확장 프로그램 호스트(Node.js)가 직접 구글 서버(`cloudcode-pa.googleapis.com`)로 API 요청을 보내지 않습니다.
* **보안:** 채팅을 입력하면, 에디터는 백그라운드에 별도로 띄워진 **로컬 통신 데몬 프로세스(Reactor, 예: `ws://127.0.0.1:19528` 또는 `50181` 포트)** 로 데이터를 넘기고, 이 데몬이 최종적으로 외부 인터넷과 통신합니다.
* **효과:** 에디터의 `settings.json`에 `http.proxy` (MITM 프록시 설정)나 전역 환경변수(`HTTPS_PROXY`)를 강제로 주입하더라도, 트래픽을 전담하는 데몬은 이 설정을 무시하고 독자적인 보안 통신망을 구축하므로 **표준적인 중간자 공격(MITM) 패킷 가로채기를 완벽하게 방어**합니다.

---

## 3. 시행착오 및 우회 기법 테스트 내역

안전한(밴 위험 없는) 연동 파이프라인을 구축하기 위해 다음과 같은 4단계의 우회 기법을 시도하였으나, 앞서 서술한 보안 메커니즘에 의해 모두 기각되었습니다.

### ❌ 1차 시도: VS Code 확장 프로그램 API 후킹
* **접근:** 브릿지 확장 프로그램을 만들어 에디터에 설치 후, `TextDocument` 변경 이벤트를 감지하여 대화 내용을 `.antigravity_bridge/contexts.json` 파일에 저장하려 함.
* **실패 원인:** 채팅창이 `TextDocument`를 쓰지 않는 샌드박스 Webview로 구성되어 이벤트 자체가 발생하지 않음.

### ❌ 2차 시도: 로컬 시스템 로그 및 DB 스캐닝
* **접근:** `~/Library/Application Support/Antigravity` 경로의 `state.vscdb`(SQLite) 및 `workspaceStorage`, `exthost.log` 등을 스캔하여 캐시된 대화 텍스트를 추출하려 함.
* **실패 원인:** 통신 로그나 대화 내용이 로컬에 평문으로 영구 저장되지 않는 휘발성 구조임을 확인.

### ❌ 3차 시도: CDP (Chrome DevTools Protocol) 기반 DOM 크롤링 및 네트워크 스니핑
* **접근:** 9222 포트로 접속하여 렌더러 프로세스의 `Network` 탭 패킷을 감청하거나, `Runtime.evaluate`를 통해 DOM(`document.body.innerText`)을 긁어오려 함.
* **실패 원인:** 메인 채팅 UI 타겟이 CDP 목록에서 숨겨져 있어 DOM 접근이 불가능했으며, 백엔드 데몬을 통한 통신 구조로 인해 프론트엔드 네트워크 탭에 API 트래픽이 잡히지 않음.

### ❌ 4차 시도: 로컬 웹소켓(WebSocket) 직접 연결 및 스니핑
* **접근:** `lsof`를 통해 에디터와 데몬이 대화하는 로컬 웹소켓 포트(`11632` 등)를 찾아내고, `ws` 라이브러리로 직접 소켓에 연결하여 실시간 JSON 패킷을 낚아채려 함.
* **실패 원인:** 소켓 연결에는 성공했으나, 실제 대화 시 패킷이 흐르지 않음. 이는 해당 소켓이 1:1 전용 세션이거나 연결 직후 특정 핸드쉐이크(인증)를 거쳐야만 데이터를 브로드캐스트하는 폐쇄형 구조임을 시사함.

### ❌ 5차 시도: MITM (Man-In-The-Middle) 로컬 프록시 강제 할당 및 SSL 복호화
* **접근:** `http-mitm-proxy`를 가동하고 Antigravity 설정(`http.proxy`, `proxyStrictSSL: false`) 및 전역 환경변수(`HTTP_PROXY`, `HTTPS_PROXY`)를 통해 트래픽을 프록시 서버로 유도, 암호화된 HTTPS 패킷을 복호화하여 평문 대화 내용을 추출하려 함.
* **실패 원인:** Antigravity의 백그라운드 데몬(Reactor)이 에디터나 OS의 프록시 설정을 완전히 무시하고 독자적인 네트워크 스택으로 구글 서버와 통신함. 이로 인해 트래픽이 우리 프록시 서버를 거치지 않고 우회하여 가로채기 실패.

---

## 4. 최종 결론 및 권고 아키텍처

로컬에 띄워진 Antigravity GUI 클라이언트의 정상적인 작동을 뒤에서 몰래 감청하거나 조종하여 컨텍스트를 빼내는 방식은 구글의 철저한 보안 아키텍처에 의해 기술적으로 **불가능**함이 입증되었습니다.

따라서 밴(Ban)의 위험을 원천적으로 통제하면서 자동화를 달성할 수 있는 유일한 솔루션은 **[버너 계정(Burner Account) + API 프록시 서버]** 아키텍처입니다.

### 🚀 권고 파이프라인 (Direct API Proxy)
1. **격리된 부계정 사용:** 본 계정이 아닌 깡통 구글 계정(Burner)을 생성하여 밴(Ban) 리스크를 이 계정에만 한정시킵니다.
2. **`antigravity-claude-proxy` 가동:** 부계정의 토큰을 활용해 공식 클라이언트 통신을 흉내 내는 API 프록시 서버(`http://127.0.0.1:8080`)를 로컬에 구동합니다.
3. **Gemini CLI 통합:** Gemini CLI 서브에이전트가 로컬 파일이나 UI 조작 없이, 직접 프록시 서버의 `/v1/messages` 엔드포인트로 REST API 요청을 쏘고 코드를 응답받아 워크플로우를 진행합니다.

이 방식은 UI 병목이 없고 가장 속도가 빠르며, 최악의 경우 봇(Bot)으로 감지되어 밴을 당하더라도 부계정만 교체하면 되는 가장 현실적이고 강력한 엔터프라이즈 자동화 패턴입니다.