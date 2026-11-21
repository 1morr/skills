# 開發

開發指令與工程護欄的單一來源。README 只給使用者看。

## 環境

- clone 或新建 worktree 後執行一次：`git config core.hooksPath .githooks`。每次 commit 時，純 POSIX `sh` 的 `.githooks/pre-commit` 擋衝突標記、私鑰與 >2MB 大檔案，`.githooks/commit-msg` 檢查 Conventional Commits 標題格式。

<!-- 技術棧定了之後（M0 的第一張票）補：語言與工具版本、安裝與建置指令、常見故障排除。 -->

## 全部檢查

```sh
sh .githooks/pre-commit
1morr-skel check
```

<!-- M0 的第一張票把這個技術棧的 lint、format、typecheck 與 test 加在這裡，CI 跑同一組；幾秒內跑完的也接進 .githooks/pre-commit。 -->

## 驗證原則（雙 checkout 防快取誤跑）

- 比對修改前後（如 base 與 head 雙 worktree／checkout）實跑驗證時，在採信任何輸出前，先查驗兩邊實際載入的程式碼出處。
- editable install、共用 virtualenv、快取 bundle 或舊程序佔用的監聽 port，常讓某一邊默默跑到另一邊的程式碼。
- 檢查程序實際載入的模組路徑、建置產物目錄、監聽 port 對應的真實 PID，或本次改動獨有的字串標記。
- 每一邊皆出現只可能來自該 checkout 的獨有標記後，實跑結果與截圖才算有效證據；收尾僅依記錄的 PID 關閉背景程序。

## 閘門

成熟專案從第一天就有的幾道檢查。M0 的第一張票把每一列的「待定」換成指令或設定檔路徑（行內程式碼），不適用的寫「不適用：<理由>」；有票做完之後還留著「待定」，`1morr-skel check` 會擋。

| 閘門 | 指令或設定檔 | 擋什麼 |
| --- | --- | --- |
| 格式 | 待定 | 排版不一致造成的無謂 diff |
| Lint | 待定 | 常見的錯誤寫法、沒人用的程式碼 |
| 型別 | 待定 | 型別對不上；語言沒有型別檢查就寫不適用 |
| 單元測試 | 待定 | 行為退化；一條指令跑完全部 |
| 端到端冒煙 | 待定 | 各模組都過、接起來卻跑不動：啟動真的程式，走一次最主要的使用路徑 |
| 密鑰掃描 | 待定 | token、密碼被 commit 進去；接在 pre-commit 與 CI（例如 gitleaks） |
| 依賴漏洞 | 待定 | 用到有已知漏洞的套件（例如 pip-audit、npm audit、osv-scanner） |
| 依賴更新 | 待定 | 依賴長期沒更新；填設定檔的路徑（例如 Dependabot、Renovate 的） |

## Commit message

Conventional Commits：`<type>(<scope>): <subject>`，英文祈使句、小寫開頭、無句號，標題不超過 72 字元。type 是 feat、fix、docs、style、refactor、perf、test、build、ci、chore、revert。`.githooks/commit-msg` 放行 git 預設的 `Merge …`、`Revert "…"` 與合併中的 `merge: ticket NN <slug>`。
