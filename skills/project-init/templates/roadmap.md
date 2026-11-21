# {{PROJECT}} 路線圖

> 里程碑的順序、狀態、開工前要讀什麼。還沒開工的里程碑在下面各有一小節；開工 session（`/to-tickets docs/roadmap.md 拆 <里程碑> 的票`）把那一節細化成 `.scratch/<里程碑>/spec.md`，這裡縮成一行連到它。插入里程碑用小數（`M1.5`），已有的編號不改。不是里程碑的工作也在表裡佔一列，「里程碑」欄以目錄名開頭（`docs-diet 文件瘦身` 對 `.scratch/docs-diet/`）。同時有兩批票時，只有一列是「進行中」，另一列寫明排在誰之後（`未開工，排在 M1 之後`）；`1morr-skel next` 與 `1morr-skel dashboard` 依此排定佇列。

## 里程碑

| 里程碑 | 目標 | 拆票前讀 | 狀態 |
| --- | --- | --- | --- |
| M0 骨架 | repo 骨架與閘門就位，端到端跑通第一條最小的使用路徑 | brief 全文；`ARCHITECTURE.md` 全文 | 未開工。brief 與架構定稿後跑 `/to-tickets docs/roadmap.md 拆 M0 的票` |

狀態以四個詞之一開頭：`未開工`、`進行中`（同時最多一個）、`已驗收`（接封存檔連結）、`不做`（接理由）。

## M0 骨架

目標：repo 骨架與閘門就位，並端到端跑通第一條最小的使用路徑（tracer bullet）。驗收條件待 brief 定案後寫。

第一張票要交付：

- `docs/development.md`〈閘門〉的表每一列都有著落（指令、設定檔，或「不適用：<理由>」）；有指令的加進〈全部檢查〉與 `.github/workflows/ci.yml`，幾秒內跑完的接進 `.githooks/pre-commit`。
- `ARCHITECTURE.md`〈依賴規則〉的強制工具與測試。
- 多個 worktree 可同時跑全部檢查（埠號、暫存目錄與測試資料庫不寫死）。

已經就位（project-init 建的）：`.gitignore`、`.gitattributes`、純 POSIX `sh` 的 `pre-commit` 與 `commit-msg` hooks，以及基礎 `ci.yml`。

## 不排里程碑

驗收與回顧時留下、尚未排入任何里程碑的項目，每條一行、附出處。有 repro 或使用者要求再開票。
