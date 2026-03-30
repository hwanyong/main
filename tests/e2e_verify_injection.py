import os
import sys
import subprocess
import time

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "calc_adv_1"))
AGENT_SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "ag-agent.sh"))

def run():
    print(f"▶ Testing Injection across Workspace: {WORKSPACE}")
    
    # Run info first
    subprocess.run([AGENT_SCRIPT, "info", "-w", WORKSPACE])
    
    # The Prompt string that commands the orchestrator
    print("\n▶ Sending Prompt (injecting /code workflow, and a distinct model)")
    prompt = "@[/code] [model: Gemini 3 Flash] Create a simple file named injected_test.txt with a single hello line."
    
    cmd = [AGENT_SCRIPT, "ask", "-w", WORKSPACE, "--new", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
         print("\n✅ Success!")
         if "🤖 Agent Response" in result.stdout:
             print(result.stdout.split("🤖 Agent Response")[1].strip())
         else:
             print("Raw Output:", result.stdout[-500:])
    else:
         print(f"❌ Failed: {result.stderr}")
         
if __name__ == "__main__":
    run()
