# skills

給 Claude Code 用的 skills，打包成 plugin `1morr`。新增或修改 `SKILL.md`、它的附屬 md、`orca/` 或 `pages/` 的 md 之前，先呼叫 Skill 工具載入 `mattpocock-skills:writing-for-agents`。

## 結構

| 路徑 | 內容 |
| --- | --- |
| `skills/<名稱>/` | 一個 skill：`SKILL.md`（`name` 等於資料夾名）、附屬 md、`scripts/`、`tests/` |
| `orca/` | 用 Orca 開子 session 的 skill 共用的流程（`COORDINATOR.md`）、已知行為（`TUI.md`）與腳本 |
| `pages/` | 產出 HTML 頁的 skill 共用的寫法（`PAGE.md`）、配色字體（`TOKENS.md`，值在 `scripts/tokens.css`）、交付方式（`HANDOFF.md`）、組頁與量溢出的腳本和樣式 |
| `tests/` | 本檔規則的檢查 |

- skill 之間不用 `../` 互連。對方是 model-invoked 就寫「呼叫 Skill 工具載入 `<名稱>`」，要跑它的腳本時用 `${CLAUDE_PLUGIN_ROOT}/skills/<名稱>` 定義縮寫；兩個 skill 都要的檔搬到 `orca/` 或 `pages/`。
- `SKILL.md` 用 `${CLAUDE_SKILL_DIR}`、`${CLAUDE_PLUGIN_ROOT}` 定義路徑縮寫（例如 `<O>`、`<P>`、`<S>`），附屬 md 沿用縮寫：Claude Code 只替換 `SKILL.md` 裡的變數。新縮寫要加進 `tests/test_repo_rules.py` 的 `SHORT`。
- 引用別的節寫 `檔名〈節名〉`，節名是那個標題的開頭；`「」` 留給引述的話和畫面上的字。
- 預設 user-invoked：`disable-model-invocation: true`，description 一行、不列觸發詞。只有模型要自己觸發、或別的 skill 要用 Skill 工具載入的才是 model-invoked，並加進 `tests/test_repo_rules.py` 的 `MODEL_INVOKED`。

## 同步

新增、改名、刪除 skill，或改了它的叫用方式：同輪改 `README.md` 的表格（連結文字等於資料夾名），以及 `.claude-plugin/plugin.json`、`marketplace.json` 的 description（每個 skill 一段，寫成 `<名稱>：<一句話>`，用 `；` 分開）。

## 文字

- `SKILL.md` 和附屬 md 用繁體中文；識別符、指令、log、commit message 用英文。
- skill 不替使用者開瀏覽器或分頁（`open`、`xdg-open`、`orca tab create`）：臨時頁的交付照 `pages/HANDOFF.md`，寫進使用者 repo 的頁（tutor）給完整路徑。執行者自己用瀏覽器自動化工具檢查頁面不算。
- 執行時讀的檔只寫執行者要做的事。給維護者的規則寫在本檔，例如「改了這支腳本要跑哪個測試」。

## 腳本

- 開頭的註解或 docstring 寫用法和輸出格式；md 只寫何時跑，不重抄參數。
- Python 只用標準函式庫；要第三方套件的用 `uv run --no-project --with <套件>` 跑，並在 CI 的那一步裝。
- 有 Python 腳本的目錄要有 `tests/test_*.py`。測試指令列在 README〈開發〉，CI 跑同一組。
- `orca/scripts/` 由 `bash orca/scripts/selftest.sh` 測，要印 `ALL OK`。md 只引用腳本的參數順序、輸出的鍵（`handle=`、`gate=`）和 `state=` 的值；改到這些時，`COORDINATOR.md`、`TUI.md` 和三個協調者 skill 的 `SKILL.md` 一起改。
- shell 腳本要在 macOS 內建的 bash 3.2 跑：
  - 變數後面緊貼中文寫 `${var}`。3.2 會把中文吃進變數名，`set -u` 下直接退出。
  - 不用 GNU 專屬的 `stat -c`、`touch -d`、`sed -i`；檔案時間用 `py.sh` 的 `age`。
  - 改完在 macOS 上跑 `selftest.sh`。

## 由測試強制的規則

`python -m unittest discover -s tests` 強制的規則，就是 `tests/test_repo_rules.py` 每個 `check_*` 的 docstring，加上 `tests/test_skeleton_contract.py` 開頭那一段。其餘規則靠改的人自查。
