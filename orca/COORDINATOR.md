# 協調者共同流程

用 Orca `orchestration` 協調多個 worker 的 skill（目前為 `ticket-coordinator`）都照這份做；各 skill 只寫自己獨有的步驟。`<O>` 是這個資料夾（repo 根目錄的 `orca/`），腳本在 `<O>/scripts/`，每支開頭寫了用法和輸出。Claude Code 專屬選項（Heads up、額度門檻）與跨平台注意事項在 [TUI.md](TUI.md)：只在 worker 或協調者是 Claude Code，或遇到跨平台問題時才讀它。

## 開工

1. 載入 `orchestration` skill（用工具載入，或直接讀它的 `SKILL.md`），執行 `orca skills get orchestration` 取得與本機 Orca 版本一致的指引。再跑 `orca status --json` 確認 Orca 在跑；要開獨立 worktree 時跑 `orca repo list --json` 找 repo 選擇器（`id:<repoId>`）。
2. 建立本次協調的 Run：`orca orchestration run-create --objective "<目標>" --json`，記下 `runId`。**開工訊息立即附上** `orca orchestration inbox --terminal run:<run_id> --full` 給使用者，方便他隨時查看完整往來內容。
3. 建立持久化的 run 目錄（重開機不消失、換 harness 也能續跑）：`mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/1morr/runs/<repo 名>-<run_id>"`，在裡面建 **ledger**（`ledger.md`），並在開工訊息印出 `ledger.md` 的完整路徑，方便使用者或重開機後的其他 harness 直接接手。你的上下文會被壓縮：**每次被叫醒先讀 ledger**，每個決定當下寫進去。「目前」段記這一場的 `SKILL.md` 和本檔的完整路徑（壓縮後流程不在上下文就重讀這兩份）、repo、orca repo 選擇器、`runId`、主分支、CI、worker 預設 agent 與模型（有指定才填）、〈授權〉的答案，再加各 skill 列的欄位。
4. 查**主分支**（`git symbolic-ref --short refs/remotes/origin/HEAD`；沒有 remote 就是使用者目前的分支）和 **CI**（`.github/workflows/` 裡 push 主分支時會跑的 workflow 檔名；沒有就記「沒有 CI」）。腳本預設 `main` 和 `ci.yml`，每次呼叫都帶上：`merge-ticket.sh` 前面加 `BASE=<主分支>`，`preflight.sh <repo> <主分支>`，`push-ci.sh <repo> <workflow 檔名> <分支>`。

完成條件：`orca status` 回報在跑；已建 `runId` 並把 `orca orchestration inbox --terminal run:<run_id> --full` 與 `ledger.md` 完整路徑印給使用者；ledger「目前」段有主分支、CI（或「沒有 CI」）、`runId` 與預設 worker agent。

## 授權

和各 skill 開工要問的事放在同一次向使用者提問（有互動提問工具就用它，否則在對話列點詢問），答案寫進 ledger：

- worker 要用哪個 agent（如 `antigravity`、`claude`、`codex`；未指定則沿用協調者目前的 agent）與模型（選填，對應 `--model`）。
- push 和其他對外動作（開 PR、issue、release、部署）：可以直接做，還是每次先給使用者看。
- 破壞性 git 操作前：「建備份」還是「直接執行」。

## 對話透明化

終端模式下使用者在畫面上只看得到簡短到達通知（例如「You have 1 orchestration message」），看不到往來全文。**以下兩條強制執行**：

- **協調者**：每次送出派發（`worker-start`）、回覆提問（`reply`）、送出指示（`send`），或透過 `check` / `inbox` 收到 worker 訊息時，在對話寫一行摘要：**對象**（工作名與 `dispatchId`）、**送出或收到什麼**、以及**相關檔案的完整路徑**。
- **Worker spec**：每份交給 worker 的 spec 檔都寫明同一條規則——worker 每次呼叫 `ask`、收到 `reply` / `send`、或送出 `worker_done` 時，都在自己的對話寫一行摘要（對象、送出或收到什麼、檔案完整路徑）。

