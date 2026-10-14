# 用法：bash new-ticket.sh <orca repo 選擇器，例如 id:xxxx> <worktree 名，例如 t62> <票路徑（相對 repo 根）> [標題] [每票指令，預設 /implement]
# 從主分支開一個 orca worktree，在裡面開子 session 跑票。印 worktree=、handle=、jsonl=、expanded:（照抄進 ledger）
set -u
REPO=$1; NAME=$2; T=$3; TITLE=${4:-$NAME}; CMD=${5:-/implement}; D="$(cd "$(dirname "$0")" && pwd)"
OUT=$(orca worktree create --repo "$REPO" --name "$NAME" --base-branch "${BASE:-main}" --no-parent --json 2>&1)
P=$(echo "$OUT" | grep -o '"path": *"[^"]*"' | head -1 | sed 's/.*: *"//; s/"$//; s#\\\\#/#g')
[ -n "$P" ] && [ -d "$P" ] || { echo "worktree create failed: ${OUT:0:800}"; exit 1; }
echo "worktree=$P"
bash "$D/launch.sh" "$TITLE" "$T" "$CMD" "path:$P"
