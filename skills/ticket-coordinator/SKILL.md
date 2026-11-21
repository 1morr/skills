---
name: ticket-coordinator
description: 用 Orca orchestration 派發 worker 解票、代答、驗收與合併，跑完整個票佇列
disable-model-invocation: true
argument-hint: "[票來源] [agent/模型] [同時最多 N 張]"
---

你是這一批票的協調者：透過 Orca `orchestration` 為每張票在獨立 worktree 啟動 worker，代答可查證的問題、驗收成果、合併推送並清理資源。本檔與附屬 [USER.md](USER.md)、`scripts/land_ticket.py`（相對本檔路徑）完全自包含；參數取自使用者呼叫本 skill 時附帶的說明。

## 1. 解析執行檔與綁定 Run

1. 載入 `orchestration` skill（用工具載入，或直接讀它的 `SKILL.md`），選定本次 session 唯一的 Orca 執行檔（下文以 `ORCA` 代稱，每次呼叫直接帶入該路徑或 `"$ORCA"`，絕不硬編碼裸 `orca`）：
   - 已設環境變數 `ORCA_CLI_COMMAND` 時用其值（如受管 WSL session）；
   - 否則環境含 `ORCA_DEV_REPO_ROOT` 時用 `orca-dev`；
   - 否則在 Linux 非 Orca 終端環境用 `orca-ide`（避開系統螢幕閱讀器 `/usr/bin/orca`）；
   - 其餘環境用 `orca`。
2. 執行 `"$ORCA" skills get orchestration` 取得對應版本的官方指引，並跑 `"$ORCA" status --json` 確認 runtime 就緒。
3. **綁定 Run（以 Orca 執行期紀錄為唯一狀態源，不維護手抄 `ledger.md`）**：
   - 若使用者指定續接既有 Run，或 `"$ORCA" orchestration run-list --json` 顯示同批次有未結算 Run 需接手：執行 `"$ORCA" orchestration run-use --id <run_id> --json` 重綁收件匣與叫醒路由。
   - 否則建立新 Run：`"$ORCA" orchestration run-create --objective "<批次目標>" --json`，記下 `runId`。
   - 全程以 `"$ORCA" orchestration run-show --id <run_id> --json`、`task-list --run <run_id> --full --json`、`worker-list --run <run_id> --include-remote --json` 與 `inbox --terminal run:<run_id> --limit 50 --full` 為唯一執行期狀態源（上下文壓縮後直接查這四項還原進度與問答紀錄）。
   - 建立本次暫存目錄 `${XDG_STATE_HOME:-$HOME/.local/state}/1morr/runs/<repo 名>-<run_id>/` 存放 `spec-t<NN>.md`；如需留存開工靜態參數，至多寫入 `<10` 行唯讀 `run.json`（僅存 `runId`、`baseBranch`、`workflow`、`agent`、`model`、`concurrency`、`userPresent`、`pushPolicy`），不抄寫動態票況。

完成條件：`"$ORCA" status --json` 為 `ok: true`；`runId` 已建立或透過 `run-use` 綁定。

## 2. 開工盤點與授權

1. 讀專案的 `AGENTS.md` / `CLAUDE.md`（及 `docs/development.md` 等工程規範），確認：
   - **雙軌票源**：本地票檔（如 `.scratch/<milestone>/issues/*.md`）或 **GitHub Issues**（`gh issue list` / `gh issue view <N> --json number,title,body,state,labels`）；
   - **完成標準與閘門指令**：lint、typecheck、test 的完整執行指令，以及每張票必改的檔案清單（對應 `--require`，無則留空）；
   - **主分支與 CI**：主分支（`git symbolic-ref --short refs/remotes/origin/HEAD`，無 `origin` 則為當前分支）與 `.github/workflows/` 中對主分支觸發的 workflow 檔名（無則記無 CI）。
2. **排定佇列**：依參數指定順序、票號或檔名排序；逐張核對 `Blocked by`、GitHub Issue 相依關係、共用產出（API 端點、資料表、元件）與重疊修改區（同模組、同一張註冊表或資料庫 migration）。已 `done` / `CLOSED` 的票跳過。
3. **一次向使用者確認授權**（有互動提問工具就用它，否則在對話列點詢問；文件已寫明的不重問）：
   - 佇列順序與並行模式：**預設單票串行（同時 1 張）**；使用者要求多張互不相擋的票並行時，採用〈4. 驗收、合併與收尾〉的 **Batch Merge Train**；
   - 使用者在不在場（不在場時需要人類拍板的題只擱置受影響的票，見 [USER.md](USER.md)）；
   - Worker 的 `agent`（未指定則沿用協調者目前的 agent）與選填 `model`；
   - `git push`、GitHub Issue 留言／關票等對外寫入授權，以及改寫歷史前的備份偏好。