## Worker 的一輪

1. **開**：把完整任務寫成 run 目錄裡的 spec 檔（含〈對話透明化〉規則）。若要 worker 照某個 skill 做，在 spec 裡直接寫明「讀取 `<SKILL.md 完整路徑>` 並照做」，避免依賴 prompt 開頭的斜線指令展開（`worker-start` 會在 spec 前加上 orchestration preamble）。接著啟動 worker：

   ```text
   orca orchestration worker-start --run <run_id> --spec-file <spec 路徑> --task-title "<標題>" --worktree new-top-level --repo <repo 選擇器> --name <worktree 名> --base-branch <主分支> --agent <agent> [--model <模型>] --json
   ```

   需要共用協調者目前工作區時改傳 `--worktree current`（省略 `--repo`、`--name`、`--base-branch`）；使用者要留著終端續聊時加 `--keep-open`。從回執把 `taskId`、`dispatchId`、worktree 路徑（`worktreeId` 中 `::` 後段）與終端 handle 寫進 ledger，並在對話寫一行派發摘要。啟動失敗時不要直接重跑：讀 `failedStage`，跑 `orca skills get orchestration --reference references/recovery-and-cleanup.md` 依指引處理。
2. **等**：把目前互不相擋的 worker 都開出去後，**直接結束回合等 Orca 叫醒**。不要自己寫輪詢或背景監看腳本（背景跑 `check` 會提前消費未讀訊息，讓 Orca 沒有訊息能叫醒你）。
3. **被叫醒**：先讀 ledger。若叫醒訊息未附全文，跑 `orca orchestration check --run <run_id> --json` 讀取未讀批次（上下文壓縮後要補查歷史用 `orca orchestration inbox --terminal run:<run_id> --limit 50 --full`），並在對話寫一行收到摘要。若該 worker 是 Claude Code，這時順便查 Heads up（見〈Heads up〉）；其他 agent 跳過。依訊息類型處理：
   - **`question`**（worker 呼叫 `ask`）：答什麼照各 skill。送出 `orca orchestration reply --id <msg_id> --body "<答案>"`，把「題目 → 答案 → 理由」寫進 ledger，並在對話寫一行送出摘要。
   - **`worker_done`**：先檢查結果是 `succeeded` 還是 `failed`；回報失敗的任務不能標成完成。需要讀長輸出或確認細節時跑 `orca orchestration worker-read --dispatch <dispatch_id>`。驗收與後續照各 skill。
   - **`escalation`**：
     - 帶 `approval` 或顯示停在本地互動提示（權限確認或本地提問工具）：訊息無法直接代答；先繼續處理其他工作等使用者回應，確實卡住任務時用 `orca orchestration deny` 附理由拒絕，或照各 skill 轉告使用者。
     - 沒送 `worker_done` 就停下（`stopReason`）：用 `worker-read --dispatch <dispatch_id>` 看最後輸出，用 `send` 叫它繼續完成或回報 `worker_done`。
     - `exited` 或 `lost`：用 `worker-show --dispatch <dispatch_id>` 確認後，依 `references/recovery-and-cleanup.md` 決定 `--retry-of <dispatch_id>` 或回報使用者。
   - **要人做事**：只有使用者本人才有的（密碼、登入、2FA、實體操作、付款）才轉給使用者；worker 或你查得到、做得到、驗得到的，用 `send` 叫它自己做並說明做法。
4. **追問或補做**：不論 worker 仍在跑或已結算，一律用：

   ```text
   orca orchestration send --to dispatch:<dispatch_id> --subject "<主題>" --body "<指示>"
   ```

   已自動關閉的本地 worker 會被重新喚起為後續任務，完成後一樣以 `worker_done` 回報。每次送出都在對話寫一行摘要。
