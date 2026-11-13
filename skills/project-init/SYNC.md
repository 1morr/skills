# 同步已有骨架的 repo

repo 已經有 `docs/progress.md`、`docs/plan.md` 或 `.scratch/` 時走這份：把它對齊現在的範本，一類一類列出差異，使用者選了才動。`<T>`、`<S>`、`<X>` 同 SKILL.md。

## 1. 盤點

1. 讀指令檔（`AGENTS.md`，或還在用的 `CLAUDE.md`）、`docs/progress.md`，記下進行中的里程碑和還沒做完的票。
2. `python3 <S>/check_docs.py <repo>`：用現在的檢查跑一次，不複製進去。違規逐條留著，第 2 步歸類。
3. 逐檔比對 SKILL.md〈寫骨架〉表的目的地與〈閘門〉複製的四個檔，各歸一類：
   - **照抄檔**（`scripts/check_docs.py`、`scripts/check_commit_msg.py`、兩個測試、`.githooks/commit-msg`、`docs/agents/milestone.md`、`docs/agents/ticket-template.md`、`docs/agents/issue-tracker.md` 的〈Conventions〉清單）：和範本 `diff`。專案自己加的規則（例如檢查改寫進專案自己的工具）列出來，保留。
   - **指令檔**：照 `<T>/instructions.md` 的 `##` 段逐段比對。範本有而專案沒有的規則、專案還在用的舊說法各列一條；專案自己的段落（架構規則、帳號、舊版）原樣保留。
   - **內容檔**（brief、plan、roadmap、progress）：只看結構，內容照舊。

完成條件：每條檢查違規、每個不同的段落都歸到第 2 步的某一項，或標成「專案自己的，保留」。

## 2. 差異清單

把盤點結果整理成下面幾項，沒有的略過。每項寫：現況、要改成什麼、動到幾個檔或幾處、會不會打到進行中的票。

| 項目 | 怎麼認 | 怎麼改 |
| --- | --- | --- |
| 路線圖 | 沒有 `docs/roadmap.md` | plan 的里程碑章節與 progress 的里程碑表搬進 `<T>/roadmap.md` 的結構；plan 留架構，progress 留 session 紀錄；指令檔的開工指令改成 `docs/roadmap.md` |
| 事實 | brief 有整節的外部事實 | 依主題搬進 `docs/research/`，每條給編號；brief 換成〈事實索引〉；原本的編號（例如 `F3`）沿用 |
| 決策紀錄 | 沒有 `docs/decisions.md`，決定寫在 progress 的偏差段與 `docs/archive/` | 用腳本把 progress 與各封存檔的偏差逐條搬進 `<T>/decisions.md` 的〈紀錄〉，依日期排序，搬完逐行比對沒丟；超過 200 字元的照搬、不改寫。沒標決定者的：進行中里程碑的逐條補，看不出來的問使用者；已封存的標 `（Agent 定）` 並在開頭註明是搬移時補的。專案的檢查只擋搬移之後新增的行 |
| 誰寫 progress | 指令檔要每張票改 `docs/progress.md` | 改成票留 `Session 紀錄：`、合併的人寫；`.gitattributes` 的 `docs/progress.md merge=union` 拿掉 |
| 使用者試 | 驗收票沒有試用這一步 | 加 `docs/agents/milestone.md`，指令檔指向它；進行中里程碑的 spec 補〈使用者試〉 |
| 使用者確認 | 指令檔沒有〈使用者確認〉 | 照範本加 |
| 章節號 | 檢查報「引用了 brief 或 plan 的章節號」 | 少於一百處：逐處改成 ADR 或事實編號。更多：開成 `.scratch/<effort>/` 的工作，或在專案的檢查裡只擋新增 |
| 票號與大小 | 檢查報「寫了票號」或超過字元上限 | 開成 `.scratch/<effort>/` 的工作：只寫現況、搬走細節，改寫附「舊的每個決定 → 新位置」對照表 |
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
