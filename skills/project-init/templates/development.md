# 開發

開發指令的單一來源。README 只給使用者看。

## 環境

- Python 3.8 以上（只給 `scripts/` 的兩支檢查用，標準函式庫）。
- clone 或新 worktree 後執行一次：`git config core.hooksPath .githooks`。之後每次 commit，`.githooks/pre-commit` 跑下面〈全部檢查〉裡快的那幾條，`.githooks/commit-msg` 檢查訊息格式。

<!-- 技術棧定了之後（M0 的第一張票）補：語言與工具的版本、安裝與建置指令。在裝置或真實服務上怎麼驗、常見故障怎麼排除，也寫在本檔，不寫進 ARCHITECTURE.md。 -->

## 全部檢查

```
python3 scripts/check_docs.py
python3 -m unittest discover -s scripts/tests
```

<!-- M0 的第一張票把這個技術棧的 lint、format、typecheck 與 test 加在這裡，CI 跑同一組；其中幾秒內跑得完的也接進 .githooks/pre-commit，慢的（完整測試、建置）只留在這裡與 CI。 -->

## Commit message

Conventional Commits：`<type>(<scope>): <subject>`，英文祈使句、小寫開頭、無句號，標題不超過 72 字元。type 是 feat、fix、docs、style、refactor、perf、test、build、ci、chore、revert。commit-msg hook 跑 `scripts/check_commit_msg.py` 擋不合格的；照收的例外：git 預設的合併與 revert 訊息，以及合併票用的 `merge: ticket NN <slug>`（正在合併時的訊息一律放行）。
