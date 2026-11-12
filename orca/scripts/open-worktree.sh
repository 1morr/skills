# 用法：bash open-worktree.sh <orca repo 選擇器> <worktree 名> <起點分支> <新分支> <prompt 檔的絕對路徑>
# 從起點分支開 orca worktree 和新分支，在裡面開子 Claude Code session 讀 prompt 檔照做。
# 印 worktree=、branch=、handle=、jsonl=（照抄進 ledger）。收掉用 close-worktree.sh。
set -u
REPO=$1; NAME=$2; BASE=$3; BR=$4; PROMPT=$5
D="$(cd "$(dirname "$0")" && pwd)"
OUT=$(orca worktree create --repo "$REPO" --name "$NAME" --base-branch "$BASE" --branch "$BR" --no-parent --json 2>&1)
P=$(echo "$OUT" | grep -o '"path": *"[^"]*"' | head -1 | sed 's/.*: *"//; s/"$//; s#\\\\#/#g')
[ -n "$P" ] && [ -d "$P" ] || { echo "worktree create failed: ${OUT:0:800}"; exit 1; }
echo "worktree=$P"
echo "branch=$(git -C "$P" rev-parse --abbrev-ref HEAD)"
bash "$D/start-session.sh" "$P" "$NAME" "$PROMPT"
