---
name: project-init
description: 替新專案搭好文件、票與閘門的骨架，或把已有的骨架對齊最新範本
disable-model-invocation: true
argument-hint: "[專案一句話]"
---

替一個新專案搭**骨架**：指令檔 `AGENTS.md`、brief / 架構 / roadmap / progress / decisions 的空殼、票的慣例、文件與 commit message 的檢查（pre-commit、commit-msg 兩個 hook 與 CI）。骨架只定流程和格式；需求、技術選型、架構由之後的 session 填：

`/grill-with-docs` 填 brief → 同一個指令寫架構與 roadmap → `/to-tickets docs/roadmap.md 拆 <里程碑> 的票` 開工 → `/implement` 或 `/1morr:ticket-coordinator` 做票 → 驗收票封存 → `/1morr:checkpoint` → 下一個里程碑。

參數：$ARGUMENTS

`<T>` 是 `${CLAUDE_SKILL_DIR}/templates`，`<S>` 是 `${CLAUDE_SKILL_DIR}/scripts`，`<X>` 是 `${CLAUDE_SKILL_DIR}/tests`。

## 1. 探查

1. 目前目錄不是 git repo：問使用者要不要 `git init`。查預設分支名。
2. 已經有 `docs/progress.md`、`docs/plan.md`、`ARCHITECTURE.md`、`docs/roadmap.md` 或 `.scratch/`：這是已有骨架的 repo，改讀 [SYNC.md](SYNC.md) 照它做，下面第 2–6 步不做。
3. 已有的 `AGENTS.md`、README、程式碼：讀過，記下專案名稱、技術棧、現有的檢查指令。
4. 找**擋路檔**：專案目錄和它上面每一層的 `CLAUDE.md`、`.claude/CLAUDE.md`、`CLAUDE.local.md`（`~/.claude/CLAUDE.md` 不算）。有任何一個，Claude Code 就只讀它們、不讀 `AGENTS.md`。
5. `docs/agents/` 在不在：在就是使用者已經跑過 `/setup-matt-pocock-skills`，記下它選的 issue tracker。

完成條件：說得出預設分支、有沒有技術棧、`docs/agents/` 在不在，以及每個擋路檔的位置和內容。

## 2. 問一次

用 AskUserQuestion 一次問完，探查已經知道的不問：

- 專案一句話（參數沒給時）。
- 專案裡的擋路檔：只有 `@AGENTS.md` 一行的直接刪，不用問；其餘的問要把內容併進 `AGENTS.md` 後刪掉，還是保留它並在第一行加 `@AGENTS.md`。
- 專案外（上層目錄）的擋路檔不動。問使用者要在專案根目錄放一個只有 `@AGENTS.md` 一行的 `CLAUDE.md`，還是自己把 `~/.claude/settings.json` 的 `pluginConfigs` → `cc-plugin-agents-md@builtin` → `options.instructionFiles` 設成 `claude-md-and-agents-md`。
- repo 公開還是私有。
- 有沒有 UI。

## 3. 寫骨架

從 `<T>` 複製到專案，已存在的檔不覆蓋、改成把缺的段落補進去：

| 範本 | 寫到 |
| --- | --- |
| `instructions.md` | `AGENTS.md` |
| `design-brief.md` | `docs/design-brief.md` |
| `architecture.md` | `ARCHITECTURE.md` |
| `roadmap.md` | `docs/roadmap.md` |
| `progress.md` | `docs/progress.md` |
| `decisions.md` | `docs/decisions.md` |
| `development.md` | `docs/development.md` |
| `ticket.md` | `docs/agents/ticket-template.md` |
| `gitattributes` | `.gitattributes` |
| `ci.yml` | `.github/workflows/ci.yml` |
| `commit-msg` | `.githooks/commit-msg`（`chmod +x`） |
| `pre-commit` | `.githooks/pre-commit`（`chmod +x`） |
| `issue-tracker.md` | `docs/agents/issue-tracker.md` |
| `triage-labels.md` | `docs/agents/triage-labels.md` |
| `domain.md` | `docs/agents/domain.md` |
| `milestone.md` | `docs/agents/milestone.md` |

