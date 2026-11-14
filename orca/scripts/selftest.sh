# 用法：bash selftest.sh  —— 改了 state.py、py.sh、headsup.py、terminals_in.py、run-check.sh、merge-ticket.sh、push-ci.sh、waitbg.sh、quota.sh、save-rate-limits.sh 之後跑；每個判準都雙向驗：該紅的紅、無關的改動不紅
D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"; X=$(mktemp -d); fail=0
ok() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: got '$2' want '$3'"; fail=1; fi; }
# GNU `touch -d '-5 minutes'` 在 macOS 不認，改用 Python 設 mtime
old() { "$PY" -c 'import os, sys, time; t = time.time() - 300; os.utime(sys.argv[1], (t, t))' "$1"; }

# ---- state.py
A='{"type":"assistant","message":{"stop_reason":"end_turn","content":[{"type":"text","text":"hi"}]}}'
TD='{"type":"system","subtype":"turn_duration"}'
BGL='{"type":"user","message":{"content":[{"type":"tool_result","content":"Command running in background with ID: b1x2. Output is being written"}]}}'
AG='{"type":"user","message":{"content":[{"type":"tool_result","content":[{"type":"text","text":"Async agent launched successfully.\nagentId: a9f8"}]}]}}'
NOTE() { echo "{\"type\":\"user\",\"message\":{\"content\":\"<task-notification>\\n<task-id>$1</task-id>\\n<status>completed</status>\\n</task-notification>\"}}"; }
ASK='{"type":"assistant","message":{"stop_reason":"tool_use","content":[{"type":"tool_use","name":"AskUserQuestion","input":{}}]}}'
TOOL='{"type":"assistant","message":{"stop_reason":"tool_use","content":[{"type":"tool_use","name":"Bash","input":{}}]}}'
st() { printf '%s\n' "$@" > "$X/s.jsonl"; old "$X/s.jsonl"; "$PY" "$D/state.py" "$X/s.jsonl"; }
ok "state done"                      "$(st "$A" "$TD")" done
ok "state ignores junk lines"        "$(st "$A" 'not json' '' "$TD")" done
ok "state waiting on bg shell"       "$(st "$BGL" "$A" "$TD")" waiting-bg
ok "state waiting on subagent"       "$(st "$AG" "$A" "$TD")" waiting-bg
ok "state bg finished"               "$(st "$BGL" "$AG" "$(NOTE b1x2)" "$(NOTE a9f8)" "$A" "$TD")" done
STOP='{"type":"user","message":{"content":[{"type":"tool_result","content":"{\"message\":\"Successfully stopped task: b1x2 (uv run x)\"}"}]}}'
ok "state bg stopped by TaskStop"    "$(st "$BGL" "$STOP" "$A" "$TD")" done
ok "state one of two bg finished"    "$(st "$BGL" "$AG" "$(NOTE b1x2)" "$A" "$TD")" waiting-bg
ok "state asking"                    "$(st "$A" "$ASK")" asking
ok "state tool running"              "$(st "$A" "$TOOL")" busy
# 並行的兩個工具先回來一個、另一個（例如 pytest）還在跑：最後一行是 tool_result，不是 unknown
RES='{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"Tests 2199 passed"}]}}'
ok "state parallel tool still running" "$(st "$A" "$TOOL" "$TOOL" "$RES")" busy
ok "state unknown (no turn end)"     "$(st "$A")" unknown
printf '%s\n' "$A" "$TD" > "$X/s.jsonl"
ok "state recent write is busy"      "$("$PY" "$D/state.py" "$X/s.jsonl")" busy

# ---- py.sh
ok "py.sh picked a python 3"           "$("$PY" -c 'import sys; print(sys.version_info[0])')" 3
touch "$X/a"; old "$X/a"; a=$(age "$X/a"); [ "$a" -ge 299 ] && [ "$a" -le 330 ]; ok "age of a 5-minute-old file" $? 0
touch "$X/a"; [ "$(age "$X/a")" -le 5 ]; ok "age of a fresh file" $? 0

