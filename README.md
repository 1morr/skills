# skills

跨 harness（[Claude Code](https://code.claude.com)、Antigravity 等）共用的 skills，打包成 plugin `1morr`。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [coursework](skills/coursework/SKILL.md) | `/1morr:coursework <哪一科的哪一份作業>`（只能手動叫用） | 做學校的作業或 project：盲讀老師原檔並匿名比對讀法由你拍板（開放式或要多版比較時走 [VARIANTS.md](skills/coursework/VARIANTS.md)），成品做完以盲做與分角度審查驗證 |
| [dashboard](skills/dashboard/SKILL.md) | `/1morr:dashboard [repo 路徑…] [static]`（只能手動叫用） | 開一頁會自動更新的專案總覽：里程碑與票的進度、等你決定的事、決策與變更，可以同時看好幾個 repo；頁面不寫進 repo |
| [diff](skills/diff/SKILL.md) | 說「給我一頁前後對照的 html」「做 diff 頁」，或由其他 skill 呼叫 | 一頁前後對照的 HTML：文件兩版（docx、PDF、HTML、Markdown、文字）逐字比對，或程式改動實跑前後並附證據；改動標記全部由腳本算 |
| [project-init](skills/project-init/SKILL.md) | `/1morr:project-init [專案一句話]`（只能手動叫用） | 替新專案搭文件、票與閘門的骨架，已有骨架的 repo 逐項對齊最新範本。票的設定含 mattpocock 的 `/setup-matt-pocock-skills` 會寫的那些，不必另外跑；之後的流程用他的 `/to-tickets`、`/implement`，格式和 ticket-coordinator、dashboard 共用 |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator [票的位置] [agent/模型] [額度門檻] [同時最多 N 張]`（只能手動叫用） | 用 Orca `orchestration` 為每張票開 worker 解票、代答、驗收、合併、等 CI，逐張跑完隊列；可選 agent/模型、額度門檻與同時上限 |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試]`（只能手動叫用） | 照老師的課件把課程、作業或考試教會：旁邊跟著課件的導讀頁、練習頁、模擬卷、考前速查，之後批改、解答和帶著做。導讀頁上有作業的做法和答案；要交的那一份檔由 coursework 做 |

`ticket-coordinator` 使用 [`orca/`](orca/)：Orca `orchestration` 協調者的共同流程與腳本。`diff`、`tutor`、`dashboard` 共用 [`pages/`](pages/)：工程檢視頁的配色字體、量水平溢出的腳本，以及把 HTML 頁交給你的非阻塞方式（本機直接給完整路徑，遠端無桌面環境起背景 server 給網址與完整路徑，不替你開瀏覽器）；每個檔是什麼見 [`AGENTS.md`](AGENTS.md)〈結構〉。

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

若安裝到別的路徑、需要手動指定共用目錄（`orca/`、`pages/`），可設環境變數 `SKILLS_ROOT`。

## 用 Orca 的 skill 要知道的事

`ticket-coordinator` 透過 [Orca](https://www.onorca.dev) 的 `orca orchestration` 啟動與管理 worker（支援 `antigravity`、`claude`、`codex` 等 agent），需要裝好 Orca 和 `orca` 指令。`coursework` 只在專案指令檔指定了別家模型的盲讀者時才用 Orca，沒有 Orca 也能跑。

- **每個 worker 在自己的 worktree 和分支上工作**，合併與 push 由協調者照你開工時給的授權做。
- **腳本預設主分支是 `main`、CI workflow 是 `ci.yml`**；協調者會在開工時查出來並帶給腳本。
- **`orca/scripts/quota.sh` 與 `orca/scripts/headsup.py` 是 Claude Code 專屬的可選輔助**：使用非 Claude Code agent（如 Antigravity、Codex）時會自動跳過。

### 額度門檻

`ticket-coordinator` 的額度門檻（例如「5h 80%」，僅在使用 Claude Code 時適用）要讀得到目前的用量。Claude Code 只把用量交給狀態列指令，所以要在狀態列指令裡多接一段存檔：

1. 把 [`orca/scripts/save-rate-limits.sh`](orca/scripts/save-rate-limits.sh) 複製到 `~/.claude/`（plugin 的安裝路徑每次更新都會變，不要直接指過去）。
2. 在 `~/.claude/settings.json` 的 `statusLine.command` 前面接上它：`sh ~/.claude/save-rate-limits.sh | <你原本的狀態列指令>`；沒有狀態列指令就寫 `sh ~/.claude/save-rate-limits.sh >/dev/null`。

它把用量存到 `~/.claude/rate-limits.json`。沒設定時，給了門檻的協調者讀不到用量，會停下來問你；沒給門檻或未使用 Claude Code 就不受影響。

## 開發

把 clone 下來的目錄加成 marketplace，plugin 會直接從這個目錄載入：改完檔案，開新 session 或執行 `/reload-plugins` 就生效，不用 push、不用重裝。

```
claude plugin marketplace add <clone 的路徑>
claude plugin install 1morr@1morr-skills
```

新增 skill：建 `skills/<名稱>/SKILL.md`，plugin 會自動載入；同時在上面的表格加一列。寫法和其他要一起改的地方在 [`AGENTS.md`](AGENTS.md)。

clone 之後設一次 `git config core.hooksPath .githooks`：每次 commit 前會跑第一條（repo 規則，不到一秒）。

測試（各目錄單元測試與腳本自檢由 `.github/workflows/test.yml` 在 CI 執行）：

```sh
python3 -m unittest discover -s tests
python3 -m unittest discover -s pages/tests
python3 -m unittest discover -s skills/project-init/tests
python3 -m unittest discover -s skills/dashboard/tests
bash orca/scripts/selftest.sh
uv run --no-project --with python-docx --with pymupdf python -m unittest discover -s skills/diff/tests
uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
```

跑 `evals/` 的案例（改 skill 的文字前後各跑一次當對照；會算進用量，CI 不跑）：

```
claude plugin eval . --no-publish --scaffold --allow-tools Bash Write Edit
```

`--no-publish` 讓報告只留在本機；`--scaffold` 讓案例的 `fixture.sh` 在每次執行的空工作目錄裡先放好輸入檔；`--allow-tools` 讓受測的 session 能跑指令和寫檔，指令關在它的沙箱裡。預設每個案例跑三次，並多跑一組沒裝 plugin 的對照；改案例本身時加 `--case <名稱> --runs 1 --ablation none`，只跑一次、不跑對照組。

量某個專案的文件實際被 agent 讀了幾次（調整文件結構前後各跑一次）：`python skills/project-init/scripts/doc_reads.py <repo> [--since YYYY-MM-DD]`。

檢查 manifest：`claude plugin validate .`。manifest 刻意不寫 `version`（寫了會把使用者釘在那個版本），所以 validator 會提醒缺 `version`，那條可以忽略。

## 授權

MIT
