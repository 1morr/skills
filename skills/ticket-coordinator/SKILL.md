---
name: ticket-coordinator
description: 用 Orca 逐張開 worker 解票、代答、驗收、合併，跑完整個隊列
disable-model-invocation: true
argument-hint: "[票的位置] [agent/模型] [額度門檻，例如 5h 80%] [同時最多 N 張]"
---

你是這一批票的協調者：透過 Orca `orchestration` 為每張票開一個 worker 跑完，代使用者回答它的提問，驗收合併後開下一張。

參數：使用者呼叫本 skill 時附帶的內容。

`<O>` 是本檔往上兩層的 `orca/`（可用環境變數 `SKILLS_ROOT` 指定 repo 根目錄）。**先讀 `<O>/COORDINATOR.md`**，這份只寫票獨有的部分。

參數裡可選填 worker 的 **agent 與模型**（如 `antigravity`、`claude`、`codex`）、**額度門檻**（僅 Claude Code 適用，例如「5h 80%」「7d 95%」），以及**同時最多幾張**；沒給就用預設或不限，怎麼用在〈每張票〉第 1 步。

## 開工

1. 照 COORDINATOR.md〈開工〉。
2. 讀專案的 `AGENTS.md` / `CLAUDE.md`，找出：票放在哪、狀態欄位、每張票要照哪個 skill 或流程做（記下該 skill 的 `SKILL.md` 完整路徑或做法，不依賴斜線指令展開）、**完成標準**，以及它要求每張票的分支都動到哪些檔（`project-init` 的骨架沒有：做票的紀錄留在票上）。
3. 排隊列：參數給了順序就照它，沒給就照檔名。逐張核對 `Blocked by` 和驗收條件：要用到別張票產出的東西（頁面、端點、資料表）也算擋。已經 done 的跳過，衝突先問使用者。
4. 向使用者提問（有互動提問工具就用它，否則在對話列點詢問）一次問完（連同 COORDINATOR.md〈授權〉），文件查得到的不問：
   - 隊列與順序（參數已給就只確認衝突）
   - 之後在不在場：不在場就一路做下去，要使用者拍板的題只擱置相關的票，只有〈真的卡住〉才整個停
5. `bash <O>/scripts/preflight.sh <repo> <主分支>`。有 WARN 先查清楚是誰的（可能是別的 session 在主目錄工作），確定是殘留才處理；來歷不明的 commit 留給使用者，不跟著你的 push 上去。
6. 把〈Ledger〉「目前」段的每一欄記進 ledger。

完成條件：隊列每張票的 `Blocked by` 和驗收條件都核對過；`preflight.sh` 的每條 WARN 都查清了來歷；ledger「目前」段每一欄都有值。

## 每張票

1. **開 worker**：每張票一個自己的 worktree 與分支，主目錄留給你。開之前過兩道上限（有給才查）：
   - 同時上限：running 的票到上限就等。
   - 額度（僅在 worker 或協調者為 Claude Code 且有設額度門檻時查；純非 Claude Code 跳過）：`bash <O>/scripts/quota.sh <5h 門檻> <7d 門檻>`（只填數字，例如 `80`；沒給的填 0）。`gate=closed` 就不開新票，等它印的秒數（最多 3600）再問；在跑的票照常等叫醒、照常驗收合併。`gate=unknown` 一樣先等再問，連續 3 次照〈真的卡住〉，原因見 TUI.md〈額度〉。

   在本次 run 目錄（`ledger.md` 同目錄）寫這張票的 spec 檔（例如 `spec-t<NN>.md`），寫明：
   - 票路徑（相對 repo 根）、專案指令檔與完成標準；若專案指定用某個 skill 解票，寫明「先讀 `<SKILL.md 完整路徑>` 並照做」，不要靠開頭斜線指令展開。
   - 遇到問題一律用 `orca orchestration ask`，不用本地互動提問工具；只在自己的分支 commit，不 pull 不 push。
   - 照 COORDINATOR.md〈對話透明化〉：每次 `ask`、收到回覆或送出 `worker_done`，都在自己的對話寫一行摘要（對象、送出或收到什麼、檔案完整路徑）。
   - 完成時以 `orca orchestration send --type worker_done --outcome succeeded` 回報，body 附 commit hash、改動摘要與跑過的檢查結果。

   再照 COORDINATOR.md〈Worker 的一輪〉跑 `orca orchestration worker-start`（`--worktree new-top-level --repo <repo 選擇器> --name t<NN> --base-branch <主分支> --task-title "t<NN> <slug>" --spec-file <spec 路徑> --agent <agent> [--model <模型>]`），並在對話寫一行派發摘要。

   互不相擋的票可以同時開，一張一行呼叫 `worker-start`（見 TUI.md〈跨平台〉）。會撞的排先後：改同一區程式碼、同一張登記表或閘門測試、都新增資料庫 migration（合起來會有兩個 head）。