# ---- headsup.py（讀 You should know mod 的狀態檔；只認 offer / explained 兩種帶內容的 view，而且只看自己的 session）
HS="$X/ysk.json"
hstore() { "$PY" -c 'import json, sys; json.dump({"sessions": json.loads(sys.argv[1]), "seen": [], "known": []}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)' "$1" "$HS"; }
hu() { HEADSUP_STORE="$HS" "$PY" "$D/headsup.py" "$@" "$X/me.jsonl"; }
OFFER='{"kind":"offer","line":"主代理刪了 tests。.","explanation":"**刪了 tests**\n- 原因一\n- 原因二","shownAt":1762900000000}'
hstore "[{\"id\":\"other\",\"view\":$OFFER},{\"id\":\"me\",\"tag\":\"Heads up\",\"view\":$OFFER}]"
ok "headsup offer summary"                 "$(hu --summary)" "主代理刪了 tests。."
ok "headsup offer full text"               "$(hu | sed -n '/^text:$/,$p' | tr '\n' '|')" "text:|**刪了 tests**|- 原因一|- 原因二|"
ok "headsup offer tag and kind"            "$(hu | grep -E '^(tag|kind)=' | tr '\n' ' ')" "tag=Heads up kind=offer "
hstore '[{"id":"me","view":{"kind":"explained","line":"L。","text":"展開後的全文","iteration":1,"shownAt":1}}]'
ok "headsup explained uses text"           "$(hu | tail -1)" "展開後的全文"
hstore "[{\"id\":\"other\",\"view\":$OFFER},{\"id\":\"me\",\"askedTurn\":\"t\"}]"
hu --summary >/dev/null; ok "headsup another session's offer is not mine" $? 1
hstore '[{"id":"me","view":{"kind":"asked","line":"L。","shownAt":1}}]'
hu --summary >/dev/null; ok "headsup dismissed (asked) is not open" $? 1
hstore '[]'
hu --summary >/dev/null; ok "headsup no entry is none"     $? 1
HEADSUP_STORE="$X/missing.json" "$PY" "$D/headsup.py" --summary "$X/me.jsonl" >/dev/null; ok "headsup missing store is unavailable" $? 2
echo '{"sessions": {"me": {}}}' > "$HS"
hu --summary >/dev/null; ok "headsup unknown shape is unavailable" $? 2
hstore '[{"id":"me","view":{"kind":"offer","explanation":"x"}}]'
hu --summary >/dev/null; ok "headsup offer without a line is unavailable" $? 2

# ---- terminals_in.py（close-worktree.sh 只關這個 worktree 的終端）
TL='{"result":{"terminals":[{"handle":"term_a","worktreePath":"/w/t07"},{"handle":"term_b","worktreePath":"/w/t07b"},{"handle":"term_c","worktreePath":"/w/t07/"}]}}'
ok "terminals: exact worktree only"     "$(echo "$TL" | W=/w/t07 "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_a term_c "
ok "terminals: sibling with same prefix" "$(echo "$TL" | W=/w/t07b "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_b "
TW='{"result":{"terminals":[{"handle":"term_w","worktreePath":"c:\\ws\\t07"},{"handle":"term_x","worktreePath":"C:\\ws\\t07b"}]}}'
ok "terminals: windows path, drive case" "$(echo "$TW" | W=C:/ws/t07 "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_w "