4. 執行預檢：`python3 scripts/land_ticket.py preflight --repo <repo> --base <主分支>`。每條 `WARN` 先查清是否為其他進行中的 session，不明來源的未提交改動或 commit 留給使用者處理。開工回覆一併印出 `"$ORCA" orchestration inbox --terminal run:<run_id> --full` 供使用者隨時查閱完整往來訊息。

完成條件：佇列相依與衝突已釐清；使用者已確認授權；`land_ticket.py preflight` 為 `READY`（或既有差異已獲使用者確認）；開工訊息已附上 `inbox` 查詢指令。

## 3. 派票與等待

1. **撰寫跨 Harness 自包含 `spec-t<NN>.md`**（存於本次 run 暫存目錄）：
   - **內聯任務與閘門**：寫入票號、目標與完整驗收條件（本地票寫相對 repo 根路徑；GitHub Issue 票將 `#<N>` 標題、內文與驗收條件直接內聯進 spec），並直接列出本專案的完成標準、lint / typecheck / test 閘門指令與紀錄格式——不傳遞私有外掛快取路徑或依賴斜線指令展開。
   - **提問規範**：遇到需求歧義或環境阻礙時，使用 preamble 指定的 Orca 執行檔呼叫 `orchestration ask --question "<問題>"`（**禁止加 `--wait`**），送出後**立即結束該回合**等 Orca 帶著回覆叫醒；不使用本地互動提問工具。
   - **結算規範**：只在自己的分支 commit（不 `git pull`、不 `git push`）；完成且全套閘門跑綠後，**直接依照 `worker-start` 自動注入的 orchestration preamble 回報 `worker_done`**（不手抄殘缺指令），在回報內文附上最新 commit hash、修改檔案與閘門檢查輸出摘要。
   - **對話透明化**：worker 每次送出 `ask`、收到 `reply` / `send` 或回報 `worker_done`，皆在自身對話輸出一行摘要（對象、內容摘要、相關檔案完整路徑）；協調者每次執行 `worker-start`、`reply`、`send` 或讀取訊息時亦同。
2. **啟動 Worker**（同專案本地派發**省略 `--repo`**；每張票獨立呼叫一行）：
   ```text
   "$ORCA" orchestration worker-start --run <run_id> --spec-file <spec-tNN.md> --task-title "t<NN> <slug>" --worktree new-top-level --name t<NN> --base-branch <主分支> --agent <agent> [--model <model>] --json
   ```
   （僅在刻意跨專案派發、多 repo 資料夾工作區或搭配 `--on <server>` 遠端派發時才傳 `--repo`。）若啟動失敗，依 `failedStage` 執行 `"$ORCA" skills get orchestration --reference references/recovery-and-cleanup.md` 排障，不盲目重跑。
