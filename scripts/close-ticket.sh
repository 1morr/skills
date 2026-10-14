# 用法：bash close-ticket.sh <主 repo 路徑> <票的 worktree 路徑>  —— merge、push、CI 都綠之後才跑
# 關掉開在這個 worktree 的終端、移除 worktree、prune、刪已合併的分支（git branch -d：沒合併就拒絕，不會丟東西）。
# jsonl 與 session 歷史不動，使用者用 claude --resume <session id> 回看。
R=$1; W=$2
BR=$(git -C "$W" rev-parse --abbrev-ref HEAD 2>/dev/null)
for h in $(orca terminal list 2>/dev/null | grep -F "$W" | awk '{print $1}'); do orca terminal close --terminal "$h" >/dev/null 2>&1 && echo "closed $h"; done
orca worktree rm --worktree "path:$W" --force 2>&1 | tail -1
git -C "$R" worktree prune
[ -n "$BR" ] && git -C "$R" branch -d "$BR"
git -C "$R" worktree list
