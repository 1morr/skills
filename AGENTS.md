# skills

跨 harness（Claude Code、Antigravity、Codex 等）共用的 skills，打包成 plugin `1morr`。新增或修改 `SKILL.md`、附屬 md、`orca/` 或 `pages/` 的 md 之前，先載入 `mattpocock-skills:writing-for-agents` skill（用工具載入，或直接讀它的 `SKILL.md`）。

## 結構

| 路徑 | 內容 |
| --- | --- |
| `skills/<名稱>/` | 一個 skill：`SKILL.md`（`name` 等於資料夾名）、`agents/openai.yaml`（手動 skill）、附屬 md、`scripts/`、`tests/` |
| `orca/` | 用 Orca `orchestration` 協調多個 worker 的流程與腳本 |
| `pages/` | 工程檢視頁（如 `diff`）共用的配色字體（`TOKENS.md`，值在 `scripts/tokens.css`）、HTML 頁交付方式（`HANDOFF.md`）與水平溢出檢查（`scripts/overflow.py`） |
| `PRODUCT.md` | tutor 與 dashboard 的使用者定位、設計約束與產品原則（impeccable schema） |
| `tests/` | 本檔規則與骨架契約的檢查 |
| `evals/` | `claude plugin eval` 的案例，一個資料夾一個：`prompt.md`、`case.yaml`、`graders/`、`fixture.sh`。跑法在 README；結果寫到 `evals/results/`，不進 git |

- skill 之間不互連（禁止 `../<other-skill>`）。對方是 model-invoked 就寫「載入 `<名稱>` skill（用工具載入，或直接讀它的 `SKILL.md`）」；跨 skill 共用的底層檔放 `pages/`（或過渡期的 `orca/`），skill 內用標準相對路徑 `../../pages/` 引用。
- `SKILL.md` 與附屬 md 用相對自身位置的標準路徑（如 `scripts/`、`templates/`、`../../pages/`；共用目錄可註明用環境變數 `SKILLS_ROOT` 覆寫），不寫 `${CLAUDE_SKILL_DIR}`、`${CLAUDE_PLUGIN_ROOT}` 或 `$ARGUMENTS`。
- 預設 user-invoked：`SKILL.md` 設 `disable-model-invocation: true`（`description` 單行、不列觸發詞與否定句），並配 `agents/openai.yaml`（`policy.allow_implicit_invocation: false`）。只有模型要自己觸發、或別的 skill 要載入的才是 model-invoked，並加進 `tests/test_repo_rules.py` 的 `MODEL_INVOKED`。

## 同步

新增、改名、刪除 skill，或改了它的叫用方式：同輪改 `README.md` 的表格（連結文字等於資料夾名）與 `.claude-plugin/` 的兩個 manifest。

## 文字

- `SKILL.md` 和附屬 md 用繁體中文；識別符、指令、log、commit message 用英文。
- skill 不替使用者開瀏覽器或分頁（`open`、`xdg-open`、`orca tab create`）：HTML 頁照 `pages/HANDOFF.md` 非阻塞交付。執行者自己用瀏覽器自動化工具檢查頁面不算。
- 執行時讀的檔只寫執行者要做的事。給維護者的規則寫在本檔，例如「改了這支腳本要跑哪個測試」。
- 刪減既有防呆或告誡前，先跑 `git log -S` / `git blame` 查驗當初攔截的故障根因是否已消失。
- 調整 skill 規則時對照真實專案 session 紀錄或產出，行為變更的驗證統一走 `evals/`。

## 腳本

- 開頭的註解或 docstring 寫用法和輸出格式；md 只寫何時跑（可附一行標準呼叫範例），不重抄完整參數清單與輸出格式。
- Python 只用標準函式庫；要第三方套件的用 `uv run --no-project --with <套件>` 跑，並在 CI 的那一步裝。
- 有 Python 腳本的目錄要有 `tests/test_*.py`，並在 CI `.github/workflows/*.yml` 執行。
- tutor 頁面的互動（`skills/tutor/assets/`，和 `build.py`、`practice.py`、`review.py` 產生互動的部分）改過之後，照 `skills/tutor/tests/BROWSER.md` 在瀏覽器走一遍：單元測試只查產出的 HTML。
- tutor 的 `build.py` 只擋會讓導讀頁或下游的頁壞掉的事（離線打不開、連結斷掉、題型對不回來、溢出）。看到一份教得不好的導讀頁時，改 `SKILL.md` 或 `GUIDE.md` 的那一句，再重做那份導讀頁確認有變好；教法不寫成檢查，也不寫成每一段都要有的格式。
- `orca/scripts/` 由 `bash orca/scripts/selftest.sh` 測，要印 `ALL OK`。
- shell 腳本要在 macOS 內建的 bash 3.2 跑：
  - 變數後面緊貼中文寫 `${var}`。3.2 會把中文吃進變數名，`set -u` 下直接退出。
  - 不用 GNU 專屬的 `stat -c`、`touch -d`、`sed -i`。

## 由測試強制的規則

`python -m unittest discover -s tests` 強制的規則，就是 `tests/test_repo_rules.py` 每個 `check_*` 的 docstring，加上 `tests/test_skeleton_contract.py` 開頭那一段。其餘規則靠改的人自查。
