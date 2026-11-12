---
name: project-init
description: 替新專案搭好文件、票與閘門的骨架，之後照 brief → plan → 票 → 驗收的流程開發
disable-model-invocation: true
argument-hint: "[專案一句話]"
---

替一個新專案搭**骨架**：指令檔、brief / plan / progress 的空殼、票的慣例、文件與 commit message 的檢查。骨架只定流程和格式；需求、技術選型、架構由之後的 session 填：

`/grill-with-docs` 填 brief → 寫 plan → `/to-tickets` 開工 → `/implement` 或 `/1morr:ticket-coordinator` 做票 → 驗收票封存 → `/1morr:checkpoint` → 下一個里程碑。

參數：$ARGUMENTS

`<T>` 是 `${CLAUDE_SKILL_DIR}/templates`，`<S>` 是 `${CLAUDE_SKILL_DIR}/scripts`，`<X>` 是 `${CLAUDE_SKILL_DIR}/tests`。

## 1. 探查

1. 目前目錄不是 git repo：問使用者要不要 `git init`。查預設分支名。
2. 已經有 `docs/progress.md`、`docs/plan.md` 或 `.scratch/`：這個 skill 只管新專案，停下來告訴使用者哪些檔已經在，不覆蓋。
3. 已有的指令檔（`CLAUDE.md`、`AGENTS.md`）、README、程式碼：讀過，記下專案名稱、技術棧、現有的檢查指令。
4. `docs/agents/` 在不在：在就是使用者已經跑過 `/setup-matt-pocock-skills`，記下它選的 issue tracker。

完成條件：說得出預設分支、指令檔現況、有沒有技術棧、`docs/agents/` 在不在。

## 2. 問一次

用 AskUserQuestion 一次問完，探查已經知道的不問：

- 專案一句話（參數沒給時）。
- 指令檔：`CLAUDE.md`（只用 Claude Code），或 `AGENTS.md` 加一個內容是 `@AGENTS.md` 的 `CLAUDE.md`（也用別的 agent）。
- repo 公開還是私有。
- 有沒有 UI。

## 3. 寫骨架

從 `<T>` 複製到專案，已存在的檔不覆蓋、改成把缺的段落補進去：

| 範本 | 寫到 |
| --- | --- |
| `instructions.md` | 第 2 步選的指令檔 |
| `design-brief.md` | `docs/design-brief.md` |
| `plan.md` | `docs/plan.md` |
| `progress.md` | `docs/progress.md` |
| `development.md` | `docs/development.md` |
| `ticket.md` | `docs/agents/ticket-template.md` |
| `gitattributes` | `.gitattributes` |
| `ci.yml` | `.github/workflows/ci.yml` |
| `commit-msg` | `.githooks/commit-msg`（`chmod +x`） |
| `issue-tracker-conventions.md` | 第 4 步的腳本用，不必自己複製 |

另外建空目錄的佔位：`docs/adr/`、`docs/research/`、`docs/archive/`、`scripts/experiments/` 各放一個 `.gitkeep`。

佔位：`{{PROJECT}}` 專案名稱，`{{ONE_LINE}}` 專案一句話（句號結尾），`{{DATE}}` 今天（`YYYY-MM-DD`），`{{MAIN_BRANCH}}` 預設分支。`instructions.md` 裡標了「只在…時保留」的段落照第 2 步的回答留或刪；所有 `<!-- -->` 註解，除了寫明留給 M0 票 01 的，都刪掉。

完成條件：專案裡 `grep -rn '{{' docs .github .githooks <指令檔>` 沒有結果；表上每個目的地都有檔。

## 4. 票的慣例

mattpocock 的工程 skill（`/to-tickets`、`/implement`、`code-review`）要先知道票放哪、狀態怎麼寫、名詞表在哪，平常由使用者執行 `/setup-matt-pocock-skills` 設定。這裡替他做掉：答案固定是 local markdown、預設標籤、單一名詞表，再換上里程碑的慣例。

```
python3 <S>/write_agent_docs.py <專案根目錄>
```

- exit 0：`docs/agents/` 的 `issue-tracker.md`、`triage-labels.md`、`domain.md` 寫好了；指令檔結尾的 `## Agent skills` 段範本已經帶著。
- 印「已存在，沒動」的檔：使用者之前設定過。`issue-tracker.md` 是 local markdown 的，就把它〈Conventions〉底下的清單換成 `<T>/issue-tracker-conventions.md` 的內容（註解那行不要）；是 GitHub 或別的 tracker，停下來告訴使用者：這套流程和 `/1morr:ticket-coordinator` 只讀 `.scratch/` 裡的票，問他要改用 local markdown 還是到此為止。
- exit 2（找不到已安裝的 mattpocock-skills，或它的種子範本格式變了）：請使用者執行 `/setup-matt-pocock-skills`，issue tracker 選 local markdown，做完回來說一聲。這個指令只有使用者能下；他回來後照上一條換清單。

完成條件：`docs/agents/issue-tracker.md` 寫著 `.scratch/<milestone>/issues/`、驗收票和 `Status: done`；`triage-labels.md`、`domain.md` 都在。

## 5. 閘門

1. 複製 `<S>/check_docs.py`、`<S>/check_commit_msg.py` 到專案的 `scripts/`；複製 `<X>/test_check_docs.py`、`<X>/test_check_commit_msg.py` 到 `scripts/tests/`。
2. `git config core.hooksPath .githooks`。
3. 專案已經有檢查指令（lint、test）：加進 `docs/development.md`〈全部檢查〉和 `ci.yml`。還沒有技術棧就留給 M0 票 01，plan §4 已經寫了。

完成條件：下面三條都親自跑過、結果如括號所寫。

```
python3 scripts/check_docs.py                                  # exit 0
python3 -m unittest discover -s scripts/tests                  # OK
python3 scripts/check_commit_msg.py --subject "Add stuff"      # exit 1
```

## 6. 交付

1. commit：`docs: scaffold agent workflow, brief and plan skeletons`（這一筆會經過剛裝的 commit-msg hook）。push 前先問。
2. 告訴使用者：建了哪些檔；下一步在新 session 下 `/grill-with-docs` 填 brief（progress.md 的第一列已經寫了同一句）；要用額度門檻跑整批票的話，照 plugin README〈額度門檻〉設定一次。
