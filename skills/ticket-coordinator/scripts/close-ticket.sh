# 用法：bash close-ticket.sh <主 repo 路徑> <票的 worktree 路徑>  —— merge、push、CI 都綠之後才跑
# 關掉開在這個 worktree 的終端、移除 worktree、prune、刪已合併的分支（git branch -d：沒合併就拒絕，不會丟東西）。
# jsonl 與 session 歷史不動，使用者用 claude --resume <session id> 回看。
R=$1; W=$2; D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"
BR=$(git -C "$W" rev-parse --abbrev-ref HEAD 2>/dev/null)
# 路徑要完全相同：用子字串比對時，關 t07 會連 t07b 的終端一起關掉
for h in $(orca terminal list --json 2>/dev/null | W="$W" "$PY" "$D/terminals_in.py"); do orca terminal close --terminal "$h" >/dev/null 2>&1 && echo "closed $h"; done
orca worktree rm --worktree "path:$W" --force 2>&1 | tail -1
# Orca 在背景刪 checkout（印 "still deleting"）：等 worktree 真的不在了才刪分支，否則 branch -d 會說分支還被用著
for i in $(seq 1 12); do
  git -C "$R" worktree prune
  git -C "$R" worktree list --porcelain | grep -qxF "worktree $W" || break
  sleep 5
done
# Orca 有時會連分支一起刪掉，不在了就不必再刪
[ -n "$BR" ] && git -C "$R" show-ref --verify --quiet "refs/heads/$BR" && git -C "$R" branch -d "$BR"
git -C "$R" worktree list
