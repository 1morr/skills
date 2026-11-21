# skills

跨 harness（Claude Code、Antigravity 等）共用的 skills，打包成 plugin `1morr`。新增或修改 `SKILL.md`、它的附屬 md、`orca/` 或 `pages/` 的 md 之前，先載入 `mattpocock-skills:writing-for-agents` skill（用工具載入，或直接讀它的 `SKILL.md`）。

## 結構

| 路徑 | 內容 |
| --- | --- |
| `skills/<名稱>/` | 一個 skill：`SKILL.md`（`name` 等於資料夾名）、附屬 md、`scripts/`、`tests/` |
| `orca/` | 用 Orca `orchestration` 協調多個 worker 的 skill 共用的流程（`COORDINATOR.md`）、Claude Code 選項與跨平台行為（`TUI.md`）與腳本 |
| `pages/` | 產出 HTML 頁的 skill 共用的寫法（`PAGE.md`）、配色字體（`TOKENS.md`，值在 `scripts/tokens.css`）、交付方式（`HANDOFF.md`）、組頁與量溢出的腳本和樣式 |
| `PRODUCT.md` | tutor 與 dashboard 的使用者定位、設計約束與產品原則（impeccable schema） |
| `tests/` | 本檔規則的檢查 |
| `evals/` | `claude plugin eval` 的案例，一個資料夾一個：`prompt.md`、`case.yaml`、`graders/`、`fixture.sh`。跑法在 README〈開發〉；結果寫到 `evals/results/`，不進 git |

- skill 之間不用 `../` 互連。對方是 model-invoked 就寫「載入 `<名稱>` skill（用工具載入，或直接讀它的 `SKILL.md`）」；兩個 skill 都要的檔搬到 `orca/` 或 `pages/`。
- `SKILL.md` 用相對自身位置的路徑定義縮寫（`<S>` 是本檔同目錄的 `scripts/`、`<T>` 是 `templates/`、`<O>` 是往上兩層的 `orca/`、`<P>` 是 `pages/`；共用目錄可註明用環境變數 `SKILLS_ROOT` 覆寫），附屬 md 沿用縮寫。不寫 `${CLAUDE_SKILL_DIR}`、`${CLAUDE_PLUGIN_ROOT}` 或 `$ARGUMENTS`；新縮寫要加進 `tests/test_repo_rules.py` 的 `SHORT`。
- 引用別的節寫 `檔名〈節名〉`，節名是那個標題的開頭；`「」` 留給引述的話和畫面上的字。
- 預設 user-invoked：`disable-model-invocation: true`，description 一行、不列觸發詞。只有模型要自己觸發、或別的 skill 要載入的才是 model-invoked，並加進 `tests/test_repo_rules.py` 的 `MODEL_INVOKED`。

## 同步

新增、改名、刪除 skill，或改了它的叫用方式：同輪改 `README.md` 的表格（連結文字等於資料夾名）。

project-init 的範本改動要搬使用者專案裡的資料時：同一個 commit 在 `skills/project-init/SYNC.md`〈差異清單〉加一條搬法，使用者的 repo 都同步過就刪掉它。

## 文字

- `SKILL.md` 和附屬 md 用繁體中文；識別符、指令、log、commit message 用英文。
- skill 不替使用者開瀏覽器或分頁（`open`、`xdg-open`、`orca tab create`）：使用者要當場看的頁照 `pages/HANDOFF.md` 交付，在瀏覽器存進度的頁（tutor）給完整路徑。執行者自己用瀏覽器自動化工具檢查頁面不算。
- 執行時讀的檔只寫執行者要做的事。給維護者的規則寫在本檔，例如「改了這支腳本要跑哪個測試」。

## 腳本

- 開頭的註解或 docstring 寫用法和輸出格式；md 只寫何時跑（可附一行標準呼叫範例），不重抄完整參數清單與輸出格式。
- Python 只用標準函式庫；要第三方套件的用 `uv run --no-project --with <套件>` 跑，並在 CI 的那一步裝。
- 有 Python 腳本的目錄要有 `tests/test_*.py`。測試指令列在 README〈開發〉，CI 跑同一組。
- tutor 頁面的互動（`skills/tutor/assets/`，和 `build.py`、`practice.py`、`review.py` 產生互動的部分）改過之後，照 `skills/tutor/tests/BROWSER.md` 在瀏覽器走一遍：單元測試只查產出的 HTML。
- tutor 的 `build.py` 只擋會讓導讀頁或下游的頁壞掉的事（離線打不開、連結斷掉、題型對不回來、溢出）。看到一份教得不好的導讀頁時，改 `SKILL.md`〈教學計畫〉或 `GUIDE.md` 的那一句，再重做那份導讀頁確認有變好；教法不寫成檢查，也不寫成每一段都要有的格式。
- `orca/scripts/` 由 `bash orca/scripts/selftest.sh` 測，要印 `ALL OK`。日常派發與收發走 `orca orchestration`，腳本負責 preflight、合併、push-ci、worktree 清理與可選的 Claude Code 輔助（`headsup.py`、`quota.sh`）。md 只引用腳本的參數順序與輸出的鍵值（如 `gate=`、`ci=`）；改到這些時，`COORDINATOR.md`、`TUI.md` 和 `skills/ticket-coordinator/SKILL.md` 一起改。
- shell 腳本要在 macOS 內建的 bash 3.2 跑：
  - 變數後面緊貼中文寫 `${var}`。3.2 會把中文吃進變數名，`set -u` 下直接退出。
  - 不用 GNU 專屬的 `stat -c`、`touch -d`、`sed -i`；檔案時間用 `py.sh` 的 `age`。
  - 改完在 macOS 上跑 `selftest.sh`。

## 由測試強制的規則

`python -m unittest discover -s tests` 強制的規則，就是 `tests/test_repo_rules.py` 每個 `check_*` 的 docstring，加上 `tests/test_skeleton_contract.py` 開頭那一段。其餘規則靠改的人自查。
