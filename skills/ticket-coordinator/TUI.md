# 讀畫面、按鍵、等待、額度：已知行為

`ticket-coordinator` 的參考檔。`<S>` 是 skill 的 `scripts/` 目錄。

## 開 session

- 剛啟動的 Claude Code 在 tui-idle 成立後幾秒內仍會吞掉輸入，`accepted: true` 照樣回來（v2.1.284 實測）。
  `launch.sh` 因此多等 15 秒，送出後沒展開、畫面上又看不到票路徑，就補送，最多三次。
- 仍然印 `expanded: NO`：先讀畫面。停在空輸入框，就在同一個終端補送一次，不必關掉重開。

## 跨平台

- 腳本 source `py.sh` 選 Python：先試 `python3` 再試 `python`，都實際跑一次（macOS 沒有 `python`，Windows 的
  `python3` 可能是 Microsoft Store 的空殼）。你自己手動叫 `scr.py` / `state.py` 時同理，Windows 上沒有 `python3` 就用 `python`。
- 腳本要在 macOS 內建的 bash 3.2 跑：變數後面緊貼中文要寫 `${var}`（3.2 會把中文吃進變數名，`set -u` 下直接退出）；
  不用 GNU 專屬的 `stat -c`、`touch -d`、`sed -i` 等，檔案時間交給 `py.sh` 的 `age`。改完在 macOS 上跑 `selftest.sh`。
- Claude Code 的 Bash 工具可能跑在 zsh：沒加引號的 `$var` 不分詞，`for t in "t02 a.md" "t05 b.md"; do set -- $t`
  會把整串當成一個參數，worktree 名字變成整條票路徑。開多張票就一張一行呼叫 `new-ticket.sh`。
- 收票只關 worktree 路徑完全相同的終端（`terminals_in.py`）：比對前統一斜線、Windows 磁碟代號不分大小寫，`t07` 不會比中 `t07b`。

## 讀畫面

- 同一個 worktree 裡常有 Orca 自動開的 shell 終端（`orca terminal list` 會列出兩個），送訊息一律用 `new-ticket.sh` 印出的 `handle=`，不要用 worktree 路徑反查：查到 shell 就會把整段話當指令送進 zsh。

- `python3 <S>/scr.py <handle> [行數]`：修正 mojibake、壓縮分隔線、只印非空行。`status: running` 只代表終端
  還在，不代表子 session 在忙。
- 畫面停在捲動模式（出現 `Jump to bottom`、看不到 spinner）：送 Ctrl+End
  `orca terminal send --terminal <h> --text $'\033[1;5F' --json`。
- 不要印子 session 的原始 jsonl 行，會灌爆你的上下文；要查就用 `grep -c` / `grep -o` 印短結果。

## 等待

- 以 transcript 為準，不以畫面為準：終端停在捲動模式時畫面不會更新，曾把還在跑的票誤判成做完。
  `python3 <S>/state.py <jsonl>` 印 `done`（回合結束、背景工作都回來了或被它自己停掉）、`busy`（含並行的工具
  只回來一部分，例如 vitest 回來了、pytest 還在跑）/ `waiting-bg`、
  `asking`（停在 AskUserQuestion 等你）、`unknown`（額度、API 錯誤、被中斷，讀畫面判斷）。
- `waitbg.sh` 每 30 秒問一次 `state.py`，`done` 而畫面上還有 shell / monitor 計數時繼續等（Monitor 認不出來）；
  `waiting-bg` 半小時、`busy` 一小時沒動靜，畫面也沒有在跑的東西時以 `state=stalled` 返回：多半是它停了背景
  工作卻沒留紀錄，或行程卡死。
- `state=done-bg`：回合結束，畫面卻還掛著 shell / 子代理計數、transcript 一小時沒動。多半是殘留的背景程序
  （票 22 是子代理留下的 `find /` 跑了 7 小時，等待因此卡了 6 小時）。叫子 session 查清楚、收掉，確認
  `git status` 乾淨再驗收：收尾刪 worktree 會丟掉背景程序還沒 commit 的改動。
- `state=no-response`：帶了 `sent`，送出後 5 分鐘 transcript 都沒新寫入。讀畫面：停在輸入框就是字被吞了，補送一次。
- `state=heads-up`：畫面出現一則還沒回報過的 Heads up，子 session 多半還在做；下一行 `headsup=` 是摘要。照下面「Heads up」的分級處理，
  處理完照原樣重新掛等待（送過訊息就加 `sent`）。同一則不會再叫醒你；任何 `state=` 返回時畫面上有 Heads up，也會多印一行 `headsup=`。
- 改了 `state.py`、`run-check.sh`、`merge-ticket.sh`、`push-ci.sh`、`waitbg.sh`、`quota.sh` 就跑 `bash <S>/selftest.sh`，要印 `ALL OK`。
- 背景等待的通知是 `failed` 或 `stopped`：先讀輸出。常見原因有下面兩種：
  - session 被關掉或重開過：重新掛等待。
  - Orca 自動更新，`runtime_unavailable` 或 `orca` 指令找不到：背景迴圈等到 `orca terminal list --json` 能用，
    再讀子終端。它通常活著。
- 背景 shell 被 Claude Code 以記憶體壓力回收：徵得使用者同意後，在 `~/.claude/settings.json` 的 env 設
  `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`。不能設就改用 CronCreate，一次性約 20 分鐘叫醒自己。

## 回答 AskUserQuestion

