# 同步已有骨架的 repo

SKILL.md〈探查〉判定 repo 已有骨架時走這份：把它對齊現在的範本，一類一類列出差異，使用者選了才動。`<T>`、`<S>` 同 SKILL.md。

## 1. 盤點

1. 讀指令檔（`AGENTS.md`，或還在用的 `CLAUDE.md`）、`docs/progress.md`，記下進行中的里程碑和還沒做完的票。
2. `python3 <S>/check_docs.py <repo>`：用現在的檢查跑一次，不複製進去。違規逐條留著，第 2 步列進清單。
3. `python3 <S>/scaffold.py --list` 印出每個範本與它在專案裡的路徑。逐檔比對，各歸一類：
   - **照抄檔**（`scripts/` 下的五支腳本與 `scripts/tests/` 的五個測試、`.githooks/commit-msg`、`.githooks/pre-commit`（專案已有自己的 pre-commit 時，把文件檢查接進去，不覆蓋）、`docs/agents/milestone.md`、`docs/agents/ui.md` 與 `docs/agents/visual.md`（專案的指令檔有〈UI〉〈視覺化〉時才要）、`docs/agents/ticket-template.md`、`docs/agents/issue-tracker.md` 的〈Conventions〉清單）：和範本 `diff`。專案自己加的規則列出來，保留。專案用自己的工具做同樣的檢查時（規則寫進專案的測試或 lint，不用 `check_docs.py`）：不複製腳本，改成逐條對 `<S>/check_docs.py` 開頭列的規則，專案沒擋的各列一條。
   - **指令檔**：照 `<T>/instructions.md` 的 `##` 段逐段比對。範本有而專案沒有的規則、專案還在用的舊說法各列一條；專案自己的段落（架構規則、帳號、舊版）原樣保留。
   - **內容檔**（brief、架構、roadmap、progress、decisions、CHANGELOG）：只看結構，內容照舊。
   - **專案檔**（`.gitattributes`、`.github/workflows/ci.yml`、`docs/development.md`、`docs/agents/domain.md`、`docs/agents/triage-labels.md`）：專案沒有的列一條「照範本建」；已有的是專案自己的，保留。

完成條件：每條檢查違規、每個不同的段落都列進第 2 步的清單，或標成「專案自己的，保留」。

## 2. 差異清單

把盤點結果列成清單，每項寫：現況、要改成什麼、動到幾個檔或幾處、會不會打到進行中的票。怎麼改照範本和檢查印的訊息；從比對看不出來的有這幾條：

- 範本新加的格式要求（票上多一種行、檔案多一段）：進行中里程碑裡已經 done 的票和檔補上；已封存在 `docs/archive/` 的不動。
- 照抄檔的用法寫在指令檔裡的（例如 `next_step.py` 的輸出怎麼交給使用者，寫在指令檔〈所有 session 的結尾〉）：兩邊列成同一項，一起現在套或一起開成票。只換了腳本，session 還是會照指令檔的舊說法做。
- 要搬內容的：原本的編號（例如事實的 `F3`）沿用，引用它的地方跟著改。
- 違規多到要改寫內容、或要改上千處引用的：開成 `.scratch/<effort>/` 的工作，改寫附「舊的每個決定 → 新位置」對照表。
- 指令檔的〈UI〉〈視覺化〉還是整段規則的：內文搬到 `docs/agents/ui.md`、`docs/agents/visual.md`（專案自己加的規則跟著搬），指令檔那兩段換成範本的寫法，只留每次改 UI 都要的那一條和指到這兩個檔的一句。
- 探查找到擋路檔：照 SKILL.md〈問一次〉講擋路檔的那兩項問，照 SKILL.md〈寫骨架〉第 4 步處理。
- 範本裡標了「只在…時保留」的段落專案沒有時：探查看得出來的（有沒有 UI、repo 公不公開）照探查；看不出來的（要不要用 `visual-explainer`）放進第 3 步一起問，題目照 SKILL.md〈問一次〉。

## 3. 問一次

向使用者提問（有互動提問工具就用它，否則在對話列點詢問），每項三個選項：**現在套**、**開成票**（寫進 `.scratch/<effort>/`，照專案的 spec 與票格式）、**不做**。附你的建議：

- 會改做票流程的項目（票上要多記什麼、驗收多一步），進行中的里程碑還有票沒做完時，建議等它驗收後再套。
- 要搬動或改寫大量內容的項目建議開成票。

完成條件：差異清單的每一項，使用者都選了現在套、開成票或不做。

## 4. 套用

只做使用者選「現在套」的：

- 照抄檔：覆蓋，再把第 1 步列的專案自己的規則加回去。動到 `.githooks/` 就跑 `git config core.hooksPath .githooks`。
- 搬移內容的：搬完逐行比對，來源刪掉的每一行都在目的地找得到，把比對結果貼給使用者。
- 指令檔：只改列出來的那幾段。
- 還沒套的項目會讓新的 `check_docs.py` 紅：那幾條檢查在專案的副本裡先關掉，旁邊註明由哪張票打開。

完成條件：專案自己的全部檢查通過；套了 `.githooks/` 的，`git config core.hooksPath` 印 `.githooks`；每個「開成票」的項目都有票，被關掉的檢查都對得到一張票；commit `docs: sync agent workflow with project-init`，push 前先問；專案有 `scripts/next_step.py` 時，最後跑它，照專案指令檔〈所有 session 的結尾〉的寫法告訴使用者下一步。
