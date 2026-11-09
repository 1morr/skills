# 用法：bash new-variant.sh <orca repo 選擇器> <任務名> <版號> <prompt 檔的絕對路徑>
# 從 bake/<任務名>/base 開 orca worktree（分支 bake/<任務名>/<版號>），在裡面開子 Claude Code session，
# 啟動參數直接帶「讀 prompt 檔照做」。印 worktree=、handle=、jsonl=（照抄進 ledger）。
# 用啟動參數而不是開好再打字：剛開的 TUI 會吞掉輸入（ticket-coordinator 的 TUI.md「開 session」）
set -u
REPO=$1; TASK=$2; N=$3; PROMPT=$4
TC="$(cd "$(dirname "$0")/../../ticket-coordinator/scripts" && pwd)"; . "$TC/py.sh"
[ -f "$PROMPT" ] || { echo "prompt file not found: $PROMPT"; exit 1; }
PROMPT=$(echo "$PROMPT" | sed 's#\\#/#g')
OUT=$(orca worktree create --repo "$REPO" --name "$TASK-$N" --base-branch "bake/$TASK/base" --branch "bake/$TASK/$N" --no-parent --json 2>&1)
P=$(echo "$OUT" | grep -o '"path": *"[^"]*"' | head -1 | sed 's/.*: *"//; s/"$//; s#\\\\#/#g')
[ -n "$P" ] && [ -d "$P" ] || { echo "worktree create failed: ${OUT:0:800}"; exit 1; }
echo "worktree=$P"
echo "branch=$(git -C "$P" rev-parse --abbrev-ref HEAD)"
MSG="Read $PROMPT and follow it."
H=$(orca terminal create --worktree "path:$P" --title "$TASK-$N" --command "claude --dangerously-skip-permissions \"$MSG\"" --json | grep -o 'term_[^"]*' | head -1)
[ -z "$H" ] && { echo "terminal create failed"; exit 1; }
echo "handle=$H"
# 子 session 的 transcript 目錄：~/.claude/projects/<worktree 路徑把非英數字元換成 ->
JDIR=$(P="$P" "$PY" -c "
import os, re
print(os.path.join(os.path.expanduser('~/.claude/projects'), re.sub(r'[^A-Za-z0-9]', '-', os.environ['P'])).replace(os.sep, '/'))")
for i in $(seq 1 40); do
  sleep 3
  for f in $(ls -t "$JDIR"/*.jsonl 2>/dev/null | head -3); do
    grep -qF "$PROMPT" "$f" && { echo "jsonl=$f"; echo "started: yes"; exit 0; }
  done
done
echo "started: NO —— 用 scr.py 讀 $H 的畫面查原因（啟動失敗、信任資料夾的提示、額度）"; exit 2
