# 用法：bash start-session.sh <worktree 路徑> <終端標題> <prompt 檔的絕對路徑>
# 在 worktree 開一個子 Claude Code session，啟動參數直接帶「讀 prompt 檔照做」，印 handle= 與 jsonl=。
# 用啟動參數而不是開好再打字：剛開的 TUI 會吞掉輸入（TUI.md「開 session」）。
# 認 transcript 的方法是「開之前不存在、內容含 prompt 路徑」：協調者自己可能就在同一個 worktree，
# 它的 transcript 也提過 prompt 路徑，只比內容會認錯。
set -u
P=$(echo "$1" | sed 's#\\#/#g'); TITLE=$2; PROMPT=$(echo "$3" | sed 's#\\#/#g')
D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"
[ -f "$PROMPT" ] || { echo "prompt file not found: $PROMPT"; exit 1; }
# 子 session 的 transcript 目錄：~/.claude/projects/<worktree 路徑把非英數字元換成 ->
JDIR=$(P="$P" "$PY" -c "
import os, re
print(os.path.join(os.path.expanduser('~/.claude/projects'), re.sub(r'[^A-Za-z0-9]', '-', os.environ['P'])).replace(os.sep, '/'))")
BEFORE=$(ls "$JDIR"/*.jsonl 2>/dev/null)
MSG="Read $PROMPT and follow it."
H=$(orca terminal create --worktree "path:$P" --title "$TITLE" --command "claude --dangerously-skip-permissions \"$MSG\"" --json | grep -o 'term_[^"]*' | head -1)
[ -z "$H" ] && { echo "terminal create failed"; exit 1; }
echo "handle=$H"
for i in $(seq 1 40); do
  sleep 3
  for f in $(ls -t "$JDIR"/*.jsonl 2>/dev/null | head -5); do
    echo "$BEFORE" | grep -qxF "$f" && continue
    grep -qF "$PROMPT" "$f" && { echo "jsonl=$f"; echo "started: yes"; exit 0; }
  done
done
echo "started: NO —— 用 scr.py 讀 $H 的畫面查原因（啟動失敗、信任資料夾的提示、額度）"; exit 2
