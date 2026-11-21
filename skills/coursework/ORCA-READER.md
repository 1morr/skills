# 別家模型的盲讀者（Orca 選配分支）

只有在專案指令檔明確指定了別家 agent（與選配模型）做盲讀時，才在 [SKILL.md](SKILL.md)〈1. 盲讀〉第 3 步讀這份。同一個模型的子代理可能共享相同的讀題偏誤，換一家模型獨立讀一次原檔能補捉共同盲點。

## 1. 解析 `ORCA` 執行檔與載入規範

1. 先載入 `orchestration` skill（用工具載入，或直接讀它的 `SKILL.md`）。
2. 依序選定當前環境對應的單一執行檔（以下以 `ORCA` 代稱，執行時直接替換為實際執行檔名，**嚴禁硬寫裸 `orca`**）：
   - 環境變數 `ORCA_CLI_COMMAND` 已設定時，用它的值（WSL 受管環境）。
   - 否則環境變數 `ORCA_DEV_REPO_ROOT` 已設定時，用 `orca-dev`。
   - 否則在 Linux 非 Orca 終端環境下，用 `orca-ide`（Linux 外部環境的裸 `orca` 常指向 `/usr/bin/orca` 螢幕閱讀器）。
   - 其他環境用 `orca`。
3. 執行一次 `ORCA skills get orchestration` 確認版本契約。若選定的執行檔不存在或無法連線 Orca，告知使用者錯誤訊息並跳過別家盲讀，不切換其他執行檔。

## 2. 工作區檢查（只用 `--worktree current`）

- 別家盲讀 worker 共用你目前所在的已納管 Orca 工作區，固定傳 `--worktree current`（不傳 `--repo` 等新建工作區旗標）。
- **非已納管工作區直接跳過**：若目前對話不在 Orca 已納管工作區內，或課程資料夾是未納管的外部目錄導致 worker 無法存取，直接告知使用者並跳過別家盲讀，只用本地盲讀單比對。**嚴禁傳必敗的 `--worktree path:<課程資料夾>`**，也不對使用者資料夾執行 `git init`。

## 3. 專用 Worker Spec 與派發

系統會在 `worker-start` 時自動注入 orchestration preamble 指導 worker 以 `worker_done` 結算回報。**不可直接套用 [read.md](templates/read.md) 末行「最後一則訊息只寫…」的限制**，否則會壓制 preamble 導致未結算停機。

在暫存目錄為這位盲讀者單獨建一個子資料夾，寫入專用任務檔 `<spec_file>`：

```text
讀 <read.md 的完整路徑> 的〈能讀什麼〉〈閱讀順序〉〈讀法單〉照做（忽略該檔開頭的 prompt 區塊與末行回覆限制）。
課程資料夾：<完整路徑>
使用者說要做的：<他的原話>
不讀的路徑清單：<一個檔的完整路徑>
輸出檔：<該盲讀者專屬暫存資料夾下的完整路徑>

你只讀原檔、不修改課程資料夾任何檔案。把十一欄讀法單完整寫進「輸出檔」後，依照你收到的 Orca orchestration preamble 完成結算回報（worker_done），在摘要寫明輸出檔路徑與第 8、9、10 欄各幾條。若寫入外部暫存目錄遇到權限限制，直接把完整十一欄讀法單放在結算報告內文。
```

啟動指令（僅在專案指令檔指定了模型時才加 `--model <模型>`）：

```text
ORCA orchestration worker-start --spec-file <spec_file> --task-title "blind-read" --worktree current --agent <agent> [--model <模型>]
```

使用者在介面上只看得到簡短系統通知：每次派發與收到回報時，在對話寫一行交代對象、送出或收到什麼、輸出檔完整路徑。

## 4. 收訊、處理 `escalation` 與收尾釋放

1. 派發後照常完成主對話讀法單封存與本地盲讀子代理；若外部 worker 尚未回報，結束回合等 Orca 喚醒（不輪詢 `check`）。喚醒訊息若指示跑 `ORCA orchestration check --run <run_id>`，照指令執行。
2. **讀取讀法單（無 `reportPath` 欄位）**：Orca 回報沒有 `reportPath` 欄位。收到 `worker_done` 後，**直接讀取你在 `<spec_file>` 指定的 `輸出檔` 完整路徑**；若該檔不存在，改跑 `ORCA orchestration worker-read --dispatch <dispatch_id> --source auto` 取回讀法單內容。同樣先查第 11 欄確認未誤讀學生檔案。
3. **處理 `escalation` 與逾時**：
   - **權限提示（含 `approval` ID）**：agent 不能代按允許。若 worker 因執行非必要指令卡在權限提示，跑 `ORCA orchestration deny --dispatch <dispatch_id> --prompt <approval_id> --reason "改用 pdftotext 或將讀法單直接放在結算內文"` 讓它繼續；若屬必要讀取權限則請使用者在 Orca 放行。
   - **未結算停機（含 `stopReason`）**：先檢查 `輸出檔` 是否已寫妥；未寫妥時可用 `ORCA orchestration send --to dispatch:<dispatch_id> --subject "finish blind read" --body "請寫入輸出檔並依 preamble 回報 worker_done"` 補催一次。
   - **逾時或啟動失敗**：若 worker 啟動失敗，或耗時超過本地盲讀子代理兩倍仍未回報，告知使用者，執行 `ORCA orchestration worker-stop --dispatch <dispatch_id> --json` 後先用已回來的讀法單比對。
4. **收尾釋放資源**：讀法單取回（或放棄並停止）且該 dispatch 已 settled 後，執行 `ORCA orchestration worker-release --dispatch <dispatch_id> --json` 釋放受監管終端資源。