3. **結束回合等待叫醒**：目前可開的票啟動完畢後，直接結束回合由 Orca 叫醒；不寫輪詢迴圈或背景 `check` 監看腳本（背景 `check` 會提前消費訊息導致漏叫醒）。不假設 worker 有 PTY 終端或狀態列，相容 Orca Chat-mode 與 Terminal-mode worker：讀輸出統一用 `"$ORCA" orchestration worker-read --dispatch <dispatch_id> --source auto --json`。
4. **被叫醒時的訊息分流**（若通知未附全文，執行 `"$ORCA" orchestration check --run <run_id> --json`）：
   - **`question`**：
     - 屬於推翻 brief / ADR / 既有決策等**須使用者拍板的題**：依 [USER.md](USER.md)〈等使用者拍板〉轉問或擱置。
     - 其餘可查證題：選項題優先選 `(Recommended)`，無標註時查票面、設計文件、ADR 與程式碼（附一句依據理由）回覆；文字題採用合理建議或查證後作答：
       `"$ORCA" orchestration reply --id <msg_id> --body "<答案與依據，標註 Agent 定>" --json`
   - **`escalation`**：
     - **含權限審批 `approval_id`**：僅真人可按允許；不擋路時先處理其他工作，若該權限超出任務邊界或卡住進度，附理由與替代方案拒絕讓 worker 繼續執行：
       `"$ORCA" orchestration deny --dispatch <dispatch_id> --prompt <approval_id> --reason "<拒絕原因與改走做法>" --json`
     - **無 `approval_id` 的本地互動等待**：執行 `"$ORCA" orchestration worker-show --dispatch <dispatch_id> --json` 檢查 `observation.agentWait`（代表 worker 停在僅真人可答的本地互動提示，`deny` 不適用；等待中的 worker 屬健康狀態而非失敗，依使用者在不在場通知處理或 `worker-stop` 重派）。
     - **未送 `worker_done` 即停下（`stopReason`）**：跑 `worker-read --dispatch <dispatch_id> --source auto --json` 看最後輸出，再用 `send --to dispatch:<dispatch_id>` 指引補完並回報 `worker_done`。
     - **`exited` 或 `lost`**：只憑證據行動（沉默、逾時或 `unverifiable` 都不算已退出），依序：
       1. `"$ORCA" orchestration worker-show --dispatch <dispatch_id> --json` 核實狀態；
       2. 前次失敗端仍持有可回收終端時，先 `"$ORCA" orchestration worker-release --dispatch <dispatch_id> --json`；
       3. 同一張 Task 重派：**`--retry-of` 必須搭配 `--task <task_id>`**（不可傳 `--spec` 或 `--spec-file`，否則會誤建新 Task），placement 不繼承，須重申 `--worktree` 與 `--agent`：
          `"$ORCA" orchestration worker-start --run <run_id> --task <task_id> --retry-of <dispatch_id> --worktree new-top-level --name t<NN>-r1 --base-branch <主分支> --agent <agent> [--model <model>] --json`
       4. 放棄這張票時改走 `"$ORCA" orchestration worker-stop --dispatch <dispatch_id> --json`（回 `stop_unknown` 就再看 `worker-show`，不盲目重複），確認停止後跑 `python3 scripts/land_ticket.py cleanup --repo <repo> --worktree <worktree 路徑> --dispatch <dispatch_id> --orca "$ORCA"`。

       同一條 `--retry-of` 鏈連續 3 次啟動失敗會觸發斷路器（breaker），Task 轉為失敗：立即停下回報使用者，不另開新 Task / Run 繞過；版本細節可用 `"$ORCA" skills get orchestration --reference references/recovery-and-cleanup.md` 查 Orca 內建指引。
   - **`worker_done`**：檢查 `outcome` 為 `succeeded` 才進入驗收；`failed` 則跑 `worker-read --source auto` 診斷根因，可修的透過 `send --to dispatch:<dispatch_id>` 指示修正，無法解決的依〈5. 異常與停機〉處理。
   - **後續追問或要求補做**：本地 worker（含已結算自動關閉者）統一呼叫 `"$ORCA" orchestration send --to dispatch:<dispatch_id> --subject "<主題>" --body "<指示>" --json` 喚醒續做；**注意 paired server（`--on <server>`）上已結算的 worker 不接受 `send`**，遠端補做須改用 `worker-start --on <server>` 開新派發。

完成條件：每張已派發的票皆收到 `outcome=succeeded` 的 `worker_done`，或明確標記擱置／停機原因。

## 4. 驗收、合併與收尾

`--worktree new-top-level`（與 `new-child`）啟動的 worker 預設為 `kept open`，結算後不會自動關閉終端／會話；**無論正常合入或異常放棄，收尾皆須明確執行 `worker-release`（未結算取消則先 `worker-stop`）**。

### 單票串行模式（預設）

1. **驗收證據與紀錄**：
   - 核對 worker 回報的全套 lint / typecheck / test 皆在最後一個 commit 之後跑綠；若有缺漏，用 `send --to dispatch:<dispatch_id>` 叫 worker 補跑，或在 `/tmp` 建一次性 detached worktree 實跑驗證後立即 `git worktree remove --force` 清理。
   - 本地票檔模式：確認票面 `Status: done`、驗收條件已勾齊，且 `## Comments` 已由 worker 寫入代答決定（標 `Agent 定`／`使用者定`／`使用者同意`）與變更摘要；缺漏一律用 `send` 叫 worker 在票分支補齊 commit（協調者不在主分支改票檔）。
2. **同步執行合入、推送等 CI 與清理**（所有步驟由 `scripts/land_ticket.py` 同步執行，不在背景偷跑 `push-ci`）：
   ```text
   python3 scripts/land_ticket.py land --repo <repo> --worktree <worktree 路徑> --base <主分支> [--ticket <票相對路徑>] [--require <必改檔> ...] --message "merge: ticket <NN> <slug>" [--workflow <ci.yml>] --dispatch <dispatch_id> --orca "$ORCA"
   ```
   - 印 `NOT READY:`：把原樣清單透過 `send --to dispatch:<dispatch_id>` 退回 worker 修正（改寫超長 commit 標題前依授權先建 `backup/` 分支）。
   - 印 `CONFLICT:`：`land_ticket.py` 已自動執行 `git merge --abort` 確保主目錄乾淨；將衝突檔清單透過 `send` 交給 worker，叫它在自身票分支執行 `git merge <主分支>` 解衝突、重跑全套閘門後再回報 `worker_done`。
   - `push-ci` 報 CI 紅燈：保留該 worker，將失敗 job 摘要透過 `send` 交給同一位 worker 在原分支修復，重跑 `merge` + `push-ci`（補修合併免傳已滿足的 `--require`）直到 `ci=success` / `ci=skipped`，再執行 `cleanup`。
   - 純 GitHub Issue 票：在 `land` 成功後依授權執行 `gh issue close <N> --comment "<commit 與驗收摘要>"`。

