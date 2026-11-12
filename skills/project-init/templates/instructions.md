<!-- project-init 的範本：新專案的 AGENTS.md。替換 {{…}}，照註解刪掉不適用的段落，最後刪掉所有註解。 -->
# {{PROJECT}}

{{ONE_LINE}}文件是唯一的記憶，對話不是。

## 文件

- `docs/design-brief.md`：需求、決定、查證過的事實（〈查證過的事實〉，附來源）。決定衝突時以它為準。
- `docs/plan.md`：架構、依賴規則、測試策略；〈里程碑任務〉是路線圖，還沒開工的里程碑在這裡各有一小節，開工後縮成一行連到它的 spec。
- `docs/progress.md`：各里程碑的閱讀指引、session 紀錄、偏差與決定。每個 session 的起點與終點。
- `.scratch/<里程碑>/spec.md`：該里程碑的目標、範圍、共同規則、驗收與票序；`issues/` 是票，執行單位，狀態在票的 `Status:` 行。
- `GLOSSARY.md`、`docs/adr/`：名詞表與架構決定，由 `/grill-with-docs` 按需建立；命名一律用名詞表的詞。
- `docs/development.md`：開發指令的單一來源，〈全部檢查〉是閘門。

## 目錄

<!-- 技術棧定了之後填：一級子目錄各一列，最多 10 列。現在只有下面這幾列。 -->

| 路徑 | 內容 |
| --- | --- |
| `docs/` | brief、plan、progress、`development.md`、ADR、研究、已完成里程碑的封存 `archive/` |
| `.scratch/` | 里程碑的 spec 與票 |
| `scripts/` | 文件與 commit message 的檢查；設計實驗放 `scripts/experiments/` |
| `.githooks/` | git hook，啟用方式見 `docs/development.md` |
| `.github/` | CI，跑什麼見 `docs/development.md`〈全部檢查〉 |

## 每個 session 的流程

工作單位是**票**：`.scratch/<里程碑>/issues/NN-slug.md`，由使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票` 產生（見〈Skills〉）。一個 session 只做一張票，在自己的分支上做。

1. 讀 `docs/progress.md` 的 session 紀錄與偏差、該里程碑的 spec，再讀票；只讀票列出的 plan / brief 章節，其他按需讀。
2. `/implement <票路徑>`：tdd、定期 typecheck、結尾 `/code-review <開工時的 commit>`、commit。
3. 驗證：`docs/development.md`〈全部檢查〉加 test；貼指令輸出。
4. 實作若推翻 plan、brief 或先前的決定，同一 commit 改文件，並在 progress.md〈偏差與決定〉記一行。只在票內的取捨記到票的 `## Comments`；影響架構的另寫 ADR。
5. 票的 `Status:` 改為 `done`、勾掉驗收條件、code-review 未處理的發現記到票的 `## Comments`；progress.md 加一列 session 紀錄（做了什麼、下一步，細節留在票裡）；驗收票多一步：照 progress.md〈寫法與封存〉封存這個里程碑；commit。
6. 合併由**開這個 session 的人**做：使用者自己開的 session，做完在主分支 `git merge --no-ff <票分支>`（訊息 `merge: ticket NN <slug>`）；協調者（`/1morr:ticket-coordinator`）開的 session 只在自己的分支 commit，合併與 push 留給協調者。

完成標準：票上每個驗收條件打勾、全部檢查與 test 綠燈、progress.md 已更新、已 commit。缺一就還沒完成。

**所有 session 的結尾**（做票、訪談、寫 plan、里程碑開工都算）：告訴使用者下一步要在新 session 下的完整指令，並把同一句寫進 progress.md 那一列的「下一步」。下一張票是 `/implement <票路徑>`，里程碑做完是 `/1morr:checkpoint <剛做完的里程碑>`（回顧上一段、和使用者對齊下一段；它結束時寫 `/to-tickets docs/plan.md 拆 <下一個里程碑> 的票`）；要使用者先決定才能繼續時，寫 `等使用者：<要決定什麼>`。協調者開的 session 不知道下一張是哪張，「下一步」寫 `由協調者決定`；協調者跑完整批後把最後一列改成真正的下一步。

## 事實與查證

