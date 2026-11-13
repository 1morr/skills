# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態與做票的 session 紀錄都在票上。這裡只記進行中里程碑裡不是做票的 session（訪談、規劃、開工、驗收、流程調整）；里程碑的順序、狀態與閱讀指引在 `docs/roadmap.md`，決定在 `docs/decisions.md`。

## 寫法與封存

- 一列不超過 200 字元；細節在票、spec 或 brief，這裡只放指向它的一句話。
- 「票」欄標里程碑（`M0 開工`），封存時靠它分。
- 里程碑驗收時，它的列搬到 `docs/archive/<里程碑>.md`，步驟在 `docs/agents/milestone.md`〈驗收票〉。本檔只留進行中的里程碑。
- `python3 scripts/check_docs.py` 強制的規則列在腳本開頭；本檔的是：兩個 `##` 段的順序、session 紀錄是一整張表、每列的長度、最後一列的下一步。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| {{DATE}} | 框架 | `/1morr:project-init` 建立文件骨架、文件檢查與 commit-msg hook | 新 session 下 `/grill-with-docs 填 docs/design-brief.md` |