- 按鍵一律 `orca terminal send --terminal <h> --text <鍵> --json`，不加 `--enter`。每按一次就讀畫面核對。
- 游標預設在第 1 項，通常就是 Recommended：送 Enter（`$'\r'`）。
- 帶預覽的版面（右側有方框示意）數字鍵無效，移動用 ↓（`$'\033[B'`）。
- 多題分頁：每題 Enter 後會跳下一題。最後出現 `Review your answers` / `Submit answers` 時，再送一次 Enter。
- 自訂答案：先用 ↓ 移到 `Type something.`，送出整段文字（不加 `--enter`），讀畫面確認整句都在，再送 Enter。
- 代答之後把「題目 → 選項 → 理由」寫進 ledger。

## Heads up

- Claude Code 會在子 session 畫面底部放一行 `✦ Heads up · <摘要>`，下面是 `1: Learn more   2: Knew this already   0: Dismiss`。摘要只有一句，完整內容（原因、推測的後果、建議）要展開才看得到。
- 展開：輸入框是空的時候送 `1`（不加 `--enter`），再 `scr.py <handle> 40` 讀。展開後選項變成 `1: Understood   2: Chat in main session   0: Dismiss`，讀完送 `1` 收起。看到的已經是後者，代表有人展開過，直接讀畫面上的內容；不要再按 `1`，那會把它收掉。
- 子 session 停在 AskUserQuestion 時先答題，等它回到空輸入框再展開：題目開著時數字鍵會被當成選項。
- 內容不在子 session 的 transcript（`grep -c 'Heads up' <jsonl>` 是 0）：要它處理就照 SKILL.md「每張票」第 3 步把原文貼給它。
- 一則沒關掉，下一則不會出來（畫面上的不會被新的蓋掉）。所以每一則都要盡快收掉，不能留到子 session 停下。
- `waitbg.sh` 每次輪詢都看畫面，新的一則以 `state=heads-up` 叫醒你，子 session 可能還在做。每一則都照這個順序：
  1. 展開（送 `1`），讀完整內容，把原文與時間記進 ledger 那張票的「Heads up」。
  2. 收起（送 `1` Understood），讀畫面確認那一行不見了，再重新掛等待。
  3. 分兩級決定什麼時候處理：
     - **馬上處理**：涉及刪檔或丟掉改動、破壞性 git、push 或對外寫入、金鑰或個人資料外洩、改隱私或安全約定、
       超出票的範圍。查證後屬實就把原文貼給子 session（它在忙時送出的訊息會排隊，最晚在它停下時讀到）。
     - **其他**：等子 session 停下（說做完或來問）時，照 ledger 的原文查證、處理。中途的 Heads up 常是它還沒定案的想法，
       停下時多半已經自己改掉（曾有一則說「改成無痕時交出前文」，最後程式碼沒改）；改掉了就在 ledger 註明「已不適用」。
- 子 session 在忙時，送一次 `1` 也會展開，展開後照樣能收起（v2.1.322 實測）。
- 視窗太矮時展開的內容會被截斷（使用者用手機開 Orca，終端只有 27–31 列），底部只剩 `↓ N more` / `↑ N more`，看不到選項那一行：
  - 用 `orca terminal read --terminal <h> --screen --json` 讀實際畫面，從 `tail` 的索引算出面板在第幾列（從 1 起算）；
    `scr.py` 讀的是輸出流，看不出截在哪。
  - 往下捲送 SGR 滑鼠滾輪，座標要落在面板內：`$'\033[<65;20;<列>M'`（往上捲用 `64`）。每次捲 3 行，一次只送一個，
    等 3–4 秒再讀；連送三個會沒反應。↓、PageDown 都沒用。
  - 捲到看得見 `1: Understood` 後，只送一次 `1`。
- 按鍵沒反應時不要連送：曾在面板沒反應時連送 `1`、`0`、↓、PageDown，之後面板就卡住，捲到選項再按 `1`、用滑鼠點都收不起來，
  最後是使用者手動關掉的。沒反應就停手，原文記進 ledger，請使用者在畫面上點掉。

## 額度

- 你和子 session 共用同一份額度。子 session 停在 `usage limit` / `continuing automatically at HH:MM` 時，它也算
  idle，對它掛 tui-idle 會立刻返回、原地空轉。改成背景 `sleep` 到重置時間之後幾分鐘，再讀畫面：
  - 它已經自己接上：照常掛 `waitbg.sh`。
  - 還停在同一個訊息：送一次「繼續，從中斷處接著做，保留已完成的部分」。
  - 畫面上找不到重置時間：`sleep 1800` 後照上面兩條判斷。
- 你自己撞到上限也會停，重置後 Claude Code 會自動接著做：醒來先讀 ledger。
- 開票前的額度門檻（SKILL.md 的參數）：`bash <S>/quota.sh <5h 門檻> <7d 門檻>`，印 `gate=open|closed|unknown src=… sleep=<秒>`。
  - 來源先讀 `~/.claude/rate-limits.json`：Claude Code 每次更新狀態列都把 `rate_limits`（已用百分比、刷新時間）交給狀態列指令，
    讓指令順手存檔（寫 `{"at": <現在>, "rate_limits": …}`，先寫暫存檔再改名），10 分鐘內寫過才算數。沒有這個檔或太舊，
    才退回讀你終端狀態列的畫面（要顯示 `5h 60% ↻ 18m · 7d 90% ↻ 4d16h` 這種格式）。
  - `closed`：不開新票，背景 `sleep` 它印的秒數（超過 3600 就先睡 3600）再問；在跑的票照常等、照常驗收合併。
  - `unknown`：兩個來源都讀不到。有門檻時當成不能開（`sleep=600`），連續 3 次都是 `unknown` 就停下問使用者
    （多半是狀態列設定被改掉，例如 Orca 更新時重寫了 `statusLine`）；不要不設防地照常開票。