# ---- run-check.sh
export CRASH_LOG="$X/crash.tsv"; : > "$CRASH_LOG"
flaky() { echo 0 > "$X/n"; cat > "$X/cmd.sh" <<EOF
n=\$(cat "$X/n"); echo \$((n+1)) > "$X/n"
[ "\$n" -lt $1 ] && { echo "$2"; exit $3; }
echo passed
EOF
}
flaky 1 'Process exited. Exit code: 3221225501' 1
bash "$D/run-check.sh" bash "$X/cmd.sh" > "$X/out"; rc=$?
ok "crash in output retried and passes" "$rc/$(cat "$X/n")/$(wc -l < "$CRASH_LOG" | tr -d ' ')" 0/2/1
grep -q CRASH-RETRY "$X/out"; ok "crash retry announced" $? 0
flaky 1 '' 139
bash "$D/run-check.sh" bash "$X/cmd.sh" > /dev/null; ok "exit 139 retried" "$?/$(cat "$X/n")" 0/2
flaky 9 'AssertionError: expected 3 got 4' 1
bash "$D/run-check.sh" bash "$X/cmd.sh" > /dev/null; ok "ordinary failure not retried" "$?/$(cat "$X/n")/$(wc -l < "$CRASH_LOG" | tr -d ' ')" 1/1/2
flaky 9 'eslint 0xC0000005' 1
bash "$D/run-check.sh" bash "$X/cmd.sh" > /dev/null; ok "crash twice stays red" "$?/$(cat "$X/n")/$(wc -l < "$CRASH_LOG" | tr -d ' ')" 1/2/4

# ---- merge-ticket.sh
R="$X/repo"; W="$X/wt"; git init -q -b main "$R"; cd "$R"
git config user.email t@t; git config user.name t
mkdir -p issues docs; printf '# 01\n**Status:** ready\n- [ ] works\n' > issues/01-x.md; echo a > docs/progress.md
git add -A; git commit -qm "chore: init"; git worktree add -q -b t01 "$W"; cd "$W"
echo b > f.txt; git add f.txt; git commit -qm "feat: Add a thing that is described with far too many words for one subject"
mt() { (cd "$R" && REQUIRE=docs/progress.md bash "$D/merge-ticket.sh" "$R" "$W" issues/01-x.md "merge: ticket 01 x" 2>&1); }
out=$(mt); ok "not ready exits 1" $? 1
for want in "標題" "Conventional" "Status 不是 done" "沒勾" "docs/progress.md"; do
  echo "$out" | grep -q "$want"; ok "not ready reports: $want" $? 0
done
git reset -q --soft HEAD~1; git commit -qm "feat: add a thing"
printf '# 01\n**Status:** done\n- [x] works\n' > issues/01-x.md; echo c >> docs/progress.md; git commit -qam "docs: close ticket 01"
echo dirty >> "$R/docs/progress.md"
out=$(mt); ok "dirty main dir blocks merge" $? 1
echo "$out" | grep -q "主目錄有未提交"; ok "dirty main dir reported" $? 0
git -C "$R" checkout -q -- docs/progress.md; touch "$R/untracked.tmp"
out=$(mt); ok "ready ticket merges (untracked file in main is fine)" $? 0
ok "merge commit made" "$(git -C "$R" log -1 --format=%s)" "merge: ticket 01 x"

# ---- push-ci.sh（假的 gh；bare repo 的 hook 記下 push 的時間點）
P="$X/pc"; mkdir -p "$P/bin"; git init -q --bare "$P/remote.git"; git clone -q "$P/remote.git" "$P/repo" 2>/dev/null
LOG="$P/log"; : > "$LOG"; printf '#!/bin/sh\necho push >> "%s"\n' "$LOG" > "$P/remote.git/hooks/pre-receive"; chmod +x "$P/remote.git/hooks/pre-receive"
cat > "$P/bin/gh" <<EOF
#!/bin/sh
case "\$*" in
  *"--branch"*) n=\$(grep -c list "$LOG"); echo list >> "$LOG"; [ "\$n" -eq 0 ] && { echo 'Get "https://api.github.com/...": EOF' >&2; exit 1; }; exit 0 ;;
  *"--commit"*) echo 7 ;;
  *"--json status"*) echo completed ;;
  *"--json conclusion"*) echo success ;;
