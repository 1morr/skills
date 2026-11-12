# 用法：bash quota.sh [5h 門檻%] [7d 門檻%] [handle]  —— 開票前問額度能不能開
# 讀協調者自己終端的狀態列（要有 `5h 60% ↻ 18m · 7d 90% ↻ 4d16h` 這種格式；handle 預設 $ORCA_TERMINAL_HANDLE）。
# 印一行：gate=open|closed|unknown 5h=<%> 5h_reset=<剩餘> 7d=<%> 7d_reset=<剩餘> sleep=<秒>
#   closed：某個門檻到了，sleep 是到那個額度刷新再多 3 分鐘的秒數（背景 sleep 這麼久再問一次）
#   unknown：讀了兩次都找不到數字（狀態列沒顯示額度）；照常開票，在 ledger 記一筆
# 門檻不給或給 0 表示不限。
cd "$(dirname "$0")"; . ./py.sh
T5=${1:-0}; T7=${2:-0}; H=${3:-$ORCA_TERMINAL_HANDLE}
read_line() { [ -n "$H" ] && PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 12 2>/dev/null; }
line=$(read_line); echo "$line" | grep -q '5h [0-9]*%' || { sleep 2; line=$(read_line); }
printf '%s' "$line" | T5="$T5" T7="$T7" "$PY" -c '
import os, re, sys
s = sys.stdin.read()
def secs(t):
    n = 0
    for v, u in re.findall(r"(\d+)([dhm])", t): n += int(v) * {"d": 86400, "h": 3600, "m": 60}[u]
    return n
got = {}
for k in ("5h", "7d"):
    m = re.findall(k + r" (\d+)% ↻ ?([0-9dhm]+)", s)
    if m: got[k] = (int(m[-1][0]), m[-1][1])
if "5h" not in got and "7d" not in got:
    print("gate=unknown 5h=? 5h_reset=? 7d=? 7d_reset=? sleep=0"); sys.exit()
wait = 0
for k, env in (("5h", "T5"), ("7d", "T7")):
    t = int(os.environ[env] or 0)
    if t and k in got and got[k][0] >= t: wait = max(wait, secs(got[k][1]) + 180)
g = lambda k, i: str(got[k][i]) if k in got else "?"
gate = "closed" if wait else "open"
print("gate=%s 5h=%s 5h_reset=%s 7d=%s 7d_reset=%s sleep=%d" % (gate, g("5h", 0), g("5h", 1), g("7d", 0), g("7d", 1), wait))
'