- 外部服務、平台框架、程式庫的行為只信兩處：brief〈查證過的事實〉，以及現查（context7、官方文件）。brief 沒寫的先查再用，查到的補進 brief 並附來源。
- 現況以指令為準：`git log`、`git status`、測試輸出。progress.md 與 repo 不符時以 repo 為準並修 progress.md。

## 上下文紀律

- 讀大檔案、查文件、跑實驗交給子代理回摘要。
- brief 或 plan 長過 500 行後，只讀任務指到的章節。
- 對話已長或一個任務碰了十幾個檔案：把進度與下一步寫進 progress.md，結束 session。

<!-- 只在 repo 公開時保留這一段 -->
## 公開 repo

commit、文件、票、fixture、log 摘錄與截圖：

- 不含個人資訊：使用者名稱、email、手機號、帳號名稱。
- cookie、token、簽名網址、API key 的值寫成 `***`。
- 本機路徑用代稱：`<資料目錄>`、`<暫存目錄>`、`<repo>`。

<!-- 只在專案有 UI 時保留這一段 -->
## UI

- **先有設計稿，再寫介面**。不論產品是網頁、原生 App 還是桌面程式，每個畫面先用 `impeccable:impeccable` 做成靜態 HTML 的設計稿，放在 `docs/design/`，使用者逐頁確認後才開做它的票。有爭議的地方給 A／B 兩個方案。只改文案、修 bug、不動版面的票不用。
- 設計稿要涵蓋的寬度、深淺色與設計系統寫在 brief；實作照定稿做，要偏離先問使用者。
- 設計稿排成一個只產出文件的階段，寫進 plan〈里程碑任務〉，在第一個有畫面的里程碑開工前完成。
- UI 改動實跑驗證，附截圖或讀回的畫面文字。

## Skills

- 需求與設計訪談：`/grill-with-docs`（邊問邊寫 `GLOSSARY.md` 與 ADR），結論寫回 brief。
- 里程碑開工：入口是使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票`。這個 session 依序做完三步，第 3 步 commit 後才算完成：
  1. 把 plan〈里程碑任務〉裡它的那一節，依最新的 brief、plan 與上一個里程碑的結果細化成 `.scratch/<里程碑>/spec.md`，plan 那一節縮成一行連結。文件不足以寫出 spec 時，問使用者並補進文件。
  2. 照 skill 提出切法，使用者同意後寫票，每張票寫明「讀：plan §x、brief §y」與驗收條件。最後一張固定是**驗收票** `NN-<里程碑>-acceptance`，被其他所有票擋：從開工的 commit 起跑里程碑 code-review、spec〈驗收〉逐條對到證據、乾淨 checkout 跑全部檢查、各票 Comments 沒處理的發現逐條歸到修掉、延後（寫進 plan）或不做，最後封存里程碑；`scripts/check_docs.py` 守它存在。
  3. 票序寫回 spec〈票序〉，progress.md 加一列 session 紀錄。
- 訪談、寫 plan 的 session 收尾在「plan 已更新」。之後的里程碑留在 plan，開工時才有 spec。
- 做票：一張票一個 session，`/implement`；整批跑票：`/1morr:ticket-coordinator`。
- 里程碑之間：`/1morr:checkpoint`；想看懂某樣東西現在怎麼運作：`/1morr:explain`。
- 新功能與修 bug：`mattpocock-skills:tdd`。設計模組邊界：`mattpocock-skills:codebase-design`。
- 用實驗回答設計問題：`mattpocock-skills:prototype`，結論寫回 brief。實驗腳本留在 `scripts/experiments/`，換版本時要重量。
- 查證外部事實：`mattpocock-skills:research`，輸出放 `docs/research/`，結論摘進 brief〈查證過的事實〉並連結。
- 每張票與里程碑收尾：`mattpocock-skills:code-review`（Spec 軸讀票，Standards 軸讀本檔）；難 bug 或效能退化：`mattpocock-skills:diagnosing-bugs`。
- 改本檔或 progress.md 的流程段：`mattpocock-skills:writing-for-agents`。

## Agent skills

### Issue tracker

Local markdown：票以檔案存在 `.scratch/<里程碑>/issues/`。See `docs/agents/issue-tracker.md`.

### Triage labels

五個預設角色標籤，字串與角色名相同。See `docs/agents/triage-labels.md`.

### Domain docs

Single-context：根目錄 `GLOSSARY.md` + `docs/adr/`。See `docs/agents/domain.md`.
