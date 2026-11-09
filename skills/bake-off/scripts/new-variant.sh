# 用法：bash new-variant.sh <orca repo 選擇器> <任務名> <版號> <prompt 檔的絕對路徑>
# 從 bake/<任務名>/base 開 orca worktree（分支 bake/<任務名>/<版號>），在裡面開子 Claude Code session 讀 prompt 檔照做。
# 印 worktree=、branch=、handle=、jsonl=（照抄進 ledger）。
set -u
REPO=$1; TASK=$2; N=$3; PROMPT=$4
TC="$(cd "$(dirname "$0")/../../ticket-coordinator/scripts" && pwd)"
OUT=$(orca worktree create --repo "$REPO" --name "$TASK-$N" --base-branch "bake/$TASK/base" --branch "bake/$TASK/$N" --no-parent --json 2>&1)
P=$(echo "$OUT" | grep -o '"path": *"[^"]*"' | head -1 | sed 's/.*: *"//; s/"$//; s#\\\\#/#g')
[ -n "$P" ] && [ -d "$P" ] || { echo "worktree create failed: ${OUT:0:800}"; exit 1; }
echo "worktree=$P"
echo "branch=$(git -C "$P" rev-parse --abbrev-ref HEAD)"
bash "$TC/start-session.sh" "$P" "$TASK-$N" "$PROMPT"
