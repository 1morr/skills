# skills

給 [Claude Code](https://code.claude.com) 用的 skills，打包成一個 plugin。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [bake-off](skills/bake-off/SKILL.md) | `/1morr:bake-off [版數] <prompt 或 prompt 檔> [現成版本…]`（只能手動叫用） | 同一個任務用 [Orca](https://www.onorca.dev) 平行做幾版（也可以加進現成版本），先核可各版計畫，做完逐版渲染審查，建議用哪一版當基礎、還要改什麼、別版有哪些能合進來；各版讀法不同的地方單獨交給你決定 |
| [checkpoint](skills/checkpoint/SKILL.md) | `/1morr:checkpoint [里程碑或 commit 範圍] [想問的事]`（只能手動叫用） | 一個里程碑做完、拆下一個之前：回顧做了什麼、為什麼、對不對、遺留什麼，說明下一個的打算，出一頁臨時回顧頁，對話對齊後把定案寫回 repo 原有的文件 |
| [diff](skills/diff/SKILL.md) | 說「給我 diff 的 html」「前後對照」「展示這個改動」，或由其他 skill 呼叫 | 做一頁給讀者看的前後對照：文件（docx、PDF、HTML、海報、Markdown、文字）逐字比對，或程式改動實跑前後並附證據。比對由腳本算，頁面由模型照內容設計 |
| [explain](skills/explain/SKILL.md) | `/1morr:explain <要解說的東西> [想知道的事]`（只能手動叫用） | 解說 repo 裡某個功能、流程、頁面、機制或里程碑現在怎麼運作：一頁附 Mermaid 圖、每句附來源的臨時 HTML，加上對話追問；不寫進 repo |
| [project-init](skills/project-init/SKILL.md) | `/1morr:project-init [專案一句話]`（只能手動叫用） | 替新專案搭骨架：指令檔 `AGENTS.md`、brief / plan / roadmap / progress 的空殼、票的慣例（含 mattpocock 的 `/setup-matt-pocock-skills` 會寫的設定，不必另外跑；流程本身要用他的 `/to-tickets`、`/implement` 等 skill）、文件格式與 commit message 的檢查和 CI；之後照 brief → plan → 票 → 驗收的流程開發，和 checkpoint、ticket-coordinator 用同一套格式 |
| [review-loop](skills/review-loop/SKILL.md) | `/1morr:review-loop <產出路徑> [補充]`（只能手動叫用） | 一輪一輪審一份成品（作業、海報、報告）到可以交：在自己的 worktree 和分支上改，每輪用 Orca 從最新 commit 另開 worktree 和新 session 當審查員，主對話逐條查證、修改、commit，收斂後做一次精簡審查，最後出一份起點→最終版的總 diff，照授權合併回原分支 |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator <票目錄> [順序] [額度門檻] [同時最多 N 張]`（只能手動叫用） | 當協調者，用 Orca 為每張票開子 session 解票、代答提問、驗收、合併、等 CI，逐張跑完隊列；可設額度門檻與同時上限 |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試]`（只能手動叫用） | 照老師課件把課程、作業或考試教給零基礎的人：左右兩欄的 HTML 導讀頁（左邊逐頁講課件、右邊逐題做例題和作業），還沒交的作業另出答案紙；再出一份練習頁，基本功在頁面上對答案，整題貼回對話批改 |

bake-off、review-loop、ticket-coordinator 共用 [`orca/`](orca/)：協調者的共同流程（`COORDINATOR.md`）、Claude Code TUI 的已知行為（`TUI.md`）和腳本。explain、checkpoint、diff 共用 [`pages/`](pages/)：解說頁的寫法與組頁腳本（`PAGE.md`、`scripts/build.py`）、頁面的配色與字體（`TOKENS.md`）。

## 安裝

在 Claude Code 裡：

```
/plugin marketplace add 1morr/skills
/plugin install 1morr@1morr-skills
```

plugin 不釘版本，`/plugin update 1morr@1morr-skills` 會更新到最新 commit；也可以在 `/plugin` 的 Marketplaces 分頁打開自動更新。

## 用 Orca 的三個 skill 要知道的事

bake-off、review-loop、ticket-coordinator 會用 [Orca](https://www.onorca.dev) 開子 Claude Code session，需要裝好 Orca 和它的 `orca` 指令。

- **子 session 以免確認模式啟動**（`claude --dangerously-skip-permissions`），這樣才能無人值守；它在自己的 worktree 和分支上工作，合併與 push 由協調者照你開工時給的授權做。要換啟動指令，在啟動協調者的環境設 `CHILD_CLAUDE`，例如 `CHILD_CLAUDE="claude --permission-mode acceptEdits"`。
- **腳本預設主分支是 `main`、CI workflow 是 `ci.yml`**；不一樣時 ticket-coordinator 會在開工時查出來並帶給腳本。

### 額度門檻

ticket-coordinator 的額度門檻（例如「5h 80%」）要讀得到目前的用量。Claude Code 只把用量交給狀態列指令，所以要在狀態列指令裡多接一段存檔：

1. 把 [`orca/scripts/save-rate-limits.sh`](orca/scripts/save-rate-limits.sh) 複製到 `~/.claude/`（plugin 的安裝路徑每次更新都會變，不要直接指過去）。
2. 在 `~/.claude/settings.json` 的 `statusLine.command` 前面接上它：`sh ~/.claude/save-rate-limits.sh | <你原本的狀態列指令>`；沒有狀態列指令就寫 `sh ~/.claude/save-rate-limits.sh >/dev/null`。

它把用量存到 `~/.claude/rate-limits.json`。沒設定時，給了門檻的協調者讀不到用量，會停下來問你；沒給門檻就不受影響。

## 開發

把 clone 下來的目錄加成 marketplace，plugin 會直接從這個目錄載入：改完檔案，開新 session 或執行 `/reload-plugins` 就生效，不用 push、不用重裝。

```
claude plugin marketplace add <clone 的路徑>
claude plugin install 1morr@1morr-skills
```

新增 skill：建 `skills/<名稱>/SKILL.md`，plugin 會自動載入；同時在上面的表格加一列。寫法和其他要一起改的地方在 [`AGENTS.md`](AGENTS.md)。

測試（CI 跑的就是這六條）：

```
python -m unittest discover -s tests
uv run --no-project --with python-docx --with pymupdf python -m unittest discover -s skills/diff/tests
python -m unittest discover -s pages/tests
python -m unittest discover -s skills/project-init/tests
bash orca/scripts/selftest.sh
uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
```

檢查 manifest：`claude plugin validate .`。manifest 刻意不寫 `version`（寫了會把使用者釘在那個版本），所以 validator 會提醒缺 `version`，那條可以忽略。

## 授權

MIT
