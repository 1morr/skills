# 等使用者決定與使用者插話

[SKILL.md](SKILL.md) 的條件分支：當 worker 提問涉及使用者拍板、整個佇列因阻礙停下、或使用者在執行中途插話時照本檔處理。所有 Orca 指令皆使用 [SKILL.md](SKILL.md)〈1. 解析執行檔與綁定 Run〉選定的 `ORCA` 執行檔（`"$ORCA"`），禁止寫裸 `orca`。

## 等使用者拍板

當 worker 的 `question` 涉及推翻 brief / ADR / 既有架構決策，或專案指令檔明定須人類決定的事項時（同批提問中其餘可查證的子題先查妥備用，等本題有答案一併回覆）：

- **使用者在場**：把題目放在對話回覆最前面（背景一句、選項、偏離哪份既有文件的哪一句、你的建議），直接結束回合等使用者回覆。即使使用者臨時離開，其他並行 worker 的 orchestration 訊息仍會正常叫醒你。
- **使用者不在場**：只擱置這張票與相依票，其餘互不相擋的票照常推進：
  1. **保留 worker 等待狀態**：不呼叫 `reply` 也不關 worker，讓該筆 `msg_id` 留在 `"$ORCA" orchestration inbox --terminal run:<run_id> --full` 待答。
  2. **單寫原則（消除雙寫衝突）**：**協調者絕不在主分支修改 worker 正在做的票檔（如 `.scratch/.../issues/NN-slug.md`）**，避免與票分支產生 `## Comments` 合併衝突。若專案有主分支進度狀態檔（如 `docs/progress.md`），先跑 `python3 scripts/land_ticket.py preflight --repo <repo> --base <主分支>`，僅在主分支狀態檔新增一列 `等使用者：<白話題目>（票 <NN>）` 並做本地 commit（**不跑遠端 `push-ci`**）。
  3. **連帶擱置**：凡 `Blocked by` 這張票、依賴其產出、或會改同一區程式碼的後續票一併暫緩派發。
- **收到使用者回答後**（當場或回來時）：
  1. 判定決定者標記：使用者採納建議記 `（使用者同意）`；自選其他方案或自訂內容記 `（使用者定）`（若推翻既有 brief / ADR，先給使用者確認文件修訂草稿，再讓 worker 隨同本次改動一併更新）。
  2. 執行 `"$ORCA" orchestration reply --id <msg_id> --body "<答案、決定者標記，並指示在票分支寫入決定>" --json`（並在對話輸出一行透明化摘要），**明確指示 worker 在自己的票分支把 `決定：<一句>（使用者定／使用者同意）` 寫進票檔 `## Comments`**，隨票完成時無衝突合併回主分支。
  3. 若先前曾在主分支 `docs/progress.md` 寫過待決列，於該票合入時一併更新或清理，並恢復連帶擱置的後續票。

## 隊列停下時

當觸發 [SKILL.md](SKILL.md)〈5. 使用者互動、異常停機與總表回報〉的「真的卡住」而必須暫停整個佇列時：

1. **不動進行中的票檔**：與上面相同，協調者絕不在主分支觸碰未結算 worker 的票檔；未結算且需待使用者排障後續跑的 worker 維持原狀。
2. **主分支本地留痕**：若專案有主分支狀態檔（如 `docs/progress.md`），跑完 `land_ticket.py preflight` 後在狀態檔本地 commit 一列 `等使用者：<卡點與所需動作>`（**不執行 `push-ci`**，避免浪費遠端 CI 或在壞死環境卡鎖）。
3. **輸出交接資訊**：在回覆最上方列出卡在哪張票、已嘗試過的診斷、需要使用者做的具體動作，並附上續跑綁定指令 `"$ORCA" orchestration run-use --id <run_id>` 與收件匣查詢指令 `"$ORCA" orchestration inbox --terminal run:<run_id> --full`。

## 使用者插話

使用者在佇列進行中提問或要求調整時，處理完即回到原本的等待：

- **問程式碼現況或佇列進度**：
  - 佇列與 worker 狀態直接查 `"$ORCA" orchestration run-show --id <run_id> --json`、`task-list`、`worker-list` 與 `inbox`；
  - 程式碼與設計依據必附真實查證的 `檔案:行`；若發現設計文件／ADR 與程式碼現況不符，單獨列出「文件與程式對不上」詢問使用者修哪一邊，不自行挑一邊當真。
- **要求修改內容**：先用一句話向使用者說明你歸入哪一類，獲同意後執行：
  - **小修**（無須新決策、不推翻既有文件、範圍集中且現有測試可驗）：
    - 相關票正在跑：用 `"$ORCA" orchestration send --to dispatch:<dispatch_id> --subject "scope-update" --body "<修改要求>" --json` 請該 worker 另成一個 commit、補測試並在票面 `## Comments` 記一行 `變更：`（注意 paired server 上已結算的 worker 不接受 `send`）。
    - 尚無相關票在跑：在佇列中下一張會動到該區域的未開工票補上一條驗收條件（跑 `land_ticket.py preflight` 後本地 commit）。
  - **已合入的票做錯了**（與票面或 spec 不符）：建立修復票 `<NN>b-<slug>.md`（驗收條件必含一條重現該問題的會紅測試），排在下一張待開票之前。
  - **變更既有決策／票面／spec／brief**：屬推翻已定決策（記 `使用者定`）；涉及 brief、架構或 ADR 時先給使用者確認修訂草稿，通過後更新文件與受影響的未開票，正在跑的票用 `send --to dispatch:<dispatch_id>` 同步變更。
  - **超出本里程碑的新需求**：寫入 `docs/roadmap.md` 對應里程碑或〈不排里程碑〉；僅在使用者明示「現在就做」時才拆票排入當前佇列。
- **切換在場／不在場**：使用者告知離開時切為「不在場」，回來時切回「在場」（若存有 `run.json` 則同步更新），並在回來時第一時間從 `inbox --terminal run:<run_id> --full` 撈出所有擱置待決題目置頂列出。
