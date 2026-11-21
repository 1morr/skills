---
name: project-init
description: 替新專案搭通用基礎工程護欄與選配本機跑票骨架，零 Python 腳本拷貝
disable-model-invocation: true
argument-hint: "[專案一句話]"
---

替專案搭兩層解耦的工程骨架：
- **通用基礎工程層**（預設寫入 12 個檔，相容 GitHub Issues、Linear 等任意 tracker）：`AGENTS.md`、`ARCHITECTURE.md`、`docs/` 基礎文件、`.gitignore`、`.gitattributes`、零 Python 依賴的純 POSIX `.githooks/`（`pre-commit`、`commit-msg`）與 GitHub Actions `ci.yml`。業務 repo 內寫入 0 行 Python 腳本。
- **選配 `.scratch/` 跑票層**（`--with-scratch`）：額外寫入 `docs/agents/milestone.md`、`ticket-template.md`、`issue-tracker.md`、`triage-labels.md`、`domain.md` 與 `CHANGELOG.md`。狀態檢查、下一步查詢、票面封存與專案總覽頁統一由共用 CLI `1morr-skel`（或本目錄 `scripts/skel.py`）執行。

本技能的腳本位於同目錄 `scripts/`，範本位於同目錄 `templates/`。

## 1. 探查

1. 若目前目錄不是 git repo：詢問使用者是否執行 `git init`，並確認預設分支名（如 `main`）。
2. 檢查既有專案狀態：
   - 讀已有的 `AGENTS.md`、`README.md` 與設定檔，記下專案名稱、技術棧與現有檢查指令。
   - **專屬指紋識別**：只有同時或任一存在 `.scratch/`（含 `spec.md` 或 `issues/`）或 `docs/agents/milestone.md` 時，才判定為已啟用 `.scratch/` 跑票層的既有專案（僅有 `ARCHITECTURE.md` 或 `docs/roadmap.md` 的普通專案不算）。既有專案執行 `scaffold.py` 時已存在的檔不會被覆寫，只按需補齊缺漏段落或替換輕量 `.githooks/`，不強制改寫歷史紀錄。
3. 檢查**外部外掛可用性**：確認目前環境是否已安裝 `mattpocock-skills`（查看可用 skills 清單，或檢查 `~/.claude/plugins/`、`~/.gemini/config/plugins/` 是否存在 `mattpocock-skills`）。**若未安裝，後續寫入任何文件與交付訊息時，一律改用自然語言工作流描述，禁止寫入 `/grill-with-docs`、`/to-tickets`、`/implement` 等外部斜線指令死連結**。
4. 檢查 `docs/agents/issue-tracker.md` 是否已存在，記下已選定的 issue tracker。
5. 使用 Claude Code 時，檢查專案目錄與上層目錄是否存在擋住 `AGENTS.md` 的 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md`（`~/.claude/CLAUDE.md` 除外）。

完成條件：明確掌握預設分支、技術棧與現有檢查指令、是否已有 `.scratch/` 專屬指紋、`mattpocock-skills` 是否已安裝，以及（Claude Code 下）擋路檔位置。

## 2. 問一次

向使用者一次問齊探查尚未得知的項目（已知的不重複問）：

- 專案一句話定位（呼叫參數未附時）。
- **Issue tracker 選擇**：使用外部 tracker（GitHub Issues、Linear 等，僅搭通用基礎工程層），或啟用本機 `.scratch/` Markdown 跑票層（`--with-scratch`）。
- repo 為公開或私有（決定是否保留 `AGENTS.md`〈公開 repo〉段）。
- 使用 Claude Code 且有擋路檔時：只有 `@AGENTS.md` 的直接刪除；其餘詢問要併入 `AGENTS.md` 後刪除，或在首行加上 `@AGENTS.md`。

完成條件：上述每項皆有探查依據或使用者明確回覆。

## 3. 寫骨架

1. 依第 2 步的選擇執行 `scripts/scaffold.py`：
   - **通用基礎工程層**：`python3 scripts/scaffold.py <專案目錄> --project <專案名稱> --one-line <一句話，句號結尾> --main-branch <預設分支>`（若需 `CHANGELOG.md` 加 `--with-changelog`）。
   - **含選配 `.scratch/` 跑票層**：加上 `--with-scratch`。
2. 輸出標示 `已存在` 的檔案未被覆寫：比對該行附的 `templates/` 範本路徑，將專案缺漏的必要段落補入，保留專案既有內容。
3. 清理 `AGENTS.md`、基礎文件：
   - 依 repo 公開／私有與所選 issue tracker 裁剪條件段落，移除範本引導註解（保留標註待技術棧或 M0 第一張票補齊的提示）。
   - 若環境**未安裝 `mattpocock-skills`**，將 `AGENTS.md`、`docs/progress.md`、`docs/roadmap.md`（及選配的 `docs/agents/milestone.md`）中的外部斜線指令替換為自然語言步驟（例如將 `` `/grill-with-docs 填 docs/design-brief.md` `` 改為 `` `訪談填寫 docs/design-brief.md` ``）。
4. 使用 Claude Code 時，依使用者選擇處理擋路檔，確保 `AGENTS.md` 可被載入。

完成條件：`grep -rnE '\{\{(PROJECT|ONE_LINE|DATE|MAIN_BRANCH)\}\}' <專案目錄>/docs <專案目錄>/.github <專案目錄>/.githooks <專案目錄>/AGENTS.md <專案目錄>/ARCHITECTURE.md` 無未替換佔位符；未裝 `mattpocock-skills` 時無外部死連結；重跑一次 `scaffold.py` 全部印 `已存在`。

## 4. 閘門

1. 在專案目錄執行 `git config core.hooksPath .githooks`。
2. 若專案已有現成 lint / typecheck / test 指令：填入 `docs/development.md`〈閘門〉與〈全部檢查〉，並同步寫入 `.github/workflows/ci.yml`（幾秒內跑完的快檢查可接進 `.githooks/pre-commit`）。尚未決定技術棧則保留「待定」交由 M0 第一張票補齊。
3. 實跑驗證所有護欄與狀態檢查：

```sh
sh .githooks/pre-commit                                        # exit 0
python3 scripts/skel.py check <專案目錄>                        # exit 0
```

並以暫存訊息檔測試 `.githooks/commit-msg`：驗證 `"Add stuff"` 被攔截（`exit 1`），`"docs: init skeleton"`、`Merge branch 'x'` 與 `Revert "docs: init"` 均放行（`exit 0`）。

完成條件：`core.hooksPath` 設為 `.githooks`，`pre-commit`、`commit-msg` 與 `scripts/skel.py check` 實測結果全數符合預期。

## 5. 交付

1. 在專案目錄 commit：`docs: scaffold project engineering guardrails`（通過剛啟用的 `pre-commit` 與 `commit-msg` hooks）；push 前先詢問使用者。
2. 執行 `python3 scripts/skel.py next <專案目錄>`，將下一步指令（替換實際專案一句話與背景限制）放進 code block 交給使用者。
3. 告知使用者已建立的檔案清單，以及後續可透過 `1morr-skel check|next|notes|dashboard`（或 `python3 <本目錄>/scripts/skel.py ...`）檢查狀態、查詢佇列與開啟專案總覽頁（`1morr-skel dashboard <專案目錄> --serve`）。

完成條件：預設分支完成 commit、`git status` 乾淨，且對話已附上立即可用的下一步指令與 `1morr-skel` 用法。
