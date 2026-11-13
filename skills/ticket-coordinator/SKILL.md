---
name: ticket-coordinator
description: 用 Orca 逐張開子 session 解票、代答、驗收、合併，跑完整個隊列
disable-model-invocation: true
argument-hint: "[票目錄或票清單] [順序，例如 01 → 02 → 14] [額度門檻，例如 5h 80%、7d 95%] [同時最多 N 張]"
---

你是這一批票的協調者：為每張票開一個子 session 跑完，代使用者回答它的提問，驗收合併後開下一張。識別標記：ORCH-TICKET-COORDINATOR（`launch.sh` 靠它排除你自己的 transcript）。

參數：$ARGUMENTS

`<O>` 是 `${CLAUDE_PLUGIN_ROOT}/orca`（plugin 根目錄的 `orca/`）。**先讀 `<O>/COORDINATOR.md`**：開工、等待、被叫醒、Heads up、規則、回報都照它，這份只寫票獨有的部分。

參數裡的兩個上限，沒給就不限：
- **額度門檻**（例如「5h 80%」「7d 95%」）：到門檻就不開新票，在跑的票照常做完，額度刷新後接著開。沒給門檻時，額度快滿照常開。
- **同時最多幾張**：在跑的票到這個數，就等其中一張收尾再開。

## 開工

1. 照 COORDINATOR.md「開工」。
2. 讀專案的 CLAUDE.md / AGENTS.md，找出：票放在哪、狀態欄位、每張票的指令（例如 `/implement <票路徑>`）、**完成標準**、紀錄檔是哪個、由誰寫（做票的 session，還是合併的人）。
3. 排隊列：參數給了順序就照它，沒給就照檔名。逐張核對 `Blocked by` 和驗收條件：要用到別張票產出的東西（頁面、端點、資料表）也算擋。已經 done 的跳過，衝突先問使用者。
4. 用 AskUserQuestion 問一次（連同 COORDINATOR.md〈授權〉），文件查得到的不問：
   - 隊列與順序（參數已給就只確認衝突）
   - 之後在不在場：不在場就一路做下去，只有〈真的卡住〉才停
5. `bash <O>/scripts/preflight.sh <repo> <主分支>`：主目錄要乾淨、本機主分支與 origin 一致。有 WARN 先查清楚是誰的（可能是別的 session 在主目錄工作），確定是殘留才處理；來歷不明的 commit 留給使用者，不跟著你的 push 上去。
6. ledger 的「目前」段再記下 `REQUIRE`（完成標準要求每張票的分支都動到的檔；紀錄檔由合併的人寫的專案留空）、紀錄檔由誰寫、額度門檻與同時上限。

## 每張票

1. **開 session**：每張票一個自己的 worktree 與分支，主目錄留給你。開之前過兩道上限（有給才查）：
   - 同時上限：running 的票到上限就等。
   - 額度：`bash <O>/scripts/quota.sh <5h 門檻> <7d 門檻>`（沒給的填 0）。`gate=closed` 就不開新票，背景 `sleep` 它印的秒數（最多 3600）再問；在跑的票照常等、照常驗收合併。`gate=unknown` 一樣先睡再問，連續 3 次就停下問使用者，原因見 TUI.md「額度」。

   `BASE=<主分支> bash <O>/scripts/new-ticket.sh <repo 選擇器> t<NN> <票路徑> [標題] [每票指令]`：從主分支開 worktree、開子 session，並確認 skill 真的展開。印 `expanded: NO` 照 TUI.md「開 session」。

   互不相擋的票可以同時開，一張一行呼叫（見 TUI.md「跨平台」）。會撞的排先後：改同一區程式碼、同一張登記表或閘門測試、都新增資料庫 migration（合起來會有兩個 head）。
2. **等與被叫醒**：照 COORDINATOR.md「子 session 的一輪」。提問這樣答：
   - **選項題**：選標 `(Recommended)` 的。沒有推薦就查票、票指定的章節、名詞表、決定紀錄、程式碼，照文件既有的決定回答，附一句理由；選項都不對就用「Type something」寫自訂答案。文件互相矛盾時選最貼近需求文件的，記進「判斷紀錄」。
   - **文字提問**：採用它自己提的建議；沒給建議就照上一條查。
   - **本機環境壞了**（服務回 500、要重啟共享的容器）：換一條不動共享環境的路，例如在 CI 上跑；使用者正在用的環境保持原樣。
   - **修不綠或原地打轉**：叫它用 diagnosing 類 skill 找根因，你讀程式碼與測試輸出給方向。
   - **說做完了**：還沒處理的 Heads up 都處理完，進第 3 步。
