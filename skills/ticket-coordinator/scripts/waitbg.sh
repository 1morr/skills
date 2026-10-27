# 用法：bash waitbg.sh <handle> <子 session 的 jsonl 路徑>（Bash run_in_background 掛著）
# 子 session 停下來才返回，最後一行印 state=done|asking|stalled|unknown 與畫面。判斷以 state.py（transcript）為準；
# 畫面只當補充：transcript 說 done、畫面卻還有背景 shell / monitor 的計數時繼續等（state.py 認不出 Monitor）
H=$1; J=$2; cd "$(dirname "$0")"; . ./py.sh
BG='… [(]([0-9]+h )?([0-9]+m )?[0-9]+s|still running|Waiting for [0-9]+ background|· [0-9]+ (shells?|monitors?)'
screen_bg() { PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 16 | grep -qE "$BG"; }
quiet() { age "$J"; }
while :; do
  st=$("$PY" state.py "$J"); rc=$?
  case $rc in
    2) break ;;
    0) screen_bg || break ;;
    # 只在等自己的背景工作、畫面又看不到任何在跑的東西，半小時沒動靜：多半是它停了自己的背景工作，交給協調者看
    1) [ "$st" = waiting-bg ] && [ "$(quiet)" -gt 1800 ] && ! screen_bg && { st=stalled; break; }
       # 工具跑了一小時 transcript 都沒動、畫面也沒有計時中的東西：多半是行程卡死
       [ "$st" = busy ] && [ "$(quiet)" -gt 3600 ] && ! screen_bg && { st=stalled; break; } ;;
    *) [ "$(quiet)" -gt 120 ] && break ;;
  esac
  sleep 30
done
echo "state=$st"
PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 45
