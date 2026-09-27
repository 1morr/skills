# 用法：bash waitbg.sh <handle> <子 session 的 jsonl 路徑>（Bash run_in_background 掛著）
# 子 session 閒下來、而且沒有在等自己的背景工作時才返回；tui-idle 單獨用會在它等背景 shell / 子代理時就返回
H=$1; J=$2; cd "$(dirname "$0")"
BG='… [(]([0-9]+h )?([0-9]+m )?[0-9]+s|still running|Waiting for [0-9]+ background|· [0-9]+ (shells?|monitors?)'
busy() { PYTHONIOENCODING=utf-8 python scr.py "$H" 16 | grep -qE "$BG" && return 0; [ -n "$J" ] && python busy.py "$J" && return 0; return 1; }
for round in $(seq 1 30); do
  for i in $(seq 1 240); do busy || break; sleep 30; done
  orca terminal wait --terminal "$H" --for tui-idle --timeout-ms 3600000 --json 2>&1 | grep -oE '"(satisfied|status)": *[^,}]*'
  sleep 5
  busy || exit 0
  echo "round $round: idle but busy, continue"
done