esac
EOF
chmod +x "$P/bin/gh"
(cd "$P/repo" && git config user.email t@t && git config user.name t && git commit -q --allow-empty -m "chore: x" && git push -q origin HEAD:main 2>/dev/null; git branch -q -M main)
: > "$LOG"; (cd "$P/repo" && git commit -q --allow-empty -m "chore: y")
# 另一個 push-ci 拿著鎖（pid 還活著）：這一個要等，不能先去問 gh 或 push
sleep 30 & holder=$!; L="$P/repo/.git/push-ci.lock"; mkdir "$L"; echo $holder > "$L/pid"
PATH="$P/bin:$PATH" PUSH_CI_POLL=1 bash "$D/push-ci.sh" "$P/repo" > "$P/out" 2>&1 & pc=$!
sleep 3; ok "push-ci waits for the lock holder" "$(wc -l < "$LOG" | tr -d ' ')" 0
kill $holder 2>/dev/null; wait $holder 2>/dev/null; wait $pc; rc=$?
ok "push-ci proceeds after the holder dies" "$rc" 0
# gh 第一次回錯誤時不能當成「沒有在跑的 run」直接 push（新 push 會取消上一張票的 CI）
ok "push-ci retries a failed run list before pushing" "$(tr '\n' ' ' < "$LOG")" "list list push "
grep -q "ci=success" "$P/out"; ok "push-ci reports the run" $? 0
[ -d "$L" ]; ok "push-ci releases the lock" $? 1

# ---- waitbg.sh（假的 orca 印出指定的畫面；每個情境都限時，舊版會卡住的那幾個靠限時判出來）
Wb="$X/wb"; mkdir -p "$Wb/bin"; SCREEN="$Wb/screen.txt"
cat > "$Wb/bin/orca" <<EOF
#!/bin/sh
"$PY" -c 'import json,sys; print(json.dumps({"ok": True, "result": {"terminal": {"status": "running", "tail": open(sys.argv[1], encoding="utf-8").read().splitlines()}}}))' "$SCREEN"
EOF
chmod +x "$Wb/bin/orca"
# 跑 waitbg 最多 $1 秒，印它的 state= 那一行（沒返回就印 TIMEOUT）
wb() { secs=$1; shift
  PATH="$Wb/bin:$PATH" WAITBG_POLL=1 STATE_RECENT_SECS=1 WAITBG_HU_SEEN="$Wb/seen" HEADSUP_STORE="${HEADSUP_STORE:-$Wb/nostore.json}" \
    bash "$D/waitbg.sh" term_x "$Wb/s.jsonl" "$@" > "$Wb/out" 2>&1 & p=$!
  for i in $(seq 1 "$secs"); do kill -0 $p 2>/dev/null || break; sleep 1; done
  if kill -0 $p 2>/dev/null; then kill $p 2>/dev/null; wait $p 2>/dev/null; echo TIMEOUT; else wait $p; grep -m1 '^state=' "$Wb/out"; fi; }
