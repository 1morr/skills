# 用法：bash merge-ticket.sh <主 repo 路徑> <票的 worktree 路徑> <票路徑（相對 repo 根）> <merge message>
# 環境變數 REQUIRE="docs/progress.md ..."：專案完成標準要求每張票都動到的檔（照專案 CLAUDE.md 填）
# 驗收 a–c 與 commit 格式全部成立才 `git merge --no-ff`；任何一項不成立就列出來、exit 1、什麼都不動。
# 衝突時停在合併中（exit 3）交給協調者解。不跑測試、不 push：測試範圍見 SKILL.md 第 4 步 d，push 用 push-ci.sh。
set -u
R=$1; W=$2; T=$3; MSG=$4; B=${BASE:-main}
BR=$(git -C "$W" rev-parse --abbrev-ref HEAD) || exit 1
bad=()
[ -n "$(git -C "$W" status --short)" ] && bad+=("worktree 不乾淨：$(git -C "$W" status --short | head -5 | tr '\n' ' ')")
commits=$(git -C "$R" log --format='%h %s' "$B..$BR")
[ -z "$commits" ] && bad+=("$BR 相對 $B 沒有新 commit")
CC='^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?!?: [^A-Z[:space:]]'
while read -r h s; do
  [ -z "$h" ] && continue
  [ ${#s} -gt 72 ] && bad+=("$h 標題 ${#s} 字元 > 72：$s")
  [[ "$s" =~ $CC || "$s" == Merge\ * ]] || bad+=("$h 不是 Conventional Commits 小寫開頭：$s")
done <<< "$commits"
TF="$W/$T"
if [ -f "$TF" ]; then
  grep -qiE '^\**Status:?\**:?\s*done' "$TF" || bad+=("票的 Status 不是 done：$(grep -im1 'status' "$TF")")
  n=$(grep -cE '^\s*[-*] \[ \]' "$TF"); [ "$n" -gt 0 ] && bad+=("票上還有 $n 個沒勾的驗收條件")
else
  bad+=("找不到票檔 $TF")
fi
for f in ${REQUIRE:-}; do
  git -C "$R" diff --quiet "$B...$BR" -- "$f" && bad+=("$BR 沒有改到 $f（專案完成標準要求）")
done
[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = "$B" ] || bad+=("主目錄不在 $B 上")
[ -n "$(git -C "$R" status --short --untracked-files=no)" ] && bad+=("主目錄有未提交的追蹤檔改動，可能是別的 session 在用；先跑 preflight.sh 查清楚")
if [ ${#bad[@]} -gt 0 ]; then printf 'NOT READY: %s\n' "${bad[@]}"; exit 1; fi
echo "checks ok: $(echo "$commits" | wc -l) commit(s) on $BR"
if git -C "$R" merge --no-ff -m "$MSG" "$BR"; then
  git -C "$R" log --oneline -1
else
  echo "CONFLICT: 停在合併中。git -C $R diff --name-only --diff-filter=U 看衝突檔；解不了就 git merge --abort，叫子 session 在它的分支先 merge $B"
  exit 3
fi
