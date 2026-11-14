# 用法：bash start-session.sh <worktree 路徑> <終端標題> <第一則訊息> <transcript 裡要出現的字串>
# 在 worktree 開一個子 Claude Code session，第一則訊息當啟動參數帶進去，印 handle= 與 jsonl=（檔名去掉 .jsonl 就是 session id）。
# 由 open-worktree.sh（訊息是「讀 prompt 檔照做」）和 new-ticket.sh（訊息是「/指令 票路徑」）呼叫。
# 環境變數 CHILD_CLAUDE：子 session 的啟動指令，預設 claude --dangerously-skip-permissions（免確認，才能無人值守）
# 用啟動參數而不是開好再打字：剛開的 TUI 會吞掉輸入（CC v2.1.284 實測 tui-idle 之後再等 5 秒仍兩次被吞，accepted 照樣是 true）。
# 斜線指令當啟動參數一樣會展開（CC v2.1.325 實測，3 秒內 transcript 就有 command-args）。
# 認 transcript 的方法是「開之前不存在、內容含指定字串」：協調者自己可能就在同一個 worktree，
# 它的 transcript 也提過同一個字串，只比內容會認錯。
set -u
P=$(echo "$1" | sed 's#\\#/#g'); TITLE=$2; MSG=$3; WANT=$4
D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"
# 子 session 的 transcript 目錄：~/.claude/projects/<worktree 路徑把非英數字元換成 ->
JDIR=$(P="$P" "$PY" -c "
import os, re
print(os.path.join(os.path.expanduser('~/.claude/projects'), re.sub(r'[^A-Za-z0-9]', '-', os.environ['P'])).replace(os.sep, '/'))")
BEFORE=$(ls "$JDIR"/*.jsonl 2>/dev/null)
H=$(orca terminal create --worktree "path:$P" --title "$TITLE" --command "${CHILD_CLAUDE:-claude --dangerously-skip-permissions} \"$MSG\"" --json | grep -o 'term_[^"]*' | head -1)
[ -z "$H" ] && { echo "terminal create failed"; exit 1; }
echo "handle=$H"
for i in $(seq 1 40); do
  sleep 3
  for f in $(ls -t "$JDIR"/*.jsonl 2>/dev/null | head -5); do
    echo "$BEFORE" | grep -qxF "$f" && continue
    grep -qF -- "$WANT" "$f" && { echo "jsonl=$f"; echo "started: yes"; exit 0; }
  done
done
echo "started: NO —— 用 scr.py 讀 $H 的畫面查原因（啟動失敗、信任資料夾的提示、額度、指令沒展開）"; exit 2