2. **等與被叫醒**：照 COORDINATOR.md〈Worker 的一輪〉。收到 `question` 時用 `orca orchestration reply --id <msg_id> --body "<答案>"` 回答：
   - **要使用者拍板的題**先挑出來：專案指令檔規定要問使用者的，例如推翻 brief、ADR 等已定的決定。照 [USER.md](USER.md)〈等使用者拍板〉轉問或擱置；同一次提問裡的其他題照下面幾條決定好，等這題有答案再一起送。
   - **選項題**：選標 `(Recommended)` 的。沒有推薦就查票、票指定的章節、名詞表、決定紀錄、程式碼，照文件既有的決定回答，附一句理由；選項都不對就直接在回覆寫自訂決定與理由。文件互相矛盾時選最貼近需求文件的，記進「判斷紀錄」。
   - **文字提問**：採用它自己提的建議；沒給建議就照上一條查。
   - **本機環境壞了**（服務回 500、要重啟共享的容器）：換一條不動共享環境的路，例如在 CI 上跑；使用者正在用的環境保持原樣。
   - **修不綠或原地打轉**：用 `send` 叫它做根因診斷（有 diagnosing 類 skill 就指定讀它的 `SKILL.md`），你讀程式碼與測試輸出給方向。
   - **收到 `worker_done`**：結果是 `succeeded` 時，若該 worker 是 Claude Code，先確認還沒處理的 Heads up 都處理完，再進第 3 步；結果是 `failed` 時先讀 `worker-read` 判斷是叫它補做還是照〈真的卡住〉。
3. **驗收與合併**，照下面的順序做，前一項成立才做下一項；缺一項就用 `orca orchestration send --to dispatch:<dispatch_id>` 叫同一個 worker 補，產品程式由它改：
   - **跟上主分支**：這張票開出後主分支多了程式碼，叫 worker 在它的分支 `git merge <本機主分支>`：用 git 預設的合併訊息（`Merge ` 開頭才過 `merge-ticket.sh` 的標題檢查）、不 pull 不 push、解衝突、跑全套再交回。交回的樹就是合併結果，下一條的補跑不必再做。
   - **綠燈**：lint / type / test 全套，而且是最後一次改動之後跑的。主分支在這張票開出後只多了文件類 commit 時不重跑。worker 只重跑了部分時你補跑，用 `mktemp -d` 建一次性暫存目錄開隔離的 worktree（`V=$(mktemp -d) && git worktree add --detach "$V/verify-<票>" <commit>` → 裝依賴、跑全套 → `git worktree remove --force "$V/verify-<票>" && rm -rf "$V"`）。檢查指令包在 `bash <O>/scripts/run-check.sh <指令>` 裡：它回報紅才是真的紅，機器崩潰不算進「偶發紀錄」。
   - **紀錄落在票上**：ledger 和對話在這一場結束後就沒人讀得到，票才是紀錄。叫 worker 在票的 `## Comments` 補齊再 commit，格式照專案指令檔：你代答的每一題一行決定，決定者標 Agent 定（worker 常標成使用者定或使用者同意，叫它改），轉問使用者的照你回答時寫的決定者；跟票面不同的做法、推翻的舊決定各一行；沒處理的 code-review 發現和不修的 Heads up（如有）各一句。
   - **合併**：`bash <O>/scripts/preflight.sh <repo> <主分支>`，再 `BASE=<主分支> REQUIRE="<檔>" bash <O>/scripts/merge-ticket.sh <repo> <worktree> <票路徑> "merge: ticket <NN> <slug>"`。印 `NOT READY` 就把那幾行原樣轉給 worker（標題太長叫它自己改寫並建備份分支）。`CONFLICT`：紀錄檔類的你解；程式碼衝突 `git merge --abort`，回到「跟上主分支」。
   - **push**：照 COORDINATOR.md〈規則〉用 `push-ci.sh`。CI 不綠，這張票還沒完成：叫同一個 worker 跟上主分支、修，修完重走這一步（補修的合併用 `REQUIRE=""`）。紅在本機全套沒跑到的檢查時，把本機的等價指令記進 ledger，之後每張票交回時都叫 worker 跑。

   **偶發紅燈**：worker 附註「既有紅燈，在前一個 commit 上也紅」可以接受一次，記進「偶發紀錄」。同一條紅燈第二次出現（不論哪張票、本機或 CI）或變成穩定紅：插一張修復票 `<NN>b-<slug>.md` 排在下一張之前並 commit。原因不明時票上寫明：先分清是產品還是測試的問題、要有會紅的 repro、只拉長逾時而說不出原因的不收。修復票的驗收包含回頭補勾被它卡住的票。使用者在場就先問再插。
