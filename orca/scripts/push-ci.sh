# 用法：bash push-ci.sh <主 repo 路徑> [workflow 檔名，預設 ci.yml] [分支，預設 main]（Bash run_in_background 掛著）
# push 之前先等主分支上還在跑的 run 跑完：多數 workflow 的 concurrency 會讓新的 push 取消舊 run，
# 上一張票（或發版）的驗證就沒了。push 之後等這個 commit 的 run 結束，印結論與失敗的 job；不綠 exit 1。
# 同一個 repo 一次只跑一個：用 .git/push-ci.lock 排隊，拿鎖的那一個結束（或它的行程已經不在）才輪到下一個。
R=$1; WF=${2:-ci.yml}; B=${3:-main}; POLL=${PUSH_CI_POLL:-30}; cd "$R" || exit 1
LOCK="$(cd "$(git rev-parse --git-common-dir)" && pwd)/push-ci.lock"
until mkdir "$LOCK" 2>/dev/null; do
  p=$(cat "$LOCK/pid" 2>/dev/null)
  if [ -n "$p" ] && ! kill -0 "$p" 2>/dev/null; then rm -rf "$LOCK"; continue; fi
  echo "another push-ci.sh (pid ${p:-?}) holds $LOCK; waiting"; sleep "$POLL"
done
echo $$ > "$LOCK/pid"; trap 'rm -rf "$LOCK"' EXIT
# gh 失敗（API 回 EOF 之類）時輸出是空的，看起來跟「沒有在跑的 run」一樣：失敗就重問，不能當成可以 push
while :; do
  out=$(gh run list --branch "$B" --limit 20 --json status,workflowName,headSha,databaseId \
    --jq '.[]|select(.status!="completed")|"\(.databaseId) \(.workflowName) \(.headSha[0:7])"') \
    || { echo "gh run list failed; retrying"; sleep "$POLL"; continue; }
  [ -z "$out" ] && break
  echo "waiting for in-progress runs: $(echo "$out" | tr '\n' ';')"; sleep "$POLL"
done
git push origin "$B" || exit 1
SHA=$(git rev-parse HEAD); ID=""
for i in $(seq 1 40); do
  ID=$(gh run list --workflow "$WF" --commit "$SHA" --limit 1 --json databaseId --jq '.[0].databaseId')
  [ -n "$ID" ] && break; sleep "$POLL"
done
[ -z "$ID" ] && { echo "no $WF run for $SHA after 40 tries"; exit 1; }
# gh run watch 偶爾會在 run 結束前就返回，所以自己輪詢 status
while [ "$(gh run view "$ID" --json status --jq .status)" != completed ]; do sleep "$POLL"; done
C=$(gh run view "$ID" --json conclusion --jq .conclusion)
echo "ci=$C run=$ID sha=${SHA:0:7}"
gh run view "$ID" --json jobs --jq '.jobs[]|select(.conclusion!="success" and .conclusion!="skipped")|"  \(.name): \(.conclusion)"'
[ "$C" = success ]
