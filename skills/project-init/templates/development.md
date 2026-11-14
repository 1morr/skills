# 開發

開發指令的單一來源。README 只給使用者看。

## 環境

- Python 3.8 以上（只給 `scripts/` 的腳本用，標準函式庫）。
- clone 或新 worktree 後執行一次：`git config core.hooksPath .githooks`。之後每次 commit，`.githooks/pre-commit` 跑下面〈全部檢查〉裡快的那幾條，`.githooks/commit-msg` 檢查訊息格式。

<!-- 技術棧定了之後（M0 的第一張票）補：語言與工具的版本、安裝與建置指令。在裝置或真實服務上怎麼驗、常見故障怎麼排除，也寫在本檔，不寫進 ARCHITECTURE.md。 -->

## 全部檢查

```
python3 scripts/check_docs.py
python3 -m unittest discover -s scripts/tests
```

<!-- M0 的第一張票把這個技術棧的 lint、format、typecheck 與 test 加在這裡，CI 跑同一組；其中幾秒內跑得完的也接進 .githooks/pre-commit，慢的（完整測試、建置）只留在這裡與 CI。 -->

## 閘門

成熟專案從第一天就有的幾道檢查。M0 的第一張票把每一列的「待定」換成指令或設定檔的路徑（寫成行內程式碼），用不到的寫「不適用：<理由>」；有指令的同時加進〈全部檢查〉與 CI。工具照這個技術棧現在的主流選，先查證再定（`AGENTS.md`〈事實與查證〉）；依賴的 lockfile 進版控。有票做完之後還留著「待定」，`scripts/check_docs.py` 會擋。

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

Conventional Commits：`<type>(<scope>): <subject>`，英文祈使句、小寫開頭、無句號，標題不超過 72 字元。type 是 feat、fix、docs、style、refactor、perf、test、build、ci、chore、revert。commit-msg hook 跑 `scripts/check_commit_msg.py` 擋不合格的；照收的例外：git 預設的合併與 revert 訊息，以及合併票用的 `merge: ticket NN <slug>`（正在合併時的訊息一律放行）。
