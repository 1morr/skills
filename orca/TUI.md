# 按鍵、畫面、等待、額度：已知行為

ticket-coordinator、bake-off、review-loop 共用的參考檔。`<O>` 是這個資料夾，腳本在 `<O>/scripts/`，每支開頭寫了用法和輸出；這份只寫腳本開頭沒有的。

## 開 session

- `launch.sh` / `new-ticket.sh` 印 `expanded: NO`：先讀畫面。停在空輸入框是字被吞了，在同一個終端補送一次；其他情況關掉那個終端重開。同一張票連兩次沒展開算卡住。
- `open-worktree.sh` 印 `started: NO`：子 session 沒起來，prompt 是啟動參數帶的，沒有東西可以補送。讀畫面：停在信任資料夾這類提示就答掉、再掛等待；其他情況關掉那個終端重開。同一版連兩次沒起來算卡住。

## 跨平台

- 手動叫 `scr.py`、`state.py`、`headsup.py` 時，Windows 上沒有 `python3` 就用 `python`。
- Claude Code 的 Bash 工具可能跑在 zsh：沒加引號的 `$var` 不分詞，`for t in "t02 a.md" "t05 b.md"; do set -- $t` 會把整串當成一個參數，worktree 名字變成整條票路徑。開多張票就一張一行呼叫 `new-ticket.sh`。
- Git Bash 裡開頭是 `/` 的 `--text` 要加 `MSYS_NO_PATHCONV=1`。

## 讀畫面

- 同一個 worktree 裡常有 Orca 自動開的 shell 終端（`orca terminal list` 會列出兩個）。用 worktree 路徑反查可能查到 shell，整段話會被當指令送進 zsh。
- `python3 <O>/scripts/scr.py <handle> [行數]` 讀畫面。`status: running` 只代表終端還在，不代表子 session 在忙。
- 送出後讀畫面核對：`accepted: true` 只代表輸入被收下，沒反應先讀畫面再決定要不要重送。handle 失效（Orca 重啟後）用 `orca terminal list` 重找，只對新的送。
- 畫面停在捲動模式（出現 `Jump to bottom`、看不到 spinner）：送 Ctrl+End `orca terminal send --terminal <h> --text $'\033[1;5F' --json`。
- 查子 session 的 jsonl 只印短結果（`grep -c` / `grep -o`）：原始行會灌爆你的上下文。

## 等待

`waitbg.sh` 以 transcript 為準，不以畫面為準：終端停在捲動模式時畫面不會更新，曾把還在跑的票誤判成做完。`state=` 各個值的定義在 `waitbg.sh` 和 `state.py` 開頭；返回之後這樣做：

- `unknown`：讀畫面判斷。額度用完見〈額度〉；API 錯誤或被中斷就叫它接著做。
- `stalled`：多半是它停了背景工作卻沒留紀錄，或行程卡死。讀畫面，叫它說明在等什麼、接著做完。
- `done-bg`：多半是殘留的背景程序（曾有子代理留下的 `find /` 跑了 7 小時）。叫子 session 查清楚、收掉，確認 `git status` 乾淨再驗收：收尾刪 worktree 會丟掉背景程序還沒 commit 的改動。
- `no-response`：讀畫面，停在輸入框就是字被吞了，補送一次。
- `heads-up`：照 COORDINATOR.md〈Heads up〉。同一則不會再叫醒你。
- 背景等待的通知是 `failed` 或 `stopped`：先讀輸出。常見原因有下面兩種：
  - session 被關掉或重開過：重新掛等待。
  - Orca 自動更新，`runtime_unavailable` 或 `orca` 指令找不到：背景迴圈等到 `orca terminal list --json` 能用，再讀子終端。它通常活著。
- 背景 shell 被 Claude Code 以記憶體壓力回收：徵得使用者同意後，在 `~/.claude/settings.json` 的 env 設 `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`。不能設就改用 CronCreate，一次性約 20 分鐘叫醒自己。

## 回答 AskUserQuestion

