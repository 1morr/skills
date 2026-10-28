# 用法：bash waitbg.sh <handle> <子 session 的 jsonl 路徑> [sent]（Bash run_in_background 掛著）
# 子 session 停下來才返回，第一行印 state=…，後面是畫面。判斷以 state.py（transcript）為準；
# 畫面只當補充：transcript 說 done、畫面卻還有背景 shell / monitor 的計數時繼續等（state.py 認不出 Monitor）。
#   sent：剛送出新指示時帶上。transcript 在這支腳本開始之後有新的寫入，才承認 done / asking——
#         否則讀到的是上一輪的 done，會提早返回。WAITBG_SENT_TIMEOUT（預設 300 秒）內都沒寫入就印
#         state=no-response（多半是送出的字被吞了：讀畫面，必要時補送）。
# state= 的值：done、asking、stalled、unknown，以及
#   done-bg      回合結束、畫面還掛著 shell / 子代理計數，而 transcript 已經 WAITBG_BG_STALE（預設 3600）秒沒動：
#                多半是殘留的背景程序（票 22：子代理留下的 `find /` 跑了 7 小時），叫子 session 收掉
#   no-response  見 sent
H=$1; J=$2; SENT=${3:-}; cd "$(dirname "$0")"; . ./py.sh
POLL=${WAITBG_POLL:-30}; BG_STALE=${WAITBG_BG_STALE:-3600}; SENT_TIMEOUT=${WAITBG_SENT_TIMEOUT:-300}
BG='… [(]([0-9]+h )?([0-9]+m )?[0-9]+s|still running|Waiting for [0-9]+ background|· [0-9]+ (shells?|monitors?)'
screen_bg() { PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 16 | grep -qE "$BG"; }
quiet() { age "$J"; }
START=$("$PY" -c 'import time; print(int(time.time()))')
elapsed() { echo $(( $("$PY" -c 'import time; print(int(time.time()))') - START )); }
# transcript 在開始之後有沒有新寫入（mtime 比 START 新）
fresh() { [ "$(quiet)" -lt "$(elapsed)" ]; }
while :; do
  st=$("$PY" state.py "$J"); rc=$?
  if [ -n "$SENT" ] && { [ $rc -eq 0 ] || [ $rc -eq 2 ]; } && ! fresh; then
    [ "$(elapsed)" -ge "$SENT_TIMEOUT" ] && { st=no-response; break; }
    sleep "$POLL"; continue
  fi
  case $rc in
    2) break ;;
    0) screen_bg || break
       [ "$(quiet)" -gt "$BG_STALE" ] && { st=done-bg; break; } ;;
    # 只在等自己的背景工作、畫面又看不到任何在跑的東西，半小時沒動靜：多半是它停了自己的背景工作，交給協調者看
    1) [ "$st" = waiting-bg ] && [ "$(quiet)" -gt 1800 ] && ! screen_bg && { st=stalled; break; }
       # 工具跑了一小時 transcript 都沒動、畫面也沒有計時中的東西：多半是行程卡死
       [ "$st" = busy ] && [ "$(quiet)" -gt 3600 ] && ! screen_bg && { st=stalled; break; } ;;
    *) [ "$(quiet)" -gt 120 ] && break ;;
  esac
  sleep "$POLL"
done
echo "state=$st"
PYTHONIOENCODING=utf-8 "$PY" scr.py "$H" 45
