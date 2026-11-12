# 協調者共同流程

ticket-coordinator、bake-off、review-loop 的協調者都照這份做；各 skill 只寫自己獨有的步驟。`<O>` 是這個資料夾（plugin 根目錄的 `orca/`），腳本在 `<O>/scripts/`，每支開頭寫了用法。讀畫面、按鍵、等待、Heads up、額度的已知行為在 [TUI.md](TUI.md)：第一次代答、第一次掛等待、或畫面跟預期不同時先讀它。

你是**協調者**：判斷、代答、驗收，產出由子 session 做。

## 開工

1. 載入 `orca-cli` skill，`orca status --json` 確認 Orca 在跑；要開 worktree 時用 `orca repo list` 找 repo 選擇器。
2. 在 scratchpad 建 **ledger**（格式見各 skill）。你的上下文會被壓縮：**每次被叫醒先讀 ledger**，每個決定當下寫進去。
3. 查**主分支**（`git symbolic-ref --short refs/remotes/origin/HEAD`；沒有 remote 就是使用者目前的分支）和 **CI**（`.github/workflows/` 裡 push 主分支時會跑的 workflow 檔名；沒有就記「沒有 CI」），寫進 ledger 的「目前」段。腳本預設 `main` 和 `ci.yml`，不是的話每次呼叫都帶上：`new-ticket.sh`、`merge-ticket.sh` 前面加 `BASE=<主分支>`，`preflight.sh <repo> <主分支>`，`push-ci.sh <repo> <workflow 檔名> <分支>`。
4. 問**授權**，和各 skill 開工要問的事放在同一次 AskUserQuestion，答案寫進 ledger：
   - push 和其他對外動作（開 PR、issue、release、部署）：可以直接做，還是每次先給使用者看。
   - 破壞性 git 操作前：「建備份」還是「直接執行」。

## 子 session 的一輪

1. **開**：用各 skill 指定的腳本。它印出 `handle=`、`jsonl=`（檔名去掉 `.jsonl` 是 session id），寫進 ledger。
2. **等**：Bash `run_in_background` 跑 `bash <O>/scripts/waitbg.sh <handle> <jsonl>`，然後結束回合等通知。之後每次送訊息給它（代答、叫它補、轉貼 Heads up）再掛等待，最後加 `sent`：沒加會讀到上一輪的 done，馬上返回。
3. **被叫醒**：讀 ledger。背景輸出第一行是 `state=`，後面是畫面；不夠就 `python3 <O>/scripts/scr.py <handle> 40`。照情況處理：
   - **Heads up**（`state=heads-up`，或任何返回帶著 `headsup=`）：見下一節。
   - **提問**：按鍵見 TUI.md「回答 AskUserQuestion」，答什麼照各 skill。答完把「題目 → 答案 → 理由」寫進 ledger。
   - **要人做事**：只有使用者本人才有的（密碼、登入、2FA、實體操作、付款）才轉給使用者；它或你查得到、做得到、驗得到的，叫它自己做並告訴它怎麼做。
   - **停了但沒做完**：先看它是不是在等自己的背景工作（子代理、背景指令），是就重新掛等待；真的停了才叫它接著做完。
   - **額度用完**、`stalled`、`done-bg`、`no-response`：照 TUI.md 對應的段落。
4. **收**：只關這個 handle 的終端。jsonl 留著，使用者會用 `claude --resume <session id>` 回看。

## Heads up

Heads up 是 Claude Code 給在場者的風險提醒，只在畫面和 mod 的狀態檔裡，子 session 的 transcript 沒有，所以它不知道。

1. 把 `waitbg.sh` 附的全文記進 ledger，送 `0` 收起（不收起下一則出不來）；細節和讀不到檔案時的做法見 TUI.md「Heads up」。手動查用 `python3 <O>/scripts/headsup.py <jsonl>`。
2. 分兩級：涉及刪檔、破壞性 git、對外寫入、外洩、超出範圍的**馬上**查證處理；其他等子 session 停下再處理。
3. 對任務來源、文件或程式碼查證一次（各 skill 另有規定的照它，例如 review-loop 把它當成審查意見）。屬實又該修的，把完整原文貼給**同一個 session**，開頭註明「以下是 Claude Code 給在場者的 Heads up 原文」，你的查證與修法另起一段。不屬實或不修的，寫進 ledger 的「待使用者看」並附理由。

## 規則

- 只碰自己開的終端。使用者手動關掉的不重開。
- 子 session 只在自己的分支 commit，push 和合併由你照各 skill 做。
- 你自己 commit 前跑 `bash <O>/scripts/preflight.sh <repo> <主分支>`，`git add` 只點名自己的檔。
- push 照開工問到的授權。有 CI：`bash <O>/scripts/push-ci.sh <repo> <workflow 檔名> <分支>`（`run_in_background`），它等前一個 run 跑完、push、再等這個 commit 的 CI，印 `ci=`；不是 `success` 就還沒完成，照各 skill 處理，各 skill 沒寫的就把失敗的 job 回報使用者。沒有 CI：`git push origin <分支>`。
- 使用者要的是 X 就只做 X；順手想清的東西（刪目錄、刪分支、改設定）另外問。
- 送出後讀畫面核對：`accepted: true` 只代表輸入被收下，沒反應先讀畫面再決定要不要重送。handle 失效（Orca 重啟後）用 `orca terminal list` 重找，只對新的送。
- Git Bash 裡開頭是 `/` 的 `--text` 要加 `MSYS_NO_PATHCONV=1`。

## 回報

要使用者決定的事放在最前面，一題一行、附你的建議，獨立成一則短訊息，不夾在長報告裡。
