#!/bin/sh
# 用法（放進 Claude Code 的狀態列指令）：sh save-rate-limits.sh | <你原本的狀態列指令>
# Claude Code 每次更新狀態列，都把一份 JSON 從 stdin 交給狀態列指令。這支把其中的 `rate_limits` 存成
# quota.sh 讀的檔，再把 JSON 原樣印到 stdout 給後面的指令。沒有原本的狀態列指令時，後面接 `>/dev/null`。
#   存到 $QUOTA_FILE（預設 ~/.claude/rate-limits.json），內容 {"at": <寫入時間>, "rate_limits": …}；先寫暫存檔再改名。
#   JSON 裡沒有 rate_limits（剛開 session 的頭幾次）就不動舊檔。讀不到、沒有 Python 時只照樣轉交，不報錯。
# 不依賴同資料夾的其他檔，可以單獨複製到 ~/.claude/（plugin 的安裝路徑每次更新都會變）。
payload=$(cat)
printf '%s' "$payload"
for py in python3 python; do
  "$py" -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1 || continue
  printf '%s' "$payload" | "$py" -c '
import json, os, sys, time
try:
    rl = json.load(sys.stdin).get("rate_limits")
except Exception:
    sys.exit()
if not rl:
    sys.exit()
p = os.environ.get("QUOTA_FILE") or os.path.expanduser("~/.claude/rate-limits.json")
tmp = "%s.%d.tmp" % (p, os.getpid())
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"at": int(time.time()), "rate_limits": rl}, f)
os.replace(tmp, p)
' >/dev/null 2>&1
  break
done
exit 0