### Batch Merge Train 模式（多票並行時）

當同時執行多張互不相擋的票時，為根除背景 `push-ci` 與 `preflight` 搶鎖、主分支未經組合測試裸奔及 O(N²) 重複合併重測，採用整合列車一次合入：

1. 等待本批並行票各自在獨立 worktree 跑綠並回報 `worker_done`（`succeeded`）。
2. 先執行 `python3 scripts/land_ticket.py preflight --repo <repo> --base <主分支>` 確認主目錄乾淨，再從 `<主分支>` 建立臨時整合 worktree：
   ```text
   TRAIN_DIR=$(mktemp -d) && git -C <repo> worktree add -b train/<batch> "$TRAIN_DIR/train" <主分支>
   ```
3. 對本批每張票依序執行預檢合併進臨時整合分支：
   ```text
   python3 scripts/land_ticket.py merge --repo "$TRAIN_DIR/train" --worktree <wt_i> --base train/<batch> [--ticket <票_i>] [--require <檔> ...] --message "merge: ticket <NN> <slug>"
   ```
   任何回傳 `NOT READY` 或 `CONFLICT` 的票已被自動 `--abort` 排除在列車外，直接用 `send` 退回該票 worker 修正，其餘健康的票繼續留在 `train/<batch>`。
4. 在 `"$TRAIN_DIR/train"` 內**跑一次專案全套閘門測試**：
   - **全綠**：移除臨時 worktree（`git -C <repo> worktree remove --force "$TRAIN_DIR/train" && rm -rf "$TRAIN_DIR"`），在主目錄快轉主分支並刪臨時分支（`git -C <repo> merge --ff-only train/<batch> && git -C <repo> branch -d train/<batch>`），同步跑一次 `python3 scripts/land_ticket.py push-ci --repo <repo> --branch <主分支> [--workflow <ci.yml>]`；綠燈後逐張執行 `python3 scripts/land_ticket.py cleanup --repo <repo> --worktree <wt_i> --dispatch <id_i> --orca "$ORCA"`。
   - **紅燈**：定位造成組合失敗的票退回其 worker 修復，移除臨時 worktree 與 `train/<batch>` 分支，僅對通過的子集重建列車合入。

**偶發紅燈處置**：worker 證明「前一個主分支 commit 亦紅」的既有偶發失敗可記下放行一次；同一測試第二次失敗或變為穩定紅燈時，先建立修復票 `<NN>b-<slug>` 排在下一張之前（使用者在場則先確認），要求重現失效條件後修復，拒絕僅盲目調大 timeout。

完成條件（每張票）：主分支已合入該票 commit 且 `land_ticket.py push-ci` 回傳 `ci=success` / `ci=skipped` / `remote=none`；worker 已 `worker-release`；`git worktree list` 已無該票 worktree。

## 5. 使用者互動、異常停機與總表回報

- **使用者插話或需要使用者拍板**：讀取並照 [USER.md](USER.md) 執行，處理完回到等待迴圈。
- **協調者主目錄本地 commit**：僅限新增修復票或依 [USER.md](USER.md) 在主分支狀態檔（如 `docs/progress.md`）登記待決事項。每次 commit 前必跑 `python3 scripts/land_ticket.py preflight --repo <repo> --base <主分支>`，`git add` 明確點名檔案，**絕不在主分支修改正在跑的票檔**。
- **真的卡住（全佇列暫停）**：僅在 ① 需使用者本人憑證／2FA／付款、② 涉及未授權外部 repo 或第三方公開操作、③ 同一技術阻礙經根因診斷仍無法解決或觸發 `worker-start` 三次失敗斷路器、④ 主分支既有 CI 壞死無法推進時，才暫停整個佇列。異常取消放棄某張未結算票時，先執行 `"$ORCA" orchestration worker-stop --dispatch <dispatch_id> --json` 確認停止後再清理；等待使用者接手排障時保留現場，並依 [USER.md](USER.md)〈隊列停下時〉記錄狀態與續跑指令。
- **回報格式**：
  - 需要使用者決定的題目永遠放在訊息最頂端，一題一段（背景、選項、建議與影響票號）；所有檔案路徑一律寫絕對路徑或相對主 repo 根的明確路徑。
  - 佇列完成或暫停時輸出一張總表：票號、狀態（`done` / `blocked`）、commit hash、`dispatchId`、代答決定摘要、未處理觀察項。若專案具備進度下一步查詢指令（如 `1morr-skel next` 或 `scripts/next_step.py`），收尾實跑一次對齊後續建議。

完成條件：佇列每張票在總表中皆為 `done` 或附帶明確使用者行動項的 `blocked`，無懸空未釋放的已結算 worker。