另外建空目錄的佔位：`docs/adr/`、`docs/research/`、`docs/archive/`、`scripts/experiments/` 各放一個 `.gitkeep`。

佔位：`{{PROJECT}}` 專案名稱，`{{ONE_LINE}}` 專案一句話（句號結尾），`{{DATE}}` 今天（`YYYY-MM-DD`），`{{MAIN_BRANCH}}` 預設分支。`instructions.md` 裡標了「只在…時保留」的段落照第 2 步的回答留或刪；所有 `<!-- -->` 註解，除了寫明留給 M0 票 01 的，都刪掉。擋路檔照第 2 步的回答處理。

完成條件：專案裡 `grep -rn '{{' docs .github .githooks AGENTS.md ARCHITECTURE.md` 沒有結果；表上每個目的地都有檔；Claude Code 讀得到 `AGENTS.md`：專案裡沒有擋路檔，或擋路檔第一行是 `@AGENTS.md`。

## 4. 票的慣例

`docs/agents/milestone.md` 是里程碑開工與驗收票的步驟，`AGENTS.md` 指向它。另外三個檔告訴 mattpocock 的工程 skill（`/to-tickets`、`/implement`、`code-review`）票放哪、狀態怎麼寫、名詞表在哪。第 3 步寫的是他的 `/setup-matt-pocock-skills` 選「local markdown、預設標籤、單一名詞表」時的結果，加上里程碑的慣例，使用者不必再跑那個指令。

探查時 `docs/agents/issue-tracker.md` 就在的（使用者之前設定過）：

- 是 local markdown 的：把它〈Conventions〉底下的清單換成 `<T>/issue-tracker.md` 同一段的清單，其餘不動。
- 是 GitHub 或別的 tracker：停下來告訴使用者，這套流程和 `/1morr:ticket-coordinator` 只讀 `.scratch/` 裡的票，問他要改用 local markdown 還是到此為止。

完成條件：`docs/agents/issue-tracker.md` 寫著 `.scratch/<milestone>/issues/`、驗收票和 `Status: done`；`triage-labels.md`、`domain.md`、`milestone.md` 都在。

## 5. 閘門

1. 複製 `<S>/check_docs.py`、`<S>/check_commit_msg.py`、`<S>/docs_moved_lines.py` 到專案的 `scripts/`；複製 `<X>/test_check_docs.py`、`<X>/test_check_commit_msg.py`、`<X>/test_docs_moved_lines.py` 到 `scripts/tests/`。
2. `git config core.hooksPath .githooks`。
3. 專案已經有檢查指令（lint、test）：加進 `docs/development.md`〈全部檢查〉和 `ci.yml`。還沒有技術棧就留給 M0 的第一張票，roadmap〈M0 骨架〉已經寫了。

完成條件：下面四條都親自跑過、結果如括號所寫。

```
python3 scripts/check_docs.py                                  # exit 0
python3 -m unittest discover -s scripts/tests                  # OK
python3 scripts/check_commit_msg.py --subject "Add stuff"      # exit 1
sh .githooks/pre-commit                                        # exit 0
```

## 6. 交付

1. commit：`docs: scaffold agent workflow, brief and architecture skeletons`（這一筆會經過剛裝的 commit-msg hook）。push 前先問。
2. 告訴使用者建了哪些檔，並印出下一個 session 要貼的訪談指令，`<…>` 換成實際內容：

   ```
   /grill-with-docs 填 docs/design-brief.md：<專案一句話>。<使用者在這次對話提過的平台、限制、參考產品>
   逐節訪談，每題附你的建議。brief、GLOSSARY.md、ADR 的每段草稿先給我看，我確認後才寫入。
   外部事實先查證，寫進 docs/research/ 並編號。
   ```

3. 要用額度門檻跑整批票的話，照 plugin README〈額度門檻〉設定一次。
