# 里程碑：規劃、開工、交接與驗收

寫架構的 session、里程碑開工的 session、做驗收票的 session 照這份做。一般票的欄位與紀錄語法見 `docs/agents/ticket-template.md`。

## 寫架構與 roadmap

在 brief 訪談之後、第一個里程碑開工之前，一個 session 做完（不寫 spec、不拆票）：

1. 讀 brief 全文；〈待決〉裡影響架構或順序的題目先問使用者拍板。
2. 寫 `ARCHITECTURE.md` 各節；技術選型先查成熟產品與套件現況，有重大取捨的另寫 ADR。
3. 寫 `docs/roadmap.md`：里程碑表與各里程碑小節（M0 為端到端 tracer bullet）。
4. 草稿經使用者確認後寫入，每個決定在 `docs/decisions.md` 記一條。

完成條件：brief 每個功能皆有歸屬；`1morr-skel check` 通過；`docs/progress.md` 加一列，「下一步」是 `/to-tickets docs/roadmap.md 拆 M0 的票`。

## 開工

入口是在新 session 下 `/to-tickets docs/roadmap.md 拆 <里程碑> 的票`。依序完成四步並 commit：

1. **spec**：將 `docs/roadmap.md` 對應小節細化為 `.scratch/<里程碑>/spec.md`，包含〈目標〉〈範圍〉〈共同規則〉〈驗收〉（分 `### Agent 驗` 與 `### 使用者試`）〈票序〉；roadmap 原小節縮成連結，狀態改為「進行中」（若有另一批未完票，標明 `排在 <誰> 之後`）。
2. **票**：經使用者同意切法後，照 `docs/agents/ticket-template.md` 建立 `.scratch/<里程碑>/issues/NN-slug.md`；最後一張固定為驗收票 `NN-<里程碑>-acceptance.md`，被其他所有票擋。
3. **對程式碼**（已有程式碼時必做）：逐一核對 spec 與每張票提到的路徑、函式、型別與現況假設，不符處附 `檔案:行` 與修法請使用者確認後更新。
4. **收尾**：填妥 spec〈票序〉，`docs/progress.md` 加一列，「下一步」寫第一張票的指令。

完成條件：spec 五段齊備、既有程式碼假設皆已核對、`1morr-skel check` 通過、`docs/progress.md` 最後一列指向第一張票。

## 平行分支撞號與所有 session 的結尾

- **遞增編號撞號處理**：事實編號、ADR 編號、資料庫 migration 等全專案遞增號，平行票在分支上先取當時下一號；合併到主分支若撞號，由合併者把後合併的那張改為下一個空號並同步更新引用處。
- **合併職責**：單張手動 session 做完後在主分支執行 `git merge --no-ff <票分支>`（訊息 `merge: ticket NN <slug>`）；協調者（`/1morr:ticket-coordinator`）派發的 worker 只在票分支 commit，合併留給協調者。
- **Session 結尾交接**：
  1. 非做票 session 在 `docs/progress.md` 加一列，「下一步」寫下一個 session 的完整指令（或 `等使用者：<題目>`）。
  2. commit 後執行 `1morr-skel next`，將待決問題與下一條指令交給使用者。

## 驗收票

依序執行，前一步成立才往下：

1. 從里程碑開工 commit 起執行 `mattpocock-skills:code-review`。
2. 用 `git log --first-parent` 核對主線變更與計畫偏差；查證現況必附 `檔案:行`，若發現設計文件／ADR 與程式不符，單列「文件與程式對不上」問使用者修哪邊。逐條核實 `### Agent 驗` 並在乾淨環境跑過 `docs/development.md`〈全部檢查〉。
3. 將各票 `## Comments` 未處理發現逐條歸位（修掉、寫入後續里程碑或〈不排里程碑〉）。
4. **使用者試與追認**：攤出啟動方式、`### 使用者試` 清單、本段所有 `（Agent 定）` 決策（跑 `1morr-skel notes <里程碑>` 檢視）、未接手遺留與偏差題目請使用者追認，`docs/progress.md`「下一步」寫 `等使用者：試用 <里程碑>` 後結束 session。使用者回覆後：
   - 不滿意處開修復票（`NNb-<slug>`）修完重試；
   - 追認或改定的決策寫回對應文件並標決定者；代測項目記明誰測與哪幾項未經親手試用。
5. **封存**：
   - 執行 `1morr-skel notes --archive <里程碑> --user-trial "<試用結果逐項紀錄>"`，自動將 `docs/progress.md`、`docs/decisions.md` 與各票紀錄無損彙整寫出至 `docs/archive/<里程碑>.md`，並清理原檔已封存列。
   - 若有 `CHANGELOG.md`，將 `1morr-skel notes --changelog <里程碑>` 輸出的條目併入 `## [Unreleased]`（先問使用者是否發版）。
   - 同一個 commit 將 `docs/roadmap.md` 狀態改為「已驗收，封存在 `docs/archive/<里程碑>.md`」，並在 `docs/progress.md` 加一列指向下一階段（`/to-tickets docs/roadmap.md 拆 <下一個里程碑> 的票`）。

完成條件：spec〈驗收〉每條皆有證據或回覆；所有 `（Agent 定）` 決策與發現皆已追認歸位；`docs/archive/<里程碑>.md` 完整產出且 `1morr-skel check` 通過。
