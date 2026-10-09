#!/usr/bin/env python3
"""사용자가 일정 시간 이상 지나서 다시 말을 걸면 git pull을 하고, 노트를 다시 읽으라고 Claude에게 알려요.

UserPromptSubmit 훅에서 실행돼요. 연속으로 대화할 때는 아무것도 하지 않아요.
"""
import json, os, subprocess, sys, time

GAP_HOURS = 2  # 이 시간 이상 쉬었다가 돌아오면 동작
root = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
stamp = os.path.join(root, ".claude", "last_prompt_time")

now = time.time()
try:
    last = float(open(stamp).read().strip())
except Exception:
    last = 0.0
try:
    open(stamp, "w").write(str(now))
except Exception:
    pass

gap_h = (now - last) / 3600
if last and gap_h < GAP_HOURS:
    sys.exit(0)  # 연속 대화: 조용히 넘어감

try:
    r = subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], cwd=root,
                       capture_output=True, text=True, timeout=30)
    pull = "성공" if r.returncode == 0 else "실패: " + (r.stderr or r.stdout).strip()[:300]
except Exception as e:
    pull = f"실패: {e}"

away = f"{gap_h:.0f}시간 만에" if last else "처음으로"
msg = (f"[자동 안내] 사용자가 {away} 돌아왔어요. 방금 git pull을 실행했어요({pull}). "
       "답하기 전에 CLAUDE.md, docs/session-summary.md, docs/watchlist.md를 다시 읽고, "
       "질문이 매매 판단과 관련 있으면 docs/analysis-notes.md의 관련 부분도 다시 확인한 뒤 답하세요. "
       "답의 첫 줄에 노트를 새로 읽었다는 것과 git pull 결과를 짧게 알려 주세요.")
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}}, ensure_ascii=False))