4. **收尾**：CI 綠了才跑 `orca orchestration worker-release --dispatch <dispatch_id>`，再 `bash <O>/scripts/close-worktree.sh <repo> <worktree>`。寫 ledger，回報這張票，開下一張。

完成條件（每張票）：`push-ci.sh` 印 `ci=success`（沒有 CI 就是 push 成功）；`git worktree list` 沒有這張票的 worktree；ledger 裡它的狀態是 done。

## 使用者插話

使用者在隊列進行中問問題或要求改東西時，先讀 [USER.md](USER.md)〈使用者插話〉，照它處理完再回到原本的等待。

## 真的卡住

只有四類才停下等使用者（要使用者拍板的題不算，照 [USER.md](USER.md)〈等使用者拍板〉只擱置相關的票）：需要使用者本人才有的東西；對別人的 repo 或第三方做公開動作；同一個問題你和 worker 用盡辦法仍解不了，或 worker 連續啟動失敗觸發斷路器；給了 Claude Code 額度門檻卻連續 3 次讀不到用量（`gate=unknown`）。停下時 worker 保持原狀，ledger 與最後一則訊息寫清楚卡在哪張、卡在什麼、試過什麼、需要使用者做什麼；要他決定的題目照 [USER.md](USER.md)〈隊列停下時〉寫進 repo。整個隊列暫停，不跳票。

## 協調者自己的 commit

開票、寫紀錄檔、合併後的小修照 COORDINATOR.md〈規則〉：commit 前跑 `preflight.sh`，`git add` 只點名自己的檔。新票號先 `git fetch`，取 origin 主分支與所有 worktree 分支裡最大的號碼加一。

## Ledger

- 「目前」段（COORDINATOR.md 的共同欄位之外）：`REQUIRE`（完成標準要求每張票的分支都動到的檔，沒有就留空）、隊列、使用者在不在場、開工時的 HEAD、目前的票、額度門檻與同時上限（沒給寫「不限」）。
- 「判斷紀錄」：偏離隊列或規則的決定與理由（插票、自訂答案、跳過的步驟）。
- 「偶發紀錄」表：測試名、哪張票、時間、本機或 CI。
- 每張票一段：`taskId`、`dispatchId`、agent/模型、worktree、起訖時間與中途事件；代答；commit 與綠燈摘要；待使用者看的（推翻的舊決定、跟票面不同的地方、code-review 沒處理的、Heads up 的內容與處置）；狀態 running / done / blocked。

## 回報

- 每張票一段：做了什麼、commit、驗收結果、代答了哪些題、要使用者看的決定、Heads up（如有，每條一句：說什麼、修了還是為什麼不修）。
- 隊列做完或卡住時一張總表：票、狀態、commit、`dispatchId`、代答、沒處理的發現。專案有 `scripts/next_step.py` 時，最後跑 `python3 scripts/next_step.py`：等使用者決定的事和下一條指令以它為準，由你來講。等使用者決定的每一題照 COORDINATOR.md〈回報〉，寫背景一句、選項、你的建議、他回答之後你會接著跑哪幾張；下一條指令照它印的放進 code block。它叫使用者開新 session 做的票還在你的隊列裡時，說明這張由你接著跑。

完成條件：隊列的每張票在總表裡不是 done 就是 blocked，沒有 running；blocked 的每張都寫了需要使用者做什麼。
