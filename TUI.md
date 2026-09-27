# 讀畫面、按鍵、等待、額度：已知行為

`ticket-coordinator` 的參考檔。`<S>` 是 skill 的 `scripts/` 目錄。

## 讀畫面

- `python <S>/scr.py <handle> [行數]`：修正 mojibake、壓縮分隔線、只印非空行。`status: running` 只代表終端
  還在，不代表子 session 在忙。
- 畫面停在捲動模式（出現 `Jump to bottom`、看不到 spinner）：送 Ctrl+End
  `orca terminal send --terminal <h> --text $'\033[1;5F' --json`。
- 不要印子 session 的原始 jsonl 行，會灌爆你的上下文；要查就用 `grep -c` / `grep -o` 印短結果。

## 等待

- `orca terminal wait --for tui-idle` 在子 session 等自己的背景 shell、monitor、子代理時就會返回。`waitbg.sh`
  另外看兩件事，任一成立就繼續等：畫面上有 spinner、`still running`、`N shells`；transcript 60 秒內有寫入，
  或最後一則是還沒完成的 tool_use。AskUserQuestion 例外，它是在等你回答。
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

## 額度

- 你和子 session 共用同一份額度。子 session 停在 `usage limit` / `continuing automatically at HH:MM` 時，它也算
  idle，對它掛 tui-idle 會立刻返回、原地空轉。改成背景 `sleep` 到重置時間之後幾分鐘，再讀畫面：
  - 它已經自己接上：照常掛 `waitbg.sh`。
  - 還停在同一個訊息：送一次「繼續，從中斷處接著做，保留已完成的部分」。
  - 畫面上找不到重置時間：`sleep 1800` 後照上面兩條判斷。
- 你自己撞到上限也會停，重置後 Claude Code 會自動接著做：醒來先讀 ledger。