5. **收**：`worker_done` 結算後 Orca 會在約 2 分鐘後自動釋放終端（釋放後仍可用 `worker-read` 讀歸檔）；要立刻釋放跑 `orca orchestration worker-release --dispatch <dispatch_id>`。開了獨立 worktree 時，照各 skill 的收尾腳本清理 worktree 與已合併分支。

完成條件：worker 已釋放（或依要求保留），該清的 worktree 已移除，ledger 有 `taskId`、`dispatchId` 與最終結果。

## Heads up（可選，僅 Claude Code worker）

Heads up 是 Claude Code 給在場者的風險提醒，不在 transcript 裡，worker 自己看不到。**僅在該 worker 的 agent 是 `claude` 時檢查**；Antigravity、Codex 等其他 agent 跳過本節。

不另外輪詢，改在**每次被叫醒處理該 worker 訊息時**（以及收到 `worker_done` 驗收前）跑一次：

```text
python3 <O>/scripts/headsup.py --worktree <worktree 路徑>
```

（已知 session id 或 jsonl 路徑時也可直接傳入。）exit 1 代表沒有掛著的 Heads up，直接繼續；exit 0 則依序處理每一則：

1. **記**：把印出的全文（含 `shown=` 與 `text:` 後段）記進 ledger。若 `text:` 是空的或指令 exit 2（狀態檔讀不到），視需要照 [TUI.md](TUI.md)〈Heads up〉確認畫面。
2. **收**：照 [TUI.md](TUI.md)〈Heads up〉在終端空閒時送 `0` 收起，確認 `headsup.py --summary --worktree <worktree 路徑>` exit 1。
3. **分兩級**：
   - **馬上處理**：涉及刪檔或丟掉改動、破壞性 git、push 或對外寫入、金鑰或個人資料外洩、改隱私或安全約定、超出任務範圍。
   - **其他**：等 worker 停下或回報 `worker_done` 時一併處理。中途的 Heads up 若停下時已經自己改掉，在 ledger 註明「已不適用」。
4. **查證**：對任務來源、文件或程式碼查證一次（各 skill 另有規定的照它）。屬實又該修的，用 `orca orchestration send --to dispatch:<dispatch_id> --subject "Heads up" --body "<內容>"` 把完整原文轉給同一個 worker（開頭註明「以下是 Claude Code 給在場者的 Heads up 原文」，你的查證與修法另起一段）。不屬實或不修的，寫進 ledger 的「待使用者看」並附理由。

完成條件（僅 Claude Code worker）：`headsup.py --summary --worktree <worktree 路徑>` exit 1（exit 2 時畫面已無 `✦ Heads up`）；每一則在 ledger 有原文和處置（已轉給 worker、已不適用，或待使用者看）。

## 規則

- 一律透過 `orca orchestration`（`send`、`reply`、`worker-release`、`worker-stop`）操作自己啟動的 worker；使用者手動關掉的不重開。
- 讓 `worker-start` 建立並託管 worker 的 worktree，不要自行 `git worktree add` 給 worker 用（協調者自己做離線驗證的臨時 detached worktree 除外）。
- worker 只在自己的分支 commit，push 和合併由你照各 skill 做。
- merge 之前、你自己在主目錄 commit 之前，跑 `bash <O>/scripts/preflight.sh <repo> <主分支>`；`git add` 只點名自己的檔。
- push 照〈授權〉。有 CI：在背景執行 `bash <O>/scripts/push-ci.sh <repo> <workflow 檔名> <分支>`，印 `ci=success` 才算完成；其他結果照各 skill 處理，各 skill 沒寫的就把失敗的 job 回報使用者。沒有 CI：`git push origin <分支>`。
- 使用者要的是 X 就只做 X；順手想清的東西（刪目錄、刪分支、改設定）另外問。

## 回報

要使用者決定的事放在最前面，一題一行、附你的建議，獨立成一則短訊息，不夾在長報告裡。

給使用者的路徑從根目錄寫起：worktree 和 run 目錄裡的檔，相對路徑會被對到他的主目錄去。
