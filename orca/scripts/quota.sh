# 用法：bash quota.sh [5h 門檻%] [7d 門檻%] [handle]  —— 開票前問額度能不能開
# 來源依序：
#   1. QUOTA_FILE（預設 ~/.claude/rate-limits.json）：狀態列指令把 Claude Code 給它的 `rate_limits` 存下來的檔，
#      格式 {"at": <寫入時間>, "rate_limits": {"five_hour": {"used_percentage", "resets_at"}, "seven_day": {…}}}；
#      QUOTA_MAX_AGE（預設 600）秒內寫過才算數。設定方式見 plugin 根目錄 README.md〈額度門檻〉。
#   2. 協調者自己終端的狀態列畫面（handle 預設 $ORCA_TERMINAL_HANDLE），要有 `5h 60% ↻ 18m · 7d 90% ↻ 4d16h` 的格式。
# 印一行：gate=open|closed|unknown src=file|screen|none 5h=<%> 5h_reset=<剩餘> 7d=<%> 7d_reset=<剩餘> sleep=<秒>
#   closed：某個門檻到了，sleep 是到那個額度刷新再多 3 分鐘
#   unknown：兩個來源都讀不到；有設門檻時 sleep=600（先別開票，過一陣子再問），沒設門檻時 sleep=0
# 門檻不給或給 0 表示不限。
cd "$(dirname "$0")"; . ./py.sh
T5=${1:-0}; T7=${2:-0}; H=${3:-$ORCA_TERMINAL_HANDLE}
read_line() { [ -n "$H" ] && PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 12 2>/dev/null; }
screen=
file=${QUOTA_FILE:-$HOME/.claude/rate-limits.json}
if ! T5="$T5" FILE="$file" MAX_AGE="${QUOTA_MAX_AGE:-600}" "$PY" -c '
import json, os, sys, time
try:
    d = json.load(open(os.environ["FILE"], encoding="utf-8"))
    sys.exit(0 if time.time() - d["at"] <= int(os.environ["MAX_AGE"]) and d["rate_limits"] else 1)
except Exception:
    sys.exit(1)'; then
  screen=$(read_line); echo "$screen" | grep -q '[57][hd] [0-9]*%' || { sleep 2; screen=$(read_line); }
fi
printf '%s' "$screen" | T5="$T5" T7="$T7" FILE="$file" USE_FILE=$([ -z "$screen" ] && echo 1) "$PY" -c '
import json, os, re, sys, time
now = time.time()
def secs(t):
    n = 0
    for v, u in re.findall(r"(\d+)([dhm])", t): n += int(v) * {"d": 86400, "h": 3600, "m": 60}[u]
    return n
def left(s):
    s = max(0, int(s)); d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return "%dd%dh" % (d, h) if d else "%dh%dm" % (h, m) if h else "%dm" % m
got, src = {}, "none"   # got[k] = (已用 %, 剩餘文字, 到刷新的秒數)
if os.environ.get("USE_FILE"):
    rl = json.load(open(os.environ["FILE"], encoding="utf-8"))["rate_limits"]
    for k, key in (("5h", "five_hour"), ("7d", "seven_day")):
        w = rl.get(key) or {}
        if isinstance(w.get("used_percentage"), (int, float)):
            r = w.get("resets_at") or now
            got[k] = (round(w["used_percentage"]), left(r - now), max(0, r - now))
    src = "file" if got else "none"
else:
    s = sys.stdin.read()
    for k in ("5h", "7d"):
        m = re.findall(k + r" (\d+)% ↻ ?([0-9dhm]+)", s)
        if m: got[k] = (int(m[-1][0]), m[-1][1], secs(m[-1][1]))
    src = "screen" if got else "none"
g = lambda k, i: str(got[k][i]) if k in got else "?"
gates = [(k, int(os.environ[e] or 0)) for k, e in (("5h", "T5"), ("7d", "T7"))]
if not got:
    gate, wait = "unknown", 600 if any(t for _, t in gates) else 0
else:
    wait = max([int(got[k][2]) + 180 for k, t in gates if t and k in got and got[k][0] >= t] or [0])
    gate = "closed" if wait else "open"
print("gate=%s src=%s 5h=%s 5h_reset=%s 7d=%s 7d_reset=%s sleep=%d" % (gate, src, g("5h", 0), g("5h", 1), g("7d", 0), g("7d", 1), wait))
'
