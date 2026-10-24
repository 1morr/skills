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
- 收票只關 worktree 路徑完全相同的終端（`terminals_in.py`）：比對前統一斜線、Windows 磁碟代號不分大小寫，`t07` 不會比中 `t07b`。

## 讀畫面

- `python3 <S>/scr.py <handle> [行數]`：修正 mojibake、壓縮分隔線、只印非空行。`status: running` 只代表終端
  還在，不代表子 session 在忙。
- 畫面停在捲動模式（出現 `Jump to bottom`、看不到 spinner）：送 Ctrl+End
  `orca terminal send --terminal <h> --text $'\033[1;5F' --json`。
- 不要印子 session 的原始 jsonl 行，會灌爆你的上下文；要查就用 `grep -c` / `grep -o` 印短結果。

## 等待

- 以 transcript 為準，不以畫面為準：終端停在捲動模式時畫面不會更新，曾把還在跑的票誤判成做完。
  `python3 <S>/state.py <jsonl>` 印 `done`（回合結束、背景工作都回來了或被它自己停掉）、`busy` / `waiting-bg`、
  `asking`（停在 AskUserQuestion 等你）、`unknown`（額度、API 錯誤、被中斷，讀畫面判斷）。
- `waitbg.sh` 每 30 秒問一次 `state.py`，`done` 而畫面上還有 shell / monitor 計數時繼續等（Monitor 認不出來）；
  `waiting-bg` 半小時沒動靜、畫面也沒有在跑的東西時以 `state=stalled` 返回，多半是它停了背景工作卻沒留紀錄。
- 改了 `state.py`、`run-check.sh`、`merge-ticket.sh` 就跑 `bash <S>/selftest.sh`，要印 `ALL OK`。
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
