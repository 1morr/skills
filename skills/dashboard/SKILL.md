---
name: dashboard
description: 開一頁會自動更新的專案總覽：里程碑與票的進度、決策、ADR、最近的 session
disable-model-invocation: true
argument-hint: "[repo 路徑…，預設目前的 repo] [static：只產生一個 HTML 檔]"
---

開一頁專案總覽給使用者看自己正在做什麼。頁面的內容全部由腳本從 repo 的固定文件讀出來（`docs/roadmap.md`、`.scratch/`、`docs/decisions.md`、`docs/adr/`、`docs/progress.md`），你不寫、不改頁面，也不改 repo。

參數：$ARGUMENTS

`<S>` 是 `${CLAUDE_SKILL_DIR}/scripts`。

## 1. 要看哪些 repo

參數給了路徑就用它們，可以好幾個，頁面上方切換；沒給就是目前的 repo（`git rev-parse --show-toplevel`）。

## 2. 開頁面

- **預設**：用 Bash 的 `run_in_background` 跑 `python3 <S>/dashboard.py --serve <repo>…`。它印出的第一行是網址。埠被佔用（`Address already in use`）就加 `--port 0` 重跑，讓系統挑一個。用預設瀏覽器打開網址（macOS `open`、Windows `start`、Linux `xdg-open`）。
- **參數有 `static`**：`python3 <S>/dashboard.py <repo>… -o <scratchpad>/dashboard.html`，打開那個檔。它不會自動更新。

伺服器只綁 `127.0.0.1`。使用者說要從手機或別台機器看時才加 `--host 0.0.0.0`，並先告訴他：同一個網路上的人都看得到這些決策和進度。

完成條件：瀏覽器開著那一頁，頁面上有里程碑。

## 3. 告訴使用者

- 網址（或檔案的完整路徑），以及頁面每 3 秒重讀一次文件、票合併或文件一改就會跟著變。
- 怎麼關：伺服器是這個 session 的背景工作，session 結束就停；要先關就說一聲。
- 頁面出現「讀不到的檔」時，照它列的轉告：那個 repo 還沒照 project-init 的骨架，在那個 repo 下 `/1morr:project-init` 會走同步。
- 頁面出現「讀不到的行」時，轉告有幾條、在哪幾個檔：那幾條決定的開頭不是 `- YYYY-MM-DD `，改成這個寫法就會列進決策。
