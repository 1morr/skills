# skills

給 [Claude Code](https://code.claude.com) 用的 skills，打包成一個 plugin。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [audit](skills/audit/SKILL.md) | `/1morr:audit [要審的 skill、指令檔或路徑]`（只能手動叫用） | 審查 skill 或指令檔（任何 repo，`~/.claude` 底下的也可以），標準是 mattpocock 的 `writing-for-agents`。先列發現，你回答後一步一個 commit 改完；改行為的可以先試跑再決定留不留 |
| [bake-off](skills/bake-off/SKILL.md) | `/1morr:bake-off [版數] <要做的任務>`（只能手動叫用） | 同一個任務用 [Orca](https://www.onorca.dev) 平行做幾版（也可以加進現成版本），逐版渲染審查後建議用哪一版當基礎；各版讀法不同的地方交給你決定 |
| [checkpoint](skills/checkpoint/SKILL.md) | `/1morr:checkpoint [剛做完的里程碑，或想問的事]`（只能手動叫用） | 里程碑之間：回顧上一段做了什麼、對不對、遺留什麼，和你對齊下一段的計畫。出一頁臨時回顧頁，定案寫回 repo 原有的文件 |
| [coursework](skills/coursework/SKILL.md) | `/1morr:coursework <哪一科的哪一份作業>`（只能手動叫用） | 做學校的作業或 project：先找出題目檔並對課程網站，再用三個沒看過對話的子代理各自只讀老師的原檔（專案指令檔指定了別家模型的 agent 時，用 [Orca](https://www.onorca.dev) 多開一個），和主對話的讀法匿名比對；讀法不同的地方附原文和建議由你決定，再出計畫。成品在主對話做一版，做完由一個只看老師原檔的子代理從頭重算、幾個子代理分角度審查；最後把做法寫進 tutor 的導讀頁，並用一個只拿到那一頁的子代理照著重做來確認教得會 |
| [dashboard](skills/dashboard/SKILL.md) | `/1morr:dashboard [repo 路徑…] [static]`（只能手動叫用） | 開一頁會自動更新的專案總覽：里程碑與票的進度、等你決定的事、決策與變更，可以同時看好幾個 repo；頁面不寫進 repo |
| [diff](skills/diff/SKILL.md) | 說「給我一頁前後對照的 html」「做 diff 頁」，或由其他 skill 呼叫 | 一頁前後對照的 HTML：文件兩版（docx、PDF、HTML、Markdown、文字）逐字比對，或程式改動實跑前後並附證據；改動標記全部由腳本算 |
| [explain](skills/explain/SKILL.md) | `/1morr:explain <要解說的東西>`（只能手動叫用） | 解說 repo 裡某樣東西現在怎麼運作：一頁附圖、每句附來源的臨時 HTML，加上對話追問；不寫進 repo |
| [project-init](skills/project-init/SKILL.md) | `/1morr:project-init [專案一句話]`（只能手動叫用） | 替新專案搭文件、票與閘門的骨架，已有骨架的 repo 逐項對齊最新範本。票的設定含 mattpocock 的 `/setup-matt-pocock-skills` 會寫的那些，不必另外跑；之後的流程用他的 `/to-tickets`、`/implement`，格式和 checkpoint、ticket-coordinator、dashboard 共用 |
| [review-loop](skills/review-loop/SKILL.md) | `/1morr:review-loop <要審的成品>`（只能手動叫用） | 一輪一輪審一份成品（作業、海報、報告）到可以交：每輪用 Orca 另開新 session 當審查員，主對話查證後修改，最後出一份起點→最終版的總 diff |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator [票的位置] [額度門檻] [同時最多 N 張]`（只能手動叫用） | 用 Orca 為每張票開子 session 解票、代答提問、驗收、合併、等 CI，逐張跑完隊列；可設額度門檻與同時上限 |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試]`，或由 coursework 載入 | 照老師的課件把課程、作業或考試教會：旁邊跟著課件的導讀頁、練習頁、模擬卷、考前速查，之後批改、解答和帶著做。導讀頁上有作業的做法和答案；要交的那一份檔由 coursework 做 |

bake-off、review-loop、ticket-coordinator 共用 [`orca/`](orca/)：協調者的共同流程、Claude Code TUI 的已知行為和腳本。explain、checkpoint、diff 共用 [`pages/`](pages/)：頁面的寫法、配色字體、組頁與量水平溢出的腳本，以及把頁面交給你的方式（開本機 server，在對話給網址和完整路徑，不替你開瀏覽器），dashboard 的靜態頁、bake-off 和 review-loop 要你看的頁也照這個方式交；每個檔是什麼見 [`AGENTS.md`](AGENTS.md)〈結構〉。

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
- **腳本預設主分支是 `main`、CI workflow 是 `ci.yml`**；協調者會在開工時查出來並帶給腳本。

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

clone 之後設一次 `git config core.hooksPath .githooks`：每次 commit 前會跑第一條（repo 規則，不到一秒）。

測試（CI 跑的就是這幾條）：

```
python -m unittest discover -s tests
uv run --no-project --with python-docx --with pymupdf python -m unittest discover -s skills/diff/tests
python -m unittest discover -s pages/tests
python -m unittest discover -s skills/project-init/tests
python -m unittest discover -s skills/dashboard/tests
bash orca/scripts/selftest.sh
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
