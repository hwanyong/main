import os
import sys
import subprocess
import threading
import time

PROMPTS_PROJECT_1 = [
    "1단계: 고급 Python 사칙연산 계산기 프로젝트를 시작할거야. 먼저 프로젝트 구조(빈 파일들)를 예상해서 만들고, 어떤 기능이 들어갈지 README.md 파일을 작성해줘.",
    "2단계: 핵심 계산 로직인 core.py 파일에 +, -, *, / 함수를 작성해줘. type hint를 꼭 사용해.",
    "3단계: core.py에 0으로 나누기 에러(ZeroDivisionError)나 잘못된 타입 입력 시 처리하는 예외 처리 로직을 추가해.",
    "4단계: 터미널에서 사용자와 상호작용하는 cli.py 파일을 만들어줘. 무한 루프로 동작하며 'q'를 누르면 종료되게 해.",
    "5단계: 마지막으로 지금까지 작성한 코드가 잘 동작하는지 확인할 수 있는 단위 테스트 파일 test_core.py를 짧게 작성해줘."
]

PROMPTS_PROJECT_2 = [
    "Step 1: Node.js 고급 사칙연산 계산기 프로젝트를 만들거야. 구조를 기획하고 리드미(README.md)만 먼저 작성해.",
    "Step 2: 핵심 비즈니스 로직을 담당하는 index.js에 4가지 기본 연산 함수를 짜줘. JSDoc을 달아줘.",
    "Step 3: index.js의 함수들에 에러 핸들링을 추가해. (예: 0으로 나누기, 숫자가 아닌 값 입력). throw Error를 사용해.",
    "Step 4: readline 모듈을 사용해서 터미널에서 대화형으로 입력을 받는 cli.js 파일을 작성해줘.",
    "Step 5: Jest를 사용한다고 가정하고 index.js를 테스트하는 index.test.js 파일을 간단히 만들어 기능이 정상인지 검증해."
]

WORKSPACE_1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "calc_adv_1"))
WORKSPACE_2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "calc_adv_2"))

AGENT_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "ag-agent.sh"))


def run_agent_step(workspace, step_num, prompt, is_first, max_retries=3):
    """ag-agent.sh를 호출하여 프롬프트를 실행하고 출력을 반환한다."""
    cmd = [AGENT_SCRIPT, "ask", "-w", workspace]
    if is_first:
        cmd.append("--new")
    cmd.append(prompt)

    for attempt in range(max_retries):
        print(f"\n[{os.path.basename(workspace)}] >> 시작: {step_num}단계 (재시도: {attempt}/{max_retries - 1})")
        start_time = time.monotonic()
        
        # 실행 및 출력 캡처
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.monotonic() - start_time
        
        output = result.stdout
        
        if result.returncode == 0:
            print(f"\n==================================================")
            print(f"[{os.path.basename(workspace)} - {step_num}단계 완료] ({elapsed:.1f}초)")
            # Agent 피드백 부분만 추출 (가독성을 위해 파싱)
            if "🤖 Agent Response" in output:
                response_part = output.split("🤖 Agent Response")[1]
                print(response_part.strip())
            else:
                print("응답 파싱 실패. 전체 출력:")
                print(output.strip()[-500:]) # 너무 길면 끝부분만
            print(f"==================================================\n")
            return  # 성공하면 루프 탈출
        
        print(f"❌ {step_num}단계 실패 (Code: {result.returncode}), {elapsed:.1f}초 경과")
        print(f"오류: {result.stderr.strip()}")
        
        if attempt < max_retries - 1:
            print("▶ 3초 대기 후 재시도합니다...")
            time.sleep(3)
        else:
            print(f"⛔ {step_num}단계 최종 실패. 테스트를 중단하거나 로깅합니다.")
            print(f"==================================================\n")


def project_worker(workspace, prompts):
    for i, prompt in enumerate(prompts):
        step_num = i + 1
        is_first = (step_num == 1)
        run_agent_step(workspace, step_num, prompt, is_first)
        # 다음 단계 요청 전 화면 안정화를 위한 대기
        time.sleep(2)


def main():
    import shutil
    
    # 작업 디렉토리 강제 초기화 및 재생성
    if os.path.exists(WORKSPACE_1): shutil.rmtree(WORKSPACE_1)
    if os.path.exists(WORKSPACE_2): shutil.rmtree(WORKSPACE_2)
    os.makedirs(WORKSPACE_1)
    os.makedirs(WORKSPACE_2)
    
    # 2. antigravity 에디터 실행 (새 창으로)
    print("에디터 창 여는 중...")
    subprocess.run(["antigravity", "-n", WORKSPACE_1])
    subprocess.run(["antigravity", "-n", WORKSPACE_2])
    time.sleep(3) # 에디터가 완전히 로드될 때까지 약간 대기
    
    print("▶ 병렬 에이전트 다기능 5단계 고도화 테스트 시작")
    print(f"프로젝트 1: {WORKSPACE_1}")
    print(f"프로젝트 2: {WORKSPACE_2}")
    
    t1 = threading.Thread(target=project_worker, args=(WORKSPACE_1, PROMPTS_PROJECT_1))
    t2 = threading.Thread(target=project_worker, args=(WORKSPACE_2, PROMPTS_PROJECT_2))
    
    start_time = time.time()
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print(f"\n✅ 완료! 전체 소요 시간: {time.time() - start_time:.1f}초")

if __name__ == "__main__":
    main()
