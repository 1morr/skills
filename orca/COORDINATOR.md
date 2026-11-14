# 協調者共同流程

ticket-coordinator、bake-off、review-loop 的協調者都照這份做；各 skill 只寫自己獨有的步驟。`<O>` 是這個資料夾（plugin 根目錄的 `orca/`），腳本在 `<O>/scripts/`，每支開頭寫了用法和輸出。按鍵、畫面、等待、額度的已知行為在 [TUI.md](TUI.md)：第一次代答、第一次掛等待、第一次遇到 Heads up、或畫面跟預期不同時先讀它。

你是**協調者**：判斷、代答、驗收，產出由子 session 做。

## 開工

1. 載入 `orca-cli` skill，`orca status --json` 確認 Orca 在跑；要開 worktree 時用 `orca repo list` 找 repo 選擇器。
2. 在 scratchpad 建 **ledger**。你的上下文會被壓縮：**每次被叫醒先讀 ledger**，每個決定當下寫進去。「目前」段記 repo、orca repo 選擇器、主分支、CI、〈授權〉的答案，再加各 skill 列的欄位。
3. 查**主分支**（`git symbolic-ref --short refs/remotes/origin/HEAD`；沒有 remote 就是使用者目前的分支）和 **CI**（`.github/workflows/` 裡 push 主分支時會跑的 workflow 檔名；沒有就記「沒有 CI」）。腳本預設 `main` 和 `ci.yml`，所以每次呼叫都帶上：`new-ticket.sh`、`merge-ticket.sh` 前面加 `BASE=<主分支>`，`preflight.sh <repo> <主分支>`，`push-ci.sh <repo> <workflow 檔名> <分支>`。

完成條件：`orca status` 回報在跑；ledger 的「目前」段有主分支和 CI（或「沒有 CI」）。

## 授權

和各 skill 開工要問的事放在同一次 AskUserQuestion，答案寫進 ledger：

- push 和其他對外動作（開 PR、issue、release、部署）：可以直接做，還是每次先給使用者看。
- 破壞性 git 操作前：「建備份」還是「直接執行」。

## 子 session 的一輪

1. **開**：用各 skill 指定的腳本。它印出 `handle=`、`jsonl=`（檔名去掉 `.jsonl` 是 session id），寫進 ledger。印 `started: NO` 或 `expanded: NO` 照 TUI.md〈開 session〉。
2. **等**：Bash `run_in_background` 跑 `bash <O>/scripts/waitbg.sh <handle> <jsonl>`，然後結束回合等通知。之後每次送訊息給它（代答、叫它補、轉貼 Heads up）再掛等待，最後加 `sent`：沒加會讀到上一輪的 done，馬上返回。
3. **被叫醒**：讀 ledger。背景輸出第一行是 `state=`，後面是畫面；不夠就 `python3 <O>/scripts/scr.py <handle> 40`。照情況處理：
   - **Heads up**（`state=heads-up`，或任何返回帶著 `headsup=`）：見下一節。
   - **提問**：按鍵見 TUI.md〈回答 AskUserQuestion〉，答什麼照各 skill。答完把「題目 → 答案 → 理由」寫進 ledger。
   - **要人做事**：只有使用者本人才有的（密碼、登入、2FA、實體操作、付款）才轉給使用者；它或你查得到、做得到、驗得到的，叫它自己做並告訴它怎麼做。
   - **停了但沒做完**：先看它是不是在等自己的背景工作（子代理、背景指令），是就重新掛等待；真的停了才叫它接著做完。
   - **額度用完**、`stalled`、`done-bg`、`no-response`：照 TUI.md 對應的段落。
4. **收**：照各 skill 的收尾指令；各 skill 沒給指令時只關這個 handle 的終端。jsonl 留著，使用者會用 `claude --resume <session id>` 回看。

完成條件：`orca terminal list` 裡沒有這個 handle；ledger 有它的 session id 和最後的結果。

## Heads up

Heads up 是 Claude Code 給在場者的風險提醒，只在畫面和 mod 的狀態檔裡，子 session 的 transcript 沒有，所以它不知道。每一則照這個順序：

1. **記**：把 `waitbg.sh` 附的全文和 `shown=` 時間記進 ledger。沒附全文（`headsup-src=screen`，或 `text:` 後面是空的）就照 TUI.md〈Heads up〉展開讀。
2. **收**：照 TUI.md〈Heads up〉送 `0`，`python3 <O>/scripts/headsup.py --summary <jsonl>` exit 1 才算收掉（exit 2 是狀態檔讀不到：改讀畫面，底部沒有 `✦ Heads up` 那一行才算），再照原樣重新掛等待（送過訊息就加 `sent`）。每一則都馬上收：掛著的時候下一則出不來。
3. **分兩級**：
   - **馬上處理**：涉及刪檔或丟掉改動、破壞性 git、push 或對外寫入、金鑰或個人資料外洩、改隱私或安全約定、超出任務範圍。
   - **其他**：等子 session 停下（說做完或來問）再處理。中途的 Heads up 常是它還沒定案的想法，停下時已經自己改掉的，在 ledger 註明「已不適用」。
4. **查證**：對任務來源、文件或程式碼查證一次（各 skill 另有規定的照它，例如 review-loop 把它當成審查意見）。屬實又該修的，把完整原文貼給**同一個 session**，開頭註明「以下是 Claude Code 給在場者的 Heads up 原文」，你的查證與修法另起一段；它在忙時送出的訊息會排隊，最晚在它停下時讀到。不屬實或不修的，寫進 ledger 的「待使用者看」並附理由。

完成條件：`headsup.py --summary` exit 1（exit 2 時畫面底部沒有 `✦ Heads up`）；這一則在 ledger 裡有原文和處置（已轉給子 session、已不適用，或待使用者看）。

## 規則

- 只碰自己開的終端，送訊息一律用開 session 的腳本印出的 `handle=`。使用者手動關掉的不重開。
- 子 session 只在自己的分支 commit，push 和合併由你照各 skill 做。
- merge 之前、你自己在主目錄 commit 之前，跑 `bash <O>/scripts/preflight.sh <repo> <主分支>`；`git add` 只點名自己的檔。
- push 照〈授權〉。有 CI：`bash <O>/scripts/push-ci.sh <repo> <workflow 檔名> <分支>`（`run_in_background`），印 `ci=success` 才算完成；其他結果照各 skill 處理，各 skill 沒寫的就把失敗的 job 回報使用者。沒有 CI：`git push origin <分支>`。
- 使用者要的是 X 就只做 X；順手想清的東西（刪目錄、刪分支、改設定）另外問。

## 回報

要使用者決定的事放在最前面，一題一行、附你的建議，獨立成一則短訊息，不夾在長報告裡。
