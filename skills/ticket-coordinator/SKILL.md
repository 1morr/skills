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
5. `bash <S>/preflight.sh <repo>`：主目錄要乾淨、本機主分支與 origin 一致。有 WARN 先查清楚是誰的（同一個 repo
   可能還有別的協調者或使用者的 session 在主目錄工作），判斷得出是殘留才處理；不明的 commit 不要跟著你的 push 上去。
   另外記下 orca 的 repo 選擇器（`orca repo list`）與專案完成標準要求每張票都動到的檔（例如 `docs/progress.md`，
   給 `merge-ticket.sh` 的 `REQUIRE`），寫進 ledger。
6. 在 scratchpad 建 `<批次名>-ledger.md`（格式見「Ledger」）。你的上下文會被壓縮：**每次被叫醒先讀 ledger**。

## 每張票

1. **開 session**：每張票一個自己的 worktree 與分支，主目錄不給子 session 用。
   `bash <S>/new-ticket.sh <repo 選擇器> t<NN> <票路徑> [標題] [每票指令]`：從主分支開 orca worktree，再呼叫
   `launch.sh` 在裡面開子 session。它印出 `worktree=`、`handle=`、`jsonl=`（檔名去掉 `.jsonl` 是 session id），
   並確認 skill 真的展開；印 `expanded: NO` 就中斷、關掉、查原因再重開，同一張票連兩次沒展開算卡住。
   互不相擋的票可以同時開幾張；同一區程式碼的票排先後，否則合併時會撞。
2. **掛等待**：把 worktree、handle、session id 寫進 ledger，用 Bash `run_in_background` 跑
   `bash <S>/waitbg.sh <handle> <jsonl 路徑>`，然後結束回合等通知。不輪詢。
3. **被叫醒**：讀 ledger。背景輸出的第一行是 `state=`（以 transcript 判斷，見 TUI.md「等待」），後面是畫面；
   不夠就 `python3 <S>/scr.py <handle> 40`。判斷情況：
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
   - **說做完了**：先看畫面上有沒有 Claude Code 的 `✦ Heads up` 旁註（提醒在場的人注意的風險，子 session 不會自己處理）。有就展開讀完整內容（按鍵見 TUI.md「Heads up」），判斷要不要修：要修的叫**同一個 session** 修完再驗收，不修的寫進 ledger 的「待使用者看」並附理由。然後進第 4 步。
4. **驗收與合併**，全部成立才算完成；缺一項就在同一個 session 叫它補，你不動手改產品程式：
   - a–c、e 交給腳本：先 `bash <S>/preflight.sh <repo>`，再
     `REQUIRE="<完成標準要求的檔>" bash <S>/merge-ticket.sh <repo> <worktree> <票路徑> "merge: ticket <NN> <slug>"`。
     它檢查票的 Status 是 done、沒有未勾的驗收條件、分支上有新 commit、worktree 乾淨、每個 commit 標題 ≤72 字元
     且是 Conventional Commits、`REQUIRE` 的檔都動到、主目錄乾淨，全部成立才 `merge --no-ff`。印 `NOT READY`
     就把那幾行原樣轉給子 session 叫它補（標題太長叫它自己改寫並建備份分支）。`CONFLICT`：紀錄檔類的衝突你解；
     程式碼衝突 `git merge --abort`，叫子 session 在它的分支先 merge 主分支、跑完檢查再交回來。
   - d. lint / type / test 綠燈，而且是**最後一次改動之後**跑的全套。子 session 只重跑了部分時你補跑，放在隔離的
     worktree（`git worktree add --detach <scratchpad>/verify-<票> <commit>` → 安裝依賴、跑全套 →
     `git worktree remove --force`）。merge 之後：主分支在這張票開出後只多了文件類 commit，不重跑；
     多了程式碼，就在合併結果上跑一次全套（專案的檢查指令與 test）。
     檢查指令一律包在 `bash <S>/run-check.sh <指令>` 裡：機器原生崩潰（0xC0000005 / 0xC000001D 之類）會被記到
     `~/.claude/crash-log.tsv` 並自動重跑一次。崩潰不算測試偶發，不計次、不開票；重跑仍紅才是真的紅。
   - push：`bash <S>/push-ci.sh <repo>`（`run_in_background`）。它先等主分支上還在跑的 run（新 push 會取消它們，
     上一張票或發版的驗證就沒了），push 後等這個 commit 的 CI，印 `ci=`。CI 不綠，這張票還沒完成：
     叫同一個子 session 在它的分支修，修完重走這一步。

   **偶發紅燈**：子 session 附註「既有紅燈，不是本票造成、在前一個 commit 上也紅」可以接受一次，記進 ledger 的
   「偶發紀錄」表。同一條紅燈第二次出現（不論哪張票、本機或 CI），或變成穩定紅：插一張修復票 `<NN>b-<slug>.md`，
   排在下一張之前並 commit。原因不明時票上寫明三件事：先分清是產品的問題還是測試的問題、要有會紅的 repro、
   只拉長逾時而說不出原因的不收。修復票的驗收要包含回頭補勾被它卡住的票。使用者在場就先問再插。
