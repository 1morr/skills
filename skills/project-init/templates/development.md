# 開發

開發指令的單一來源。README 只給使用者看。

## 環境

- Python 3.8 以上（只給 `scripts/` 的兩支檢查用，標準函式庫）。
- clone 或新 worktree 後執行一次：`git config core.hooksPath .githooks`。

<!-- 技術棧定了之後（M0 票 01）補：語言與工具的版本、安裝與建置指令。 -->

## 全部檢查

```
python3 scripts/check_docs.py
python3 -m unittest discover -s scripts/tests
```

<!-- M0 票 01 把這個技術棧的 lint、format、typecheck 與 test 加在這裡，CI 跑同一組。 -->

## Commit message

Conventional Commits：`<type>(<scope>): <subject>`，英文祈使句、小寫開頭、無句號，標題不超過 72 字元。type 是 feat、fix、docs、style、refactor、perf、test、build、ci、chore、revert。commit-msg hook 跑 `scripts/check_commit_msg.py` 擋不合格的；照收的例外：git 預設的合併與 revert 訊息，以及合併票用的 `merge: ticket NN <slug>`（正在合併時的訊息一律放行）。