printf '%s\n' "$A" "$TD" > "$Wb/s.jsonl"; old "$Wb/s.jsonl"
echo '❯' > "$SCREEN"
ok "waitbg done returns at once"                   "$(wb 5)" "state=done"
# 票 22：回合結束了，畫面卻還掛著子代理留下的 shell，舊版一直等
echo '  ⏵⏵ bypass permissions on · 1 shell' > "$SCREEN"
ok "waitbg done with a lingering shell keeps waiting while fresh" "$(WAITBG_BG_STALE=600 wb 4)" "TIMEOUT"
ok "waitbg done with a lingering shell returns once stale"        "$(WAITBG_BG_STALE=60 wb 5)" "state=done-bg"
# 送出新指示後馬上掛等待：transcript 還是上一輪的 done，不能算這一次做完
echo '❯' > "$SCREEN"
ok "waitbg sent: old done is not this turn"        "$(WAITBG_SENT_TIMEOUT=3 wb 8 sent)" "state=no-response"
( sleep 2; printf '%s\n' "$A" "$TD" >> "$Wb/s.jsonl" ) & writer=$!
ok "waitbg sent: a new turn after the send counts" "$(WAITBG_SENT_TIMEOUT=30 wb 15 sent)" "state=done"
wait $writer 2>/dev/null
# Heads up（讀不到狀態檔、退回讀畫面）：子 session 還在跑工具時跳出來的新一則要叫醒；回報過的同一則不再叫醒；換一則再叫醒；可關
printf '%s\n' "$A" "$TOOL" > "$Wb/s.jsonl"; old "$Wb/s.jsonl"; : > "$Wb/seen"
printf '%s\n' '✻ Working…' '✦ Heads up · 主代理刪了整個 tests 目錄。' '  1: Learn more   2: Knew this already   0: Dismiss' '❯' > "$SCREEN"
ok "waitbg heads-up wakes while busy"              "$(wb 5)" "state=heads-up"
ok "waitbg heads-up prints the summary"            "$(grep -m1 '^headsup=' "$Wb/out")" "headsup=主代理刪了整個 tests 目錄。"
ok "waitbg same heads-up does not wake again"      "$(wb 3)" "TIMEOUT"
printf '%s\n' '✻ Working…' '✦ Heads up · 主代理開了 SIMD，舊瀏覽器載不起來。' '❯' > "$SCREEN"
ok "waitbg a different heads-up wakes"             "$(wb 5)" "state=heads-up"
printf '%s\n' '✻ Working…' '✦ Heads up · 第三則' '❯' > "$SCREEN"
ok "waitbg heads-up detection can be turned off"   "$(WAITBG_HEADSUP=0 wb 3)" "TIMEOUT"
printf '%s\n' "$A" "$TD" > "$Wb/s.jsonl"; old "$Wb/s.jsonl"
ok "waitbg done with a heads-up still says done"   "$(WAITBG_HEADSUP=0 wb 5)" "state=done"
grep -qxF '第三則' "$Wb/seen"; ok "waitbg records the heads-up shown at return" $? 0
# Heads up（讀狀態檔）：不看畫面也叫醒、印出全文；狀態檔說沒有就不看畫面
WS="$Wb/ysk.json"
wstore() { "$PY" -c 'import json, sys; json.dump({"sessions": json.loads(sys.argv[1])}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)' "$1" "$WS"; }
printf '%s\n' "$A" "$TOOL" > "$Wb/s.jsonl"; old "$Wb/s.jsonl"; : > "$Wb/seen"
printf '%s\n' '✻ Working…' '❯' > "$SCREEN"
wstore '[{"id":"s","tag":"Heads up","view":{"kind":"offer","line":"主代理改了公開 API。.","explanation":"**公開 API 變了**\n- 呼叫端會壞","shownAt":1}}]'
ok "waitbg file heads-up wakes without the screen" "$(HEADSUP_STORE="$WS" wb 5)" "state=heads-up"
ok "waitbg file heads-up prints the summary"       "$(grep -m1 '^headsup=' "$Wb/out")" "headsup=主代理改了公開 API。."
ok "waitbg file heads-up says where it came from"  "$(grep -m1 '^headsup-src=' "$Wb/out")" "headsup-src=file"
grep -qxF -- '- 呼叫端會壞' "$Wb/out"; ok "waitbg file heads-up prints the full text" $? 0
ok "waitbg file same heads-up does not wake again" "$(HEADSUP_STORE="$WS" wb 3)" "TIMEOUT"
wstore '[{"id":"s","view":{"kind":"asked","line":"主代理改了公開 API。.","shownAt":1}}]'
printf '%s\n' '✻ Working…' '✦ Heads up · 畫面上殘留的一則' '❯' > "$SCREEN"
ok "waitbg file says none, the screen is not used" "$(HEADSUP_STORE="$WS" wb 3)" "TIMEOUT"