- 按鍵一律 `orca terminal send --terminal <h> --text <鍵> --json`，不加 `--enter`。每按一次就讀畫面核對。
- 游標預設在第 1 項，通常就是 Recommended：送 Enter（`$'\r'`）。
- 帶預覽的版面（右側有方框示意）數字鍵無效，移動用 ↓（`$'\033[B'`）。
- 多題分頁：每題 Enter 後會跳下一題。最後出現 `Review your answers` / `Submit answers` 時，再送一次 Enter。
- 自訂答案：先用 ↓ 移到 `Type something.`，送出整段文字（不加 `--enter`），讀畫面確認整句都在，再送 Enter。

## Heads up

處理的順序在 COORDINATOR.md〈Heads up〉；這裡是按鍵和畫面。

- 畫面底部一行 `✦ Heads up · <摘要>`，下面是 `1: Learn more   2: Knew this already   0: Dismiss`。摘要只有一句，完整內容（原因、推測的後果、建議）在 Learn more 裡。
- 全文用 `python3 <O>/scripts/headsup.py <jsonl>` 讀，不必展開畫面。全文只在掛著時存在，收起後只剩摘要：先記進 ledger 再收。
- **收起只用 `0`**（不加 `--enter`），在輸入框是空的、沒有 AskUserQuestion 開著時送。`2` 和展開後的 `1`（Understood）會把這句記成「這個人已經懂」，全機所有 session 之後都不再提，而看到的是你、不是使用者。
- 送 `0` 後畫面會留一行 `Dismissed.` 和回饋選項約 20 秒，這段時間先別送數字鍵。
- 子 session 停在 AskUserQuestion 時先答題，等它回到空輸入框再按 Heads up 的鍵：題目開著時數字鍵會被當成選項。
- **展開讀**（`headsup.py` exit 2，或 `text:` 是空的時才用）：輸入框是空的時候送 `1`（不加 `--enter`），再 `scr.py <handle> 40` 讀。展開後選項變成 `1: Understood   2: Chat in main session   0: Dismiss`，讀完送 `0` 收起。看到的已經是後者，代表有人展開過，直接讀畫面上的內容。子 session 在忙時，送一次 `1` 也會展開，展開後照樣能收起。
- 視窗太矮時展開的內容會被截斷（使用者用手機開 Orca，終端只有 27–31 列），底部只剩 `↓ N more` / `↑ N more`，看不到選項那一行：
  - 用 `orca terminal read --terminal <h> --screen --json` 讀實際畫面，從 `tail` 的索引算出面板在第幾列（從 1 起算）；`scr.py` 讀的是輸出流，看不出截在哪。
  - 往下捲送 SGR 滑鼠滾輪，座標要落在面板內：`$'\033[<65;20;<列>M'`（往上捲用 `64`）。每次捲 3 行，一次只送一個，等 3–4 秒再讀；連送三個會沒反應。↓、PageDown 都沒用。
  - 捲到看得見選項那一行（`1: Understood … 0: Dismiss`）後，只送一次 `0`。
- 按鍵沒反應就停手：原文記進 ledger，請使用者在畫面上點掉。連送不同的鍵會讓面板卡死，之後怎麼按都收不起來。

## 額度

- 你和子 session 共用同一份額度。`state=unknown` 而畫面停在 `usage limit` / `continuing automatically at HH:MM`：背景 `sleep` 到重置時間之後幾分鐘，再讀畫面：
  - 它已經自己接上：照常掛 `waitbg.sh`。
  - 還停在同一個訊息：送一次「繼續，從中斷處接著做，保留已完成的部分」。
  - 畫面上找不到重置時間：`sleep 1800` 後照上面兩條判斷。
- 你自己撞到上限也會停，重置後 Claude Code 會自動接著做：醒來先讀 ledger。
- `quota.sh` 印 `gate=unknown`：讀不到用量。多半是沒照 plugin 根目錄 `README.md`〈額度門檻〉設定，或狀態列設定被改掉（例如 Orca 更新時重寫了 `statusLine`）。
