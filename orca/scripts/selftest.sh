# 用法：bash selftest.sh  —— 改了 py.sh、headsup.py、terminals_in.py、run-check.sh、merge-ticket.sh、push-ci.sh、quota.sh、save-rate-limits.sh 之後跑；每個判準都雙向驗：該紅的紅、無關的改動不紅
D="$(cd "$(dirname "$0")" && pwd)"; . "$D/py.sh"; X=$(mktemp -d); fail=0
ok() { if [ "$2" = "$3" ]; then echo "ok   $1"; else echo "FAIL $1: got '$2' want '$3'"; fail=1; fi; }
# GNU `touch -d '-5 minutes'` 在 macOS 不認，改用 Python 設 mtime
old() { "$PY" -c 'import os, sys, time; t = time.time() - 300; os.utime(sys.argv[1], (t, t))' "$1"; }

# ---- py.sh
ok "py.sh picked a python 3"           "$("$PY" -c 'import sys; print(sys.version_info[0])')" 3
touch "$X/a"; old "$X/a"; a=$(age "$X/a"); [ "$a" -ge 299 ] && [ "$a" -le 330 ]; ok "age of a 5-minute-old file" $? 0
touch "$X/a"; [ "$(age "$X/a")" -le 5 ]; ok "age of a fresh file" $? 0

# ---- headsup.py（僅限 Claude Code worker；讀 You should know mod 的狀態檔，支援 jsonl/session id 與 --worktree）
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

# --worktree 模式：以 worktree 路徑反查 ~/.claude/projects/<sanitized>/*.jsonl
CCFG="$X/ccfg"; WT="/tmp/demo/wt-01"; PDIR="$CCFG/projects/-tmp-demo-wt-01"
mkdir -p "$PDIR"
: > "$PDIR/old-sid.jsonl"; old "$PDIR/old-sid.jsonl"
: > "$PDIR/new-sid.jsonl"
hstore "[{\"id\":\"new-sid\",\"tag\":\"Heads up\",\"view\":$OFFER}]"
ok "headsup --worktree finds active session" "$(CLAUDE_CONFIG_DIR="$CCFG" HEADSUP_STORE="$HS" "$PY" "$D/headsup.py" --summary --worktree "$WT")" "主代理刪了 tests。."
hstore '[{"id":"new-sid","view":{"kind":"asked","line":"L。","shownAt":1}}]'
CLAUDE_CONFIG_DIR="$CCFG" HEADSUP_STORE="$HS" "$PY" "$D/headsup.py" --summary --worktree "$WT" >/dev/null
ok "headsup --worktree dismissed returns 1" $? 1
CLAUDE_CONFIG_DIR="$CCFG" HEADSUP_STORE="$HS" "$PY" "$D/headsup.py" --summary --worktree "/tmp/demo/empty-wt" >/dev/null
ok "headsup --worktree with no jsonl returns 1" $? 1
CLAUDE_CONFIG_DIR="$CCFG" HEADSUP_STORE="$X/missing.json" "$PY" "$D/headsup.py" --summary --worktree "$WT" >/dev/null
ok "headsup --worktree missing store returns 2" $? 2

# ---- terminals_in.py（close-worktree.sh 只關這個 worktree 的終端；Git Bash 會把環境變數裡的 /w/t07 改寫成 W:/t07，用 MSYS2_ENV_CONV_EXCL 擋掉這個變數）
export MSYS2_ENV_CONV_EXCL=W
TL='{"result":{"terminals":[{"handle":"term_a","worktreePath":"/w/t07"},{"handle":"term_b","worktreePath":"/w/t07b"},{"handle":"term_c","worktreePath":"/w/t07/"}]}}'
ok "terminals: exact worktree only"     "$(echo "$TL" | W=/w/t07 "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_a term_c "
ok "terminals: sibling with same prefix" "$(echo "$TL" | W=/w/t07b "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_b "
TW='{"result":{"terminals":[{"handle":"term_w","worktreePath":"c:\\ws\\t07"},{"handle":"term_x","worktreePath":"C:\\ws\\t07b"}]}}'
ok "terminals: windows path, drive case" "$(echo "$TW" | W=C:/ws/t07 "$PY" "$D/terminals_in.py" | tr '\n' ' ')" "term_w "
unset MSYS2_ENV_CONV_EXCL

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
# 未設 CRASH_LOG 且沒有 ~/.claude/ 時，預設寫進 XDG_STATE_HOME 並自動 mkdir -p
unset CRASH_LOG
flaky 1 '' 139
XDG_STATE_HOME="$X/xdg-state" HOME="$X/no-claude-home" bash "$D/run-check.sh" bash "$X/cmd.sh" > /dev/null; rc=$?
ok "run-check default XDG path creates parent dir" "$rc/$(wc -l < "$X/xdg-state/1morr/crash-log.tsv" | tr -d ' ')" 0/1

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
git commit -q --allow-empty -m "Merge branch 'main' into a-ticket-branch-whose-name-pushes-the-subject-past-72-chars"
echo dirty >> "$R/docs/progress.md"
out=$(mt); ok "dirty main dir blocks merge" $? 1
echo "$out" | grep -q "主目錄有未提交"; ok "dirty main dir reported" $? 0
echo "$out" | grep -q "標題"; ok "git's own merge subject may exceed 72" $? 1
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

# ---- quota.sh（僅限 Claude Code；先讀狀態列存下的檔，太舊或沒有才讀畫面；畫面來自 SCR_SCREEN_FILE）
Qd="$X/qt"; mkdir -p "$Qd"; SCREEN="$Qd/screen.txt"; export SCR_SCREEN_FILE="$SCREEN"
QF="$Qd/rl.json"
qt() { QUOTA_FILE="$QF" bash "$D/quota.sh" "$@" term_x; }
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
ok "save-rate-limits output is read by quota.sh"  "$(QUOTA_FILE="$SF" bash "$D/quota.sh" 60 0 term_x | fields | cut -d' ' -f1-2)" "gate=closed src=file"
before=$(cat "$SF")
ok "save-rate-limits passes a payload without limits" "$(printf '%s' '{"model":"x"}' | QUOTA_FILE="$SF" sh "$D/save-rate-limits.sh")" '{"model":"x"}'
ok "save-rate-limits keeps the old file without limits" "$(cat "$SF")" "$before"
ok "save-rate-limits survives junk input"            "$(printf 'not json' | QUOTA_FILE="$SF" sh "$D/save-rate-limits.sh"; echo " rc=$?")" "not json rc=0"

rm -rf "$X"; [ $fail -eq 0 ] && echo "ALL OK"; exit $fail