3. **驗收與合併**，照下面的順序做，前一項成立才做下一項；缺一項就在同一個 session 叫它補，產品程式由它改：
   - **跟上主分支**：這張票開出後主分支多了程式碼，叫子 session 在它的分支 `git merge <本機主分支>`：用 git 預設的合併訊息（自訂標題會被 `merge-ticket.sh` 擋）、不 pull 不 push、解衝突、跑全套再交回。交回的樹就是合併結果，下一條的補跑不必再做。
   - **綠燈**：lint / type / test 全套，而且是最後一次改動之後跑的。主分支在這張票開出後只多了文件類 commit 時不重跑。子 session 只重跑了部分時你補跑，放在隔離的 worktree（`git worktree add --detach <scratchpad>/verify-<票> <commit>` → 裝依賴、跑全套 → `git worktree remove --force`）。檢查指令包在 `bash <O>/scripts/run-check.sh <指令>` 裡：機器原生崩潰會記到 `~/.claude/crash-log.tsv` 並自動重跑一次，崩潰不算偶發；重跑仍紅才是真的紅。
   - **合併**：`bash <O>/scripts/preflight.sh <repo> <主分支>`，再 `BASE=<主分支> REQUIRE="<檔>" bash <O>/scripts/merge-ticket.sh <repo> <worktree> <票路徑> "merge: ticket <NN> <slug>"`。票、commit、worktree 和主目錄都合格它才 `merge --no-ff`。印 `NOT READY` 就把那幾行原樣轉給子 session（標題太長叫它自己改寫並建備份分支）。`CONFLICT`：紀錄檔類的你解；程式碼衝突 `git merge --abort`，回到「跟上主分支」。
   - **紀錄**（專案規定紀錄檔由合併的人寫時）：照專案指令檔的格式，把票上留給紀錄檔的行抄進去（project-init 的骨架是票 `## Comments` 裡的 `Session 紀錄：` 一行抄成 `docs/progress.md` 的一列、`決定：` 每行抄成 `docs/decisions.md` 的一條，補上日期與里程碑），「下一步」寫隊列裡下一張票的指令；跑專案的文件檢查，照〈協調者自己的 commit〉commit。票上沒有那一行就叫子 session 補，補完重走合併。
   - **push**：照 COORDINATOR.md「規則」用 `push-ci.sh`。CI 不綠，這張票還沒完成：叫同一個子 session 跟上主分支、修，修完重走這一步（補修的合併用 `REQUIRE=""`）。紅在本機全套沒跑到的檢查時，把本機的等價指令記進 ledger，之後每張票交回時都叫子 session 跑。

   **偶發紅燈**：子 session 附註「既有紅燈，在前一個 commit 上也紅」可以接受一次，記進「偶發紀錄」。同一條紅燈第二次出現（不論哪張票、本機或 CI）或變成穩定紅：插一張修復票 `<NN>b-<slug>.md` 排在下一張之前並 commit。原因不明時票上寫明：先分清是產品還是測試的問題、要有會紅的 repro、只拉長逾時而說不出原因的不收。修復票的驗收包含回頭補勾被它卡住的票。使用者在場就先問再插。
4. **收尾**：CI 綠了才 `bash <O>/scripts/close-worktree.sh <repo> <worktree>`：關掉開在那個 worktree 的終端、移除 worktree、刪已合併的分支。寫 ledger，回報這張票，開下一張。

## 隊列停下時

隊列做完或卡住，而專案的指令檔要求紀錄檔寫「下一步」時：子 session 不知道下一張是哪張，它們寫的那一欄不可靠，你自己寫的那一列也可能已經過時。把紀錄檔最後一列的「下一步」改成真正的下一步（還有票就是下一張沒做的票的指令，里程碑做完就是指令檔規定的那一句，卡住就是「等使用者：…」），照〈協調者自己的 commit〉commit，再照 `push-ci.sh` 推上去。

## 真的卡住

只有三類才停下等使用者：需要使用者本人才有的東西；對別人的 repo 或第三方做公開動作；同一個問題你和子 session 用盡辦法（包括 diagnosing）仍解不了。停下時子 session 保持原狀，ledger 與最後一則訊息寫清楚卡在哪張、卡在什麼、試過什麼、需要使用者做什麼。整個隊列暫停，不跳票。

## 協調者自己的 commit

開票、修紀錄檔、合併後的小修照 COORDINATOR.md 的 commit 規則。新票號先 `git fetch`，取 origin 主分支與所有 worktree 分支裡最大的號碼加一。

## Ledger

- 「目前」段（COORDINATOR.md 的共同欄位之外）：`REQUIRE`、紀錄檔由誰寫、隊列、開工時的 HEAD、目前的票、handle 與 worktree、額度門檻與同時上限（沒給寫「不限」）。
- 「判斷紀錄」：偏離隊列或規則的決定與理由（插票、自訂答案、跳過的步驟）。
- 「偶發紀錄」表：測試名、哪張票、時間、本機或 CI。
- 每張票一段：handle、session id、起訖時間與中途事件；代答；commit 與綠燈摘要；待使用者看的（推翻的舊決定、跟票面不同的地方、code-review 沒處理的、Heads up 的內容與處置）；狀態 running / done / blocked。

## 回報

- 每張票一段：做了什麼、commit、驗收結果、代答了哪些題、要使用者看的決定、Heads up（每條一句：說什麼、修了還是為什麼不修）。
- 隊列做完或卡住時一張總表：票、狀態、commit、session id、代答、沒處理的發現。
