# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、進行中里程碑的 session 紀錄、偏差與決定。

## 寫法與封存

- session 紀錄一列、偏差一條，整行各不超過 200 字元；細節在票的 `## Comments`、brief、plan 或 ADR，這裡只放指向它們的一句話。
- session 紀錄的「票」欄與偏差每條的開頭都標里程碑（`M0 01`、`{{DATE}} M0 票 01：…`），封存時靠它分。
- 偏差每條標決定者：`（使用者定）`、`（使用者同意）` 或 `（Agent 定）`，意思在 `AGENTS.md`〈使用者確認〉。
- 里程碑驗收時，把它的 session 紀錄與偏差整段移到 `docs/archive/<里程碑>.md`，里程碑表的備註換成那個檔的連結。同一個 commit 把下一個里程碑標成進行中，「下一步」寫 `/1morr:checkpoint <封存的里程碑>`。本檔只留進行中的里程碑。
- 里程碑的閱讀範圍、票序等細節寫在 `.scratch/<里程碑>/spec.md`，里程碑表的備註只寫一句狀態，進行中的那一個以「進行中」開頭。spec 與票留在原處、不搬。
- `python3 scripts/check_docs.py` 強制：四個 `##` 段的順序、session 紀錄是一整張表、每列每條的長度、偏差每條以日期開頭並標決定者、最後一列的下一步、最多一個進行中的里程碑、`.scratch/` 的 spec 與驗收票、票的 `Status:` 行。其餘靠收尾自查。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | brief 全文；plan §1、§4、§5.1 | 未拆票。brief 與 plan 定稿後跑 `/to-tickets docs/plan.md 拆 M0 的票` |

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| {{DATE}} | 框架 | `/1morr:project-init` 建立文件骨架、文件檢查與 commit-msg hook | 新 session 下 `/grill-with-docs` 填 brief，再寫 plan |

## 偏差與決定

- {{DATE}} 框架（Agent 定）：技術棧未定，lint、test 與依賴規則的閘門延到 M0 票 01（plan §4）。