# ---- quota.sh（先讀狀態列存下的檔，太舊或沒有才讀畫面；同一個假的 orca）
QF="$Wb/rl.json"
qt() { PATH="$Wb/bin:$PATH" QUOTA_FILE="$QF" bash "$D/quota.sh" "$@" term_x; }
fields() { sed -E 's/ (5h|7d)(_reset)?=[^ ]*//g'; }   # 只留 gate、src、sleep
rl() { "$PY" -c 'import json, sys, time; n = time.time(); json.dump({"at": int(n) - int(sys.argv[1]), "rate_limits": {"five_hour": {"used_percentage": 60, "resets_at": int(n) + 1020}, "seven_day": {"used_percentage": 90, "resets_at": int(n) + 400000}}}, open(sys.argv[2], "w"))' "$1" "$QF"; }
echo '  QIM main  ·  Opus  ·  5h 40% ↻ 17m · 7d 50% ↻ 4d16h' > "$SCREEN"
rl 5
ok "quota fresh file below the gate is open"  "$(qt 80 0 | fields)" "gate=open src=file sleep=0"
ok "quota file 5h gate sleeps to its reset"   "$(qt 60 0 | fields | sed -E 's/sleep=1(19[0-9]|20[0-9])$/sleep=~1200/')" "gate=closed src=file sleep=~1200"
ok "quota file 7d gate"                       "$(qt 0 90 | fields | cut -d' ' -f1)" "gate=closed"
rl 3600
ok "quota stale file falls back to the screen" "$(qt 60 0 | fields)" "gate=open src=screen sleep=0"
rm -f "$QF"
echo '  QIM main  ·  Opus  ·  5h 60% ↻ 17m · 7d 90% ↻ 4d16h' > "$SCREEN"
ok "quota screen below the 5h gate is open"   "$(qt 80 0)" "gate=open src=screen 5h=60 5h_reset=17m 7d=90 7d_reset=4d16h sleep=0"
ok "quota no gates is open"                   "$(qt 0 0 | fields)" "gate=open src=screen sleep=0"
ok "quota screen 5h gate sleeps to reset"     "$(qt 60 0 | fields)" "gate=closed src=screen sleep=1200"
ok "quota screen 7d gate uses the 7d reset"   "$(qt 0 85 | fields)" "gate=closed src=screen sleep=403380"
echo '  QIM main  ·  Opus' > "$SCREEN"
ok "quota unknown with a gate holds off"      "$(qt 80 0 | fields)" "gate=unknown src=none sleep=600"
ok "quota unknown without gates does not wait" "$(qt 0 0 | fields)" "gate=unknown src=none sleep=0"

# ---- save-rate-limits.sh（狀態列指令裡的一段：存 rate_limits、原樣轉交 JSON；quota.sh 讀得回來）
SF="$X/saved.json"; PAY='{"model":"x","rate_limits":{"five_hour":{"used_percentage":61,"resets_at":'$(( $(date +%s) + 600 ))'}}}'
ok "save-rate-limits passes the payload through" "$(printf '%s' "$PAY" | QUOTA_FILE="$SF" sh "$D/save-rate-limits.sh")" "$PAY"
ok "save-rate-limits output is read by quota.sh"  "$(PATH="$Wb/bin:$PATH" QUOTA_FILE="$SF" bash "$D/quota.sh" 60 0 term_x | fields | cut -d' ' -f1-2)" "gate=closed src=file"
before=$(cat "$SF")
ok "save-rate-limits passes a payload without limits" "$(printf '%s' '{"model":"x"}' | QUOTA_FILE="$SF" sh "$D/save-rate-limits.sh")" '{"model":"x"}'
ok "save-rate-limits keeps the old file without limits" "$(cat "$SF")" "$before"
ok "save-rate-limits survives junk input"            "$(printf 'not json' | QUOTA_FILE="$SF" sh "$D/save-rate-limits.sh"; echo " rc=$?")" "not json rc=0"

rm -rf "$X"; [ $fail -eq 0 ] && echo "ALL OK"; exit $fail
