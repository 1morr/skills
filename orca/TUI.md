# Claude Code 選項與跨平台已知行為

協調者參考檔，僅在涉及 **Claude Code 專屬功能**（Heads up、額度門檻）或**跨平台 shell 問題**時才讀。日常派發、等待、提問與回覆全部走 `orca orchestration`，見 [COORDINATOR.md](COORDINATOR.md)。`<O>` 是這個資料夾，腳本在 `<O>/scripts/`，每支開頭寫了用法和輸出。

## 跨平台

- 手動叫 `headsup.py` 時，Windows 上沒有 `python3` 就用 `python`。
- 某些 shell 環境跑在 zsh：沒加引號的 `$var` 不分詞，`for t in "t02 a.md" "t05 b.md"; do set -- $t` 會把整串當成一個參數。開多個 worker 就一張一行呼叫 `orca orchestration worker-start`。
- Git Bash 裡傳給 CLI 的參數若以 `/` 開頭，加 `MSYS_NO_PATHCONV=1` 避免被轉成 Windows 路徑。

## Heads up（僅 Claude Code worker）

處理順序在 COORDINATOR.md〈Heads up〉；這裡是終端按鍵與畫面細節。非 Claude Code worker 不會出現 Heads up，整節跳過。

- 畫面底部一行 `✦ Heads up · <摘要>`，下面是 `1: Learn more   2: Knew this already   0: Dismiss`。摘要只有一句，完整內容（原因、推測的後果、建議）在 Learn more 裡。
- 全文優先用 `python3 <O>/scripts/headsup.py --worktree <worktree 路徑>` 讀，不必展開畫面。全文只在掛著時存在，收起後 `headsup.py` 讀不到：先記進 ledger 再收。
- **收起只用 `0`**（`orca terminal send --terminal <h> --text 0 --json`，不加 `--enter`），且只在終端空閒、沒有互動提示開著時送。`2` 和展開後的 `1`（Understood）會把這句記成「這個人已經懂」，全機所有 session 之後都不再提，而看到的是你、不是使用者。
- 送 `0` 後畫面會留一行 `Dismissed.` 和回饋選項約 20 秒，這段時間不要再送數字鍵。
- **展開讀**（僅在 `headsup.py` exit 2 或 `text:` 是空的時候才用）：確認終端空閒後送 `1`（不加 `--enter`），用 `orca terminal read --terminal <h> --screen --json` 讀實際畫面，讀完送 `0` 收起。視窗太矮被截斷（看到 `↓ N more`）時，從 `tail` 算出面板所在列（從 1 起算），送 SGR 滑鼠滾輪 `$'\033[<65;20;<列>M'`（每次 1 個、等 3–4 秒再讀），看到 `0: Dismiss` 後只送一次 `0`。
- 按鍵沒反應就停手：原文記進 ledger，請使用者在畫面上點掉。連送不同的鍵會讓面板卡死。

## 額度（僅 Claude Code）

僅在協調者或 worker 使用 Claude Code、且使用者有設定額度門檻時適用；Antigravity、Codex 等其他 agent 跳過。

- Claude Code 協調者與 Claude Code worker 共用同一份額度。若 `worker-read` 顯示 worker 停在 `usage limit` / `continuing automatically at HH:MM`：等到重置時間之後幾分鐘，再看 `orca orchestration worker-show --dispatch <dispatch_id>`；若仍停在同一個訊息，用 `orca orchestration send` 送一次「繼續，從中斷處接著做，保留已完成的部分」。
- `quota.sh` 印 `gate=unknown`：讀不到用量。多半是沒照 repo 根目錄 `README.md`〈額度門檻〉設定，或狀態列設定被改掉（例如 Orca 更新時重寫了 `statusLine`）。
