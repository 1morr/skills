# {{PROJECT}} 路線圖

> 里程碑的順序、狀態、開工前要讀什麼。還沒開工的里程碑在下面各有一小節；開工 session（`/to-tickets docs/roadmap.md 拆 <里程碑> 的票`）把那一節細化成 `.scratch/<里程碑>/spec.md`，這裡縮成一行連到它。插入里程碑用小數（`M1.5`），已有的編號不改。不是里程碑的工作（文件瘦身、審計）也在表裡佔一列，「里程碑」欄以它的目錄名開頭（`docs-diet 文件瘦身` 對 `.scratch/docs-diet/`）；`scripts/check_docs.py` 擋有票卻沒列的目錄。

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | repo 骨架與閘門就位，端到端跑通第一條最小的使用路徑 | brief 全文；`ARCHITECTURE.md` 全文 | 未開工。brief 與架構定稿後跑 `/to-tickets docs/roadmap.md 拆 M0 的票` |

狀態以四個詞之一開頭，後面可以接一句說明：`未開工`、`進行中`（同時最多一個）、`已驗收`（接封存檔的連結）、`不做`（接理由）。`scripts/check_docs.py` 強制，總覽頁只看開頭這個詞。

## M0 骨架

目標：repo 骨架與閘門就位，並端到端跑通第一條最小的使用路徑（tracer bullet）。驗收條件待 brief 定案後寫。

第一張票要交付：

- `docs/development.md`〈全部檢查〉補上這個技術棧的 lint、format、typecheck 與 test，CI（`.github/workflows/ci.yml`）跑同一組；幾秒內跑得完的接進 `.githooks/pre-commit`。
- `ARCHITECTURE.md`〈依賴規則〉的強制工具與它的測試。
- 幾張票能在各自的 worktree 同時跑全部檢查：測試用的埠、暫存目錄、資料庫不寫死；進版控的生成物（型別檔、資料包、截圖）由全部檢查重新產生並比對，測試不就地改寫它們。
- 一次只能給一張票用的資源（模擬器、實機、付費帳號）有鎖，拿不到鎖的票等，用法寫在 `docs/development.md`。

已經就位（project-init 建的）：`scripts/` 的 `check_docs.py`、`check_commit_msg.py`、`docs_moved_lines.py`、`ticket_notes.py`，pre-commit 與 commit-msg 兩個 hook，以及只跑文件檢查與腳本測試的 CI。

## 不排里程碑

驗收與回顧時留下、沒有排進任何里程碑的項目，每條一行、附出處。有 repro 或使用者要求再開票。
