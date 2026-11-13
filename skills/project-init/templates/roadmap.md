# {{PROJECT}} 路線圖

> 里程碑的順序、狀態、開工前要讀什麼。還沒開工的里程碑在下面各有一小節；開工 session（`/to-tickets docs/roadmap.md 拆 <里程碑> 的票`）把那一節細化成 `.scratch/<里程碑>/spec.md`，這裡縮成一行連到它。插入里程碑用小數（`M1.5`），已有的編號不改。

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | repo 骨架與閘門就位，端到端跑通第一條最小的使用路徑 | brief 全文；`ARCHITECTURE.md` 全文 | 未開工。brief 與架構定稿後跑 `/to-tickets docs/roadmap.md 拆 M0 的票` |

狀態只寫一句，進行中的那一個以「進行中」開頭，驗收後換成 `docs/archive/<里程碑>.md` 的連結。

## M0 骨架

目標：repo 骨架與閘門就位，並端到端跑通第一條最小的使用路徑（tracer bullet）。驗收條件待 brief 定案後寫。

第一張票要交付：

- `docs/development.md`〈全部檢查〉補上這個技術棧的 lint、format、typecheck 與 test，CI（`.github/workflows/ci.yml`）跑同一組；幾秒內跑得完的接進 `.githooks/pre-commit`。
- `ARCHITECTURE.md`〈依賴規則〉的強制工具與它的測試。
- 幾張票能在各自的 worktree 同時跑全部檢查：測試用的埠、暫存目錄、資料庫不寫死；進版控的生成物（型別檔、資料包）由全部檢查重新產生並比對。

已經就位（project-init 建的）：`scripts/check_docs.py`、`scripts/check_commit_msg.py`，pre-commit 與 commit-msg 兩個 hook，以及只跑這兩支腳本的 CI。

## 不排里程碑

驗收與回顧時留下、沒有排進任何里程碑的項目，每條一行、附出處。有 repro 或使用者要求再開票。
