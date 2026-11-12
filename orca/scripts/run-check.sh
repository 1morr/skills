# 用法：bash run-check.sh <指令...>  —— 跑檢查；看起來是機器原生崩潰就記一筆、原樣重跑一次，回傳最後一次的 exit code
# 崩潰的判準：Git Bash 把 0xC0000005 / 0xC000001D 換成 139 / 132；包在 pre-commit、pnpm 裡時只看得到輸出裡的碼或字樣。
# 崩潰記到 $CRASH_LOG（預設 ~/.claude/crash-log.tsv）：時間、exit、命中的字樣、cwd、指令，可以直接給修電腦的人看。
# 崩潰不算測試偶發：不進 ledger 的偶發計次、不為它開修復票。重跑仍崩就是真的失敗，照常處理。
LOG=${CRASH_LOG:-$HOME/.claude/crash-log.tsv}
SIG='3221225477|3221225501|0xC0000005|0xC000001D|Windows fatal exception: access violation|Fatal error in .*, line [0-9]+|Check failed: '
OUT=$(mktemp)
for attempt in 1 2; do
  "$@" 2>&1 | tee "$OUT"; rc=${PIPESTATUS[0]}
  [ "$rc" -eq 0 ] && break
  hit=$(grep -oE "$SIG" "$OUT" | head -1)
  [ -z "$hit" ] && { [ "$rc" -eq 139 ] || [ "$rc" -eq 132 ]; } && hit="exit $rc"
  [ -z "$hit" ] && break
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "$rc" "$hit" "$PWD" "$*" >> "$LOG"
  [ "$attempt" -eq 1 ] && echo "CRASH-RETRY: $hit (rc=$rc), logged to $LOG; rerunning once"
done
rm -f "$OUT"
exit "$rc"
