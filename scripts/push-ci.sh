# 用法：bash push-ci.sh <主 repo 路徑> [workflow 檔名，預設 ci.yml] [分支，預設 main]（Bash run_in_background 掛著）
# push 之前先等主分支上還在跑的 run 跑完：多數 workflow 的 concurrency 會讓新的 push 取消舊 run，
# 上一張票（或發版）的驗證就沒了。push 之後等這個 commit 的 run 結束，印結論與失敗的 job；不綠 exit 1。
R=$1; WF=${2:-ci.yml}; B=${3:-main}; cd "$R" || exit 1
running() { gh run list --branch "$B" --limit 20 --json status,workflowName,headSha,databaseId \
  --jq '.[]|select(.status!="completed")|"\(.databaseId) \(.workflowName) \(.headSha[0:7])"'; }
while [ -n "$(running)" ]; do echo "waiting for in-progress runs: $(running | tr '\n' ';')"; sleep 30; done
git push origin "$B" || exit 1
SHA=$(git rev-parse HEAD); ID=""
for i in $(seq 1 40); do
  ID=$(gh run list --workflow "$WF" --commit "$SHA" --limit 1 --json databaseId --jq '.[0].databaseId')
  [ -n "$ID" ] && break; sleep 15
done
[ -z "$ID" ] && { echo "no $WF run for $SHA after 10 min"; exit 1; }
# gh run watch 偶爾會在 run 結束前就返回，所以自己輪詢 status
while [ "$(gh run view "$ID" --json status --jq .status)" != completed ]; do sleep 30; done
C=$(gh run view "$ID" --json conclusion --jq .conclusion)
echo "ci=$C run=$ID sha=${SHA:0:7}"
gh run view "$ID" --json jobs --jq '.jobs[]|select(.conclusion!="success" and .conclusion!="skipped")|"  \(.name): \(.conclusion)"'
[ "$C" = success ]
