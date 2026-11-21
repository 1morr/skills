# {{PROJECT}}

{{ONE_LINE}}文件是唯一的記憶，對話不是。

## 文件與指標

- `docs/design-brief.md`：產品需求與拍板決策（衝突時以它為準）。
- `ARCHITECTURE.md`：模組邊界、依賴方向、跨模組契約與測試策略；架構取捨存 `docs/adr/`，命名依 `GLOSSARY.md`。
- `docs/roadmap.md`、`docs/progress.md`、`docs/decisions.md`：里程碑佇列、階段進度與非做票期決策紀錄。
- `docs/development.md`：環境建置、〈全部檢查〉閘門與驗證原則的單一來源。
- 任務與跑票：若採用 `.scratch/<里程碑>/issues/` 本機票，規劃、結尾交接、撞號與封存見 `docs/agents/milestone.md`，票面欄位語法見 `docs/agents/ticket-template.md`（見 `docs/agents/issue-tracker.md`）；狀態檢查、下一步、封存與總覽頁跑 `1morr-skel check|next|notes|dashboard`。若用 GitHub Issues / Linear 等外部 tracker，則以該 tracker 為任務單一來源。

## 使用者確認與決策標記

- 修改 `docs/design-brief.md`、`ARCHITECTURE.md`、ADR 或推翻既有決策前，先給草稿或選項請使用者確認；同意後同一個 commit 更新文件並記一條決定。
- 向使用者提問（對話中或票面 `等使用者：`）依序寫明：背景一句、選項、建議、不決定會卡住什麼。使用者回「照建議」僅涵蓋當則列出的題目。
- 每個選擇記一行並標決定者：`（使用者定）`、`（使用者同意）`、`（Agent 定）`（Agent 自行取捨或協調者代答皆標 `Agent 定`，里程碑驗收時攤出追認）。

## 事實與查證

- 外部服務、框架與套件行為只信官方文件與 `docs/research/` 已查證事實（附編號與來源）。
- 現況以指令與原始碼為準（`git log`、`git status`、實跑輸出），查證程式碼現況必附 `檔案:行`。
- 發現設計文件／ADR 與程式碼不符時，單獨列出「文件與程式對不上」詢問使用者修哪邊，不自行挑一邊當真。

## 任務執行與完成標準

- 一個 session 在獨立分支專注完成一張票（例如 `/implement <票路徑>`）：先看上下文與驗收條件，實作並補齊測試，結尾跑 code review。
- UI 改動必須實跑驗證，附上截圖或讀回的畫面文字。
- **完成標準**：驗收條件全數勾選、`docs/development.md`〈全部檢查〉與測試綠燈、票面或紀錄已更新並完成 Conventional Commits 提交（由發起者或 `/1morr:ticket-coordinator` 合併）。

<!-- 只在 repo 公開時保留這一段 -->
## 公開 repo

- commit、文件、fixture、log 與截圖不含個資（姓名、email、帳號）；憑證與 token 遮蔽為 `***`；本機路徑改寫為 `<repo>`、`<暫存目錄>`。
