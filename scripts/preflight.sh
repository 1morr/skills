# 用法：bash preflight.sh <主 repo 路徑> [主分支，預設 main]  —— 每次被叫醒、每次 merge 之前跑
# 同一個 repo 可能還有別的 session（另一個協調者、使用者自己開的）在動主目錄。印出不是你造成的痕跡，
# 有 WARN 就先對照 ledger 弄清楚是誰的，不明來源的 commit 不要跟著你的 push 一起推上去。
R=$1; B=${2:-main}; cd "$R" || exit 1
git fetch -q origin
echo "HEAD $(git rev-parse --abbrev-ref HEAD) $(git log --oneline -1)"
up=$(git log --oneline "origin/$B..$B"); [ -n "$up" ] && { echo "WARN 本機 $B 有還沒 push 的 commit（是你 merge 的嗎？對 ledger）："; echo "$up"; }
down=$(git log --oneline "$B..origin/$B"); [ -n "$down" ] && { echo "WARN origin/$B 有本機沒有的 commit（別處 push 的）："; echo "$down"; }
dirty=$(git status --short --untracked-files=no); [ -n "$dirty" ] && { echo "WARN 主目錄有未提交的追蹤檔改動（別的 session 在主目錄工作？不要在這裡 merge）："; echo "$dirty"; }
new=$(git status --short | grep '^??'); [ -n "$new" ] && { echo "INFO 未追蹤的檔（不是你的就別 add）："; echo "$new"; }
echo "worktrees:"; git worktree list
echo "terminals in this repo:"; orca terminal list 2>/dev/null | grep -i "$(basename "$R")" || echo "(orca 不可用或沒有)"
[ -z "$up$down$dirty" ]
