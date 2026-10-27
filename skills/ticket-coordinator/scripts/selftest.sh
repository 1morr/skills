# 用法：bash selftest.sh  —— 改了 state.py、run-check.sh、merge-ticket.sh、push-ci.sh 之後跑；每個判準都雙向驗：該紅的紅、無關的改動不紅
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

# ---- terminals_in.py（close-ticket.sh 只關這個 worktree 的終端）
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

rm -rf "$X"; [ $fail -eq 0 ] && echo "ALL OK"; exit $fail
