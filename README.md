# skills

跨 harness（[Claude Code](https://code.claude.com)、Antigravity、Codex 等）共用的 skills，打包成 plugin `1morr`。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [coursework](skills/coursework/SKILL.md) | `/1morr:coursework <哪一科的哪一份作業>`（只能手動叫用） | 做學校的作業或 project：盲讀老師原檔並過濾真歧義由你拍板（多版比較走 [VARIANTS.md](skills/coursework/VARIANTS.md)、只審初稿走 [REVIEW-ONLY.md](skills/coursework/REVIEW-ONLY.md)），成品以盲做與分角度審查驗證；收尾不自動接 `tutor`，需要學做法時可手動呼叫 `/tutor` |
| [diff](skills/diff/SKILL.md) | 說「給我一頁前後對照的 html」「做 diff 頁」，或由其他 skill 呼叫 | 文件兩版（docx、PDF、HTML、Markdown）逐字與表格對照頁，或輸出結構化差異 JSON（`--json-only`）供上游流程使用；改動標記全部由腳本算 |
| [project-init](skills/project-init/SKILL.md) | `/1morr:project-init [專案一句話]`（只能手動叫用） | 替新專案搭通用基礎工程護欄（指令檔、設計與架構空殼、`.gitignore`、純 POSIX git hooks 與 CI）與選配 `.scratch/` 跑票層，零 Python 腳本拷貝；狀態檢查、下一步查詢、票面封存與專案總覽頁由共用骨架 CLI `1morr-skel`（`check` / `next` / `notes` / `dashboard`）提供 |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator [票來源] [agent/模型] [同時最多 N 張]`（只能手動叫用） | 用 Orca `orchestration` 為每張票（`.scratch/` 本地票或 GitHub Issues）開獨立 worktree worker 解票、代答、驗收，並透過 `land_ticket.py` 合併、推送等 CI 與清理（多票並行走 Batch Merge Train） |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試]`（只能手動叫用） | 照老師的課件把課程、作業或考試教會：旁邊跟著課件的導讀頁、練習頁、模擬卷、考前速查，之後批改、解答和帶著做。導讀頁上有作業的做法和答案；要交的那一份檔由 coursework 做 |

`diff` 與 `tutor` 共用 [`pages/`](pages/)：工程檢視頁的配色字體、量水平溢出的腳本，以及把 HTML 頁交給你的非阻塞方式（本機直接給完整路徑，遠端無桌面環境起背景 server 給網址與完整路徑，不替你開瀏覽器）；`project-init` 透過根目錄 [`pyproject.toml`](pyproject.toml) 暴露共用骨架 CLI `1morr-skel`（含自動更新與靜態單檔的專案總覽頁 `1morr-skel dashboard`）；每個檔是什麼見 [`AGENTS.md`](AGENTS.md)〈結構〉。

## 安裝

### Claude Code

透過 marketplace 安裝，叫用為 `/1morr:<skill>`：

```
/plugin marketplace add 1morr/skills
/plugin install 1morr@1morr-skills
```

plugin 不釘版本，`/plugin update 1morr@1morr-skills` 會更新到最新 commit；也可以在 `/plugin` 的 Marketplaces 分頁打開自動更新。

### Antigravity

從本機路徑安裝，叫用為 `/<skill>`：

```
agy plugin install /Users/roxy/orca/projects/skills
```

若安裝到別的路徑、需要手動指定共用目錄（`pages/`），可設環境變數 `SKILLS_ROOT`。

## 用 Orca 的 skill 要知道的事

`ticket-coordinator` 透過 [Orca](https://www.onorca.dev) 的 `orchestration` 指令啟動與管理 worker（支援 `antigravity`、`claude`、`codex` 等 Chat-mode 與 Terminal-mode worker），執行前會依 `ORCA_CLI_COMMAND`、`orca-dev`、`orca-ide`、`orca` 順序解析執行檔。`coursework` 只在專案指令檔指定了別家模型的盲讀者時才走 [ORCA-READER.md](skills/coursework/ORCA-READER.md)，沒有 Orca 也能跑。

- **每個 worker 在自己的 worktree 和分支上工作**，協調者以 Orca Run 紀錄（`run-show`、`task-list`、`worker-list`、`inbox`）為唯一執行期狀態源，續跑用 `orchestration run-use --id <run_id>`。
- **合併、推送等 CI 與清理統一由 `skills/ticket-coordinator/scripts/land_ticket.py` 執行**：預設主分支是 `main`，自動處理無 `origin` 降級、衝突自動 `--abort` 與 `paths-ignore` 放行。

## 開發

把 clone 下來的目錄加成 marketplace，plugin 會直接從這個目錄載入：改完檔案，開新 session 或執行 `/reload-plugins` 就生效，不用 push、不用重裝。

```
claude plugin marketplace add <clone 的路徑>
claude plugin install 1morr@1morr-skills
```

新增 skill：建 `skills/<名稱>/SKILL.md`，plugin 會自動載入；同時在上面的表格加一列。寫法和其他要一起改的地方在 [`AGENTS.md`](AGENTS.md)。

clone 之後設一次 `git config core.hooksPath .githooks`：每次 commit 前會跑第一條（repo 規則，不到一秒）。

測試（各目錄單元測試由 `.github/workflows/test.yml` 在 CI 執行）：

```sh
python3 -m unittest discover -s tests
python3 -m unittest discover -s pages/tests
python3 -m unittest discover -s skills/project-init/tests
python3 -m unittest discover -s skills/ticket-coordinator/tests
python3 -m unittest discover -s tools/tests
uv run --no-project --with python-docx --with pymupdf python -m unittest discover -s skills/diff/tests
uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
```

跑 `evals/` 的案例（現有 `diff-document`、`coursework-ambiguous-calc`、`tutor-zero-prereq` 三組，改 skill 的文字前後各跑一次當對照；會算進用量，CI 不跑）：

```
claude plugin eval . --no-publish --scaffold --allow-tools Bash Write Edit
```

`--no-publish` 讓報告只留在本機；`--scaffold` 讓案例的 `fixture.sh` 在每次執行的空工作目錄裡先放好輸入檔；`--allow-tools` 讓受測的 session 能跑指令和寫檔，指令關在它的沙箱裡。預設每個案例跑三次，並多跑一組沒裝 plugin 的對照；改案例本身時加 `--case <名稱> --runs 1 --ablation none`，只跑一次、不跑對照組。

量某個專案的文件實際被 agent 讀了幾次（調整文件結構前後各跑一次）：`python3 tools/doc_reads.py <repo> [--since YYYY-MM-DD]`。

檢查 manifest：`claude plugin validate .`。manifest 刻意不寫 `version`（寫了會把使用者釘在那個版本），所以 validator 會提醒缺 `version`，那條可以忽略。

## 授權

MIT
