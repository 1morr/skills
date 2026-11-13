# 同步已有骨架的 repo

repo 已經有 `docs/progress.md`、`docs/plan.md`、`ARCHITECTURE.md` 或 `.scratch/` 時走這份：把它對齊現在的範本，一類一類列出差異，使用者選了才動。`<T>`、`<S>`、`<X>` 同 SKILL.md。

## 1. 盤點

1. 讀指令檔（`AGENTS.md`，或還在用的 `CLAUDE.md`）、`docs/progress.md`，記下進行中的里程碑和還沒做完的票。
2. `python3 <S>/check_docs.py <repo>`：用現在的檢查跑一次，不複製進去。違規逐條留著，第 2 步歸類。
3. 逐檔比對 SKILL.md〈寫骨架〉表的目的地與〈閘門〉複製的六個檔，各歸一類：
   - **照抄檔**（`scripts/check_docs.py`、`scripts/check_commit_msg.py`、`scripts/docs_moved_lines.py`、三個測試、`.githooks/commit-msg`、`.githooks/pre-commit`（專案已有自己的 pre-commit 時，把文件檢查接進去，不覆蓋）、`docs/agents/milestone.md`、`docs/agents/ticket-template.md`、`docs/agents/issue-tracker.md` 的〈Conventions〉清單）：和範本 `diff`。專案自己加的規則（例如檢查改寫進專案自己的工具）列出來，保留。
   - **指令檔**：照 `<T>/instructions.md` 的 `##` 段逐段比對。範本有而專案沒有的規則、專案還在用的舊說法各列一條；專案自己的段落（架構規則、帳號、舊版）原樣保留。
   - **內容檔**（brief、架構、roadmap、progress、decisions）：只看結構，內容照舊。

完成條件：每條檢查違規、每個不同的段落都歸到第 2 步的某一項，或標成「專案自己的，保留」。

## 2. 差異清單

把盤點結果整理成下面幾項，沒有的略過。每項寫：現況、要改成什麼、動到幾個檔或幾處、會不會打到進行中的票。

| 項目 | 怎麼認 | 怎麼改 |
| --- | --- | --- |
| 路線圖 | 沒有 `docs/roadmap.md` | plan 的里程碑章節與 progress 的里程碑表搬進 `<T>/roadmap.md` 的結構；plan 留架構，progress 留 session 紀錄；指令檔的開工指令改成 `docs/roadmap.md` |
| 事實 | brief 有整節的外部事實 | 依主題搬進 `docs/research/`，每條給編號；brief 換成〈事實索引〉；原本的編號（例如 `F3`）沿用 |
| 決策紀錄 | 沒有 `docs/decisions.md`，決定寫在 progress 的偏差段 | 照 `<T>/decisions.md` 建檔，把進行中里程碑的偏差搬進〈紀錄〉，逐條補決定者（看不出來的問使用者），超過 200 字元的把細節留在票上並連過去。已封存在 `docs/archive/` 的不動：總覽頁會讀封存檔的〈決定〉與舊的〈偏差與決定〉 |
| 誰寫 progress | 指令檔要每張票改 `docs/progress.md` | 改成票留 `Session 紀錄：`、合併的人寫；`.gitattributes` 的 `docs/progress.md merge=union` 拿掉 |
| 使用者試 | 驗收票沒有試用這一步 | 加 `docs/agents/milestone.md`，指令檔指向它；進行中里程碑的 spec 補〈使用者試〉 |
| 使用者確認 | 指令檔沒有〈使用者確認〉 | 照範本加 |
| 架構文檔 | 有 `docs/plan.md`，沒有 `ARCHITECTURE.md` | 操作步驟（建置、在裝置上驗、排除故障）整段搬到 `docs/development.md`，逐行比對沒丟；剩下的搬到根目錄的 `ARCHITECTURE.md`、拿掉節的編號，引用它的地方跟著改。還超過 15,000 字元：開成 `.scratch/<effort>/` 的工作，一節一張票，改寫附「舊的每個決定 → 新位置」對照表，那之前專案的檢查先放寬這個上限並註明由哪張票收回 |
| 章節號 | 檢查報「引用了 brief 或架構文檔的章節號」 | 用腳本把編號換成節的標題（`plan §4` → `architecture〈開發環境與閘門〉`）；程式碼引用上千處、文件又還沒瘦身的，在專案的檢查裡只擋新增 |
| 票號與大小 | 檢查報「寫了票號」或超過字元上限 | 開成 `.scratch/<effort>/` 的工作：只寫現況、搬走細節，改寫附「舊的每個決定 → 新位置」對照表 |
| 文件的位置 | 檢查報「指令檔沒有提到它」或「日期放在檔名最後」 | 還在用的：在指令檔〈文件〉加一行。不再維護的（舊版的文件、審計快照）：搬進 `docs/legacy/`，連到它的地方跟著改。`docs/development.md` 被舊文件佔用時先把舊的搬走，新的才用這個名字。`docs/research/` 裡日期不在最後的改名 |
| 里程碑狀態 | 檢查報「狀態要以…其中一個開頭」 | 改寫每列狀態開頭的詞（「完成，已封存」→「已驗收，封存在 …」），其餘照舊 |
| 沒列的工作 | 檢查報「里程碑表沒有列它」 | 在里程碑表加一列，「里程碑」欄以目錄名開頭 |
| 擋路檔 | 指令檔是 `CLAUDE.md` | 照 SKILL.md 第 2 步問 |

## 3. 問一次

用 AskUserQuestion，每項三個選項：**現在套**、**開成票**（寫進 `.scratch/<effort>/`，照專案的 spec 與票格式）、**不做**。附你的建議：

- 會改做票流程的項目（誰寫 progress、使用者試），進行中的里程碑還有票沒做完時，建議等它驗收後再套。
- 要搬動大量內容的項目（路線圖、事實、章節號、票號與大小）建議開成票。

## 4. 套用

只做使用者選「現在套」的：

- 照抄檔：覆蓋，再把第 1 步列的專案自己的規則加回去。
- 搬移（路線圖、事實）：搬完逐行比對，來源刪掉的每一行都在目的地找得到，把比對結果貼給使用者。
- 指令檔：只改列出來的那幾段。
- 還沒套的項目會讓新的 `check_docs.py` 紅：那幾條檢查在專案的副本裡先關掉，旁邊註明由哪張票打開。

完成條件：專案自己的全部檢查通過；每個「開成票」的項目都有票，被關掉的檢查都對得到一張票；commit `docs: sync agent workflow with project-init`，push 前先問。
