# 用法：bash launch.sh <終端標題> <票路徑（相對 repo 根）> [每票指令，預設 /implement] [worktree 選擇器，預設 active]
# 開子 session、送「<指令> <票路徑>」、確認 skill 真的展開；印出 handle= 與 jsonl=（檔名去掉 .jsonl 就是 session id）
set -u
D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"
TITLE=$1; TICKET=$2; CMD=${3:-/implement}; WT=${4:-active}
MARK='ORCH-TICKET-'"COORDINATOR"   # 協調者自己的 transcript 含這個標記（來自 SKILL.md），拆開寫免得腳本本身被當成它
H=$(orca terminal create --worktree "$WT" --title "$TITLE" --command "claude --dangerously-skip-permissions" --json | grep -o 'term_[^"]*' | head -1)
[ -z "$H" ] && { echo "create failed"; exit 1; }
echo "handle=$H"
# 子 session 的 transcript 目錄：~/.claude/projects/<worktree 路徑把非英數字元換成 ->
JDIR=$(orca terminal list --json | H="$H" "$PY" -c "
import json, os, re, sys
d = json.load(sys.stdin)
p = next(t['worktreePath'] for t in d['result']['terminals'] if t['handle'] == os.environ['H'])
print(os.path.join(os.path.expanduser('~/.claude/projects'), re.sub(r'[^A-Za-z0-9]', '-', p)).replace(os.sep, '/'))")
orca terminal wait --terminal "$H" --for tui-idle --timeout-ms 60000 --json | grep -o '"satisfied": *[a-z]*'
# tui-idle 在輸入框能收字之前就會成立（CC v2.1.284 實測 sleep 5 仍兩次被吞，accepted 照樣是 true），所以多等，
# 並且沒展開時看畫面：看不到票路徑就是被吞了，補送；看得到就是在跑，只是慢，繼續等
sleep 15
found() {
  for f in $(ls -t "$JDIR"/*.jsonl 2>/dev/null | head -5); do
    grep -q "$MARK" "$f" && continue
    grep -q "command-args>$TICKET<" "$f" && { echo "jsonl=$f"; echo "expanded: yes"; return 0; }
  done
  return 1
}
for attempt in 1 2 3; do
  echo "send attempt $attempt"
  MSYS_NO_PATHCONV=1 orca terminal send --terminal "$H" --text "$CMD $TICKET" --enter --wait-submit 20 --json | grep -o '"accepted": *[a-z]*'
  for i in $(seq 1 10); do sleep 3; found && exit 0; done
  PYTHONIOENCODING=utf-8 "$PY" "$D/scr.py" "$H" 30 | grep -qF "$TICKET" && { for i in $(seq 1 20); do sleep 3; found && exit 0; done; break; }
  echo "command swallowed (ticket path not on screen), resending"
  sleep 10
done
echo "expanded: NO —— 讀畫面查原因；送 --interrupt、關掉 $H 後重開；同一張票連兩次沒展開算卡住"; exit 2
