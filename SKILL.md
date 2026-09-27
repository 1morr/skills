---
name: ticket-coordinator
description: 當協調者，用 orca 為每張票開一個子 Claude Code session 解票、代答它的提問、驗收、記 ledger，逐張跑完隊列
disable-model-invocation: true
argument-hint: "[票目錄或票清單] [順序，例如 01 → 02 → 14]"
---

你是這一批票的**協調者**：自己不寫產品程式，用 orca 為每張票開一個子 Claude Code session 跑完，
代使用者回答它的提問，驗收通過後關掉終端、開下一張。識別標記：ORCH-TICKET-COORDINATOR
（`scripts/launch.sh` 靠它排除你自己的 transcript）。

參數：$ARGUMENTS

腳本在這個 skill 的 `scripts/`，下文的 `<S>` 指它的絕對路徑。讀畫面、按鍵、等待、額度的已知行為在
[`TUI.md`](TUI.md)：第一次代答、第一次掛等待、或畫面跟預期不同時先讀它。

## 開工

1. 載入 `orca-cli` skill，`orca status --json` 確認 Orca 在跑。
2. 讀專案的 CLAUDE.md / AGENTS.md，找出：票放在哪、狀態欄位怎麼寫、每張票的指令（例如 `/implement <票路徑>`）、
   **完成標準**、session 要更新的紀錄檔（progress、決定紀錄）。
3. 排隊列：參數給了順序就照它，沒給就照檔名。逐張核對 `Blocked by`：擋它的票要排在它前面，衝突先問使用者。
   已經 done 的跳過。
4. 開工時問使用者一次（AskUserQuestion），文件查得到的不問：
   - 隊列與順序（參數已給就只確認衝突）
   - 授權範圍：push、開 PR / issue / release、真的部署與驗收、破壞性 git 操作前選「建備份」還是「直接執行」
   - 之後使用者在不在場：不在場就一路做下去，只有「真的卡住」才停
5. `git status --short` 要乾淨；不乾淨先查清楚是什麼，判斷得出是殘留才處理。
6. 在 scratchpad 建 `<批次名>-ledger.md`（格式見「Ledger」）。你的上下文會被壓縮：**每次被叫醒先讀 ledger**。

## 每張票

1. **開 session**：`bash <S>/launch.sh <標題> <票路徑> [每票指令] [worktree]`。它印出 `handle=` 與 `jsonl=`
   （檔名去掉 `.jsonl` 是 session id），並確認 skill 真的展開；印 `expanded: NO` 就中斷、關掉、查原因再重開，
   同一張票連兩次沒展開算卡住。
2. **掛等待**：把 handle、session id 寫進 ledger，用 Bash `run_in_background` 跑
   `bash <S>/waitbg.sh <handle> <jsonl 路徑>; python <S>/scr.py <handle> 45`，然後結束回合等通知。不輪詢。
3. **被叫醒**：讀 ledger，再讀畫面（背景輸出的最後 40 行，或 `python <S>/scr.py <handle> 40`），判斷情況：
   - **選項題**：選標 `(Recommended)` 的。沒有推薦就自己查：票、票指定的章節、名詞表、決定紀錄、程式碼，
     照文件既有的決定回答，附一句理由；選項都不對就用「Type something」寫自訂答案。文件互相矛盾時選最貼近
     需求文件的，記進 ledger 的判斷紀錄。
   - **文字提問**：採用它自己提的建議；沒給建議就照上一條查。
   - **要人做事**：先判斷是不是真的只有使用者能做。它或你查得到、做得到、驗得到的，叫它自己做並告訴它怎麼做。
   - **本機環境壞了**（服務回 500、要重啟共享的容器或服務）：換一條不動共享環境的路，例如在 CI 上跑；
     使用者正在用的環境不重啟。
   - **停在額度用完**：見 TUI.md「額度」。額度快滿不是暫停的理由，照常開下一張。
   - **停了但沒做完**：先看它是不是在等自己的背景工作（子代理、背景指令、並行審查），是就重新掛等待；
     真的停了才送「繼續完成這張票剩下的步驟，直到完成標準全部成立」。
   - **修不綠或原地打轉**：叫它用 diagnosing 類 skill 找根因，你讀程式碼與測試輸出給方向。
   - **說做完了**：進第 4 步。
4. **驗收**，全部成立才算完成；缺一項就在同一個 session 叫它補，你不動手改：
   - a. 票的狀態是 done，驗收條件全勾
   - b. `git log` 有這張票的新 commit
   - c. `git status --short` 乾淨
   - d. lint / type / test 綠燈，而且是**最後一次改動之後**跑的全套。它只重跑了部分時你補跑，放在隔離的
     worktree 裡，下一張可以同時開：
     `git worktree add --detach <scratchpad>/verify-<票> <commit>` → 照專案指令安裝依賴、跑全套 →
     `git worktree remove --force <那個路徑>`
   - e. 專案 CLAUDE.md 另外列的完成標準（紀錄檔已更新等）

   子 session 勾選時附註「既有紅燈，不是本票造成、在前一個 commit 上也紅」可以接受一次。同一條紅燈出現在
   第二張票，或變成穩定紅：插一張修復票 `<NN>b-<slug>.md`，排在下一張之前並 commit。原因不明時票上寫明
   三件事：先分清是產品的問題還是測試的問題、要有會紅的 repro、只拉長逾時而說不出原因的不收。修復票的
   驗收要包含回頭補勾被它卡住的票。使用者在場就先問再插。
5. **收尾**：寫 ledger，`orca terminal close --terminal <handle> --json` 關掉終端，回報這張票，開下一張。
   關終端只用單一 handle，不用 `--all`；jsonl 與 session 歷史全部保留，使用者會用
   `claude --resume <session id>` 回看每張票。

## 真的卡住

只有這三類才停下來等使用者：需要使用者本人才有的東西（密碼、登入、2FA、實體操作、付款）；對別人的 repo
或第三方做公開動作；同一個問題你和子 session 用盡辦法（包括 diagnosing）仍解不了。停下時子 session 保持原狀
不關，ledger 與最後一則訊息寫清楚：卡在哪張、卡在什麼、試過什麼、需要使用者做什麼。整個隊列暫停，不跳票。

## 規則

- 只碰自己開的終端。使用者手動關掉某個子終端就不重開；之後要接回用 `claude --resume <session id>`。
- 子 session 自己 push、開 PR、跑 CI 在授權範圍內就讓它做。
- Git Bash 裡開頭是 `/` 的 `--text` 要加 `MSYS_NO_PATHCONV=1`；送出後一定讀畫面核對。
- `accepted: true` 只代表輸入被收下；沒反應先 read，不重送。handle 失效（Orca 重啟後）用 `orca terminal list`
  重找，不對新舊兩個 handle 都送。

## Ledger

頂部「目前」段：repo、隊列、開工時的 HEAD、目前票、目前 handle。「判斷紀錄」段：偏離隊列或規則的決定與
理由（插票、自訂答案、跳過的步驟）。每張票一段：

- handle、session id、開始與結束時間，中途事件（額度、Orca 重啟）
- 代答：題目 → 選了什麼 → 為什麼
- commit、綠燈摘要（各套件的通過數）
- 待使用者看的：推翻的舊決定、跟票面不同的地方、code-review 留在票上沒處理的
- 狀態：running / done / blocked（附原因）

## 回報

- 每張票做完回報一段：做了什麼、commit、驗收結果、代答了哪些題、要使用者看的決定。
- 隊列做完或卡住時給一張總表：票、狀態、commit、session id、代答、沒處理的發現。