5. **收尾**：CI 綠了才 `bash <S>/close-ticket.sh <repo> <worktree>`：關掉開在那個 worktree 的終端、移除 worktree、
   prune、刪已合併的分支。只關自己開的那幾個終端，不用 `--all`；jsonl 與 session 歷史全部保留，使用者會用
   `claude --resume <session id>` 回看每張票。寫 ledger，回報這張票，開下一張。

## 真的卡住

只有這三類才停下來等使用者：需要使用者本人才有的東西（密碼、登入、2FA、實體操作、付款）；對別人的 repo
或第三方做公開動作；同一個問題你和子 session 用盡辦法（包括 diagnosing）仍解不了。停下時子 session 保持原狀
不關，ledger 與最後一則訊息寫清楚：卡在哪張、卡在什麼、試過什麼、需要使用者做什麼。整個隊列暫停，不跳票。

## 規則

- 只碰自己開的終端。使用者手動關掉某個子終端就不重開；之後要接回用 `claude --resume <session id>`。
- 子 session 只在自己的分支 commit，不 push、不 merge 主分支以外的東西；push 主分支只由協調者用 `push-ci.sh` 做，
  一次一個，免得互相取消 CI。開 PR、開 issue 照授權範圍。
- 協調者自己也會 commit（開票、修紀錄檔、合併後的小修）：先跑 `preflight.sh`，`git add` 只點名自己的檔，不用
  `-A` / `.`。新票號先 `git fetch`，取 origin 主分支與所有 worktree 分支裡最大的號碼加一，免得跟別的 session 撞號。
- 使用者叫你做 X 就只做 X；順手想清的東西（刪目錄、刪分支、改設定）另外問，不要夾帶在同一個指令裡。
- Git Bash 裡開頭是 `/` 的 `--text` 要加 `MSYS_NO_PATHCONV=1`；送出後一定讀畫面核對。
- `accepted: true` 只代表輸入被收下；沒反應先 read，不重送。handle 失效（Orca 重啟後）用 `orca terminal list`
  重找，不對新舊兩個 handle 都送。

## Ledger

頂部「目前」段：repo、orca repo 選擇器、`REQUIRE`、隊列、開工時的 HEAD、目前票、目前 handle 與 worktree。
「判斷紀錄」段：偏離隊列或規則的決定與理由（插票、自訂答案、跳過的步驟）。「偶發紀錄」表：測試名、哪張票、
時間、本機或 CI；第二筆同名就開修復票（崩潰不記這裡，記在 crash-log）。每張票一段：

- handle、session id、開始與結束時間，中途事件（額度、Orca 重啟）
- 代答：題目 → 選了什麼 → 為什麼
- commit、綠燈摘要（各套件的通過數）
- 待使用者看的：推翻的舊決定、跟票面不同的地方、code-review 留在票上沒處理的、Heads up 的完整內容與處置
- 狀態：running / done / blocked（附原因）

## 回報

- **要使用者決定的事放在最前面**，一題一行、附你的建議；有這種題目時獨立成一則短訊息，不要夾在總表或長報告裡
  （曾經夾在長總表裡，使用者六天後才看到）。
- 每張票做完回報一段：做了什麼、commit、驗收結果、代答了哪些題、要使用者看的決定、Heads up（每條一句：說什麼、修了還是為什麼不修）。
- 隊列做完或卡住時給一張總表：票、狀態、commit、session id、代答、沒處理的發現。
