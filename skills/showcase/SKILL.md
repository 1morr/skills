---
name: showcase
description: Show a code change to someone who did not write it, so they can see what an agent changed without asking it or running the code themselves. Runs the code before and after the change, captures evidence (screenshots, screen recordings, command output, test results), and renders a self-contained HTML report, plus text-only Markdown for a PR, explaining what changed, why, and which decisions were made, with annotated key diffs. Use when asked to showcase, demo, walk through, or explain a change, branch, commit range, or PR, to compare before and after, or after finishing a feature. Also triggers on 展示改動、前後對照.
argument-hint: "[commit | range | PR# | branch] [no-run] [post] [auto]"
---

# Showcase

Showcase 替沒寫這個改動的**讀者**回答四個問題：它做了什麼、為什麼做、做了哪些決定、我怎麼親眼看到。讀者不必去問寫它的 agent，也不必自己把程式跑起來。完整 diff 在 PR 的檔案頁已經有了；showcase 補的是 diff 說不出來的部分。

產出放在 repo 外的 `<系統暫存目錄>/showcase/<repo 名>/<id>/`（使用者指定位置時用使用者的）。`<id>` 是 `pr-<編號>`（範圍正好是整個 PR 時），否則 head 的短 SHA，否則 `wip`。目錄已存在時不碰它，改用 `<id>-2`、`<id>-3`…… 的新目錄：裡面可能是別人或上一次的報告。

- `showcase.html`：單一檔案，截圖與錄影全部內嵌。拖進 PR 的留言框就能附上（GitHub 接受 `.html`，上限 25 MB；`gh` 不能上傳它）。
- `pr.md`：只在要貼到 PR 時產出。內容與 HTML 相同，但沒有圖片與錄影，單獨貼出來也讀得懂。

報告語言：使用者指定的，或使用者長期指示裡設定的；都沒有就跟 repo 的 PR 描述，再來是 repo 文件。`lang` 設 `zh-Hant` 或 `en` 會有對應標籤，其他值用英文標籤。

## 叫用方式

使用者可以用參數，也可以用口語說。沒說的照預設做，不問。

- 範圍：commit、範圍、PR 編號或分支。省略時見第 1 步。
- `no-run`（「不實跑」）：什麼都不跑。證據停在 `tests` 或 `static`，`why_not_higher` 寫「使用者選擇不實跑」。
- `post`（「貼留言」）：最後把 `pr.md` 貼成 PR 留言（第 7 步）。「PR」、「PR #12」這類字只代表範圍，不代表要貼。
- `auto`（「不要問我」）：全程不提問、不幫使用者打開報告、不提議改 repo 的檔案。需要使用者決定的事一律選不動手的那邊，並列進 `unverified`。擷取照常做：用無頭瀏覽器、模擬器截圖與錄影不需要使用者決定，證據要和預設模式一樣完整。被其他流程呼叫，或沒有使用者在場時（CI、排程、hook），也照這樣做。

預設是：能跑就實跑，證據擷取完馬上收掉。

## 1. 確認要展示什麼

範圍沒指定時，依序看這些候選：

1. 這個 session 做的改動：從 session 開始時的 HEAD 到現在，含未 commit 的工作。
2. 未 commit 的工作。
3. 目前分支相對預設分支的改動。
4. 目前分支的 PR。

只有一個合理候選、或在 `auto` 下時，取第一個存在的，說一句你用哪個，然後直接開始。候選不只一個時，一次問完。

改動沒有使用者操作得到的東西時（重構、文件、純內部邏輯），不會有畫面可截；照證據階梯，用測試或輸出當證據。

## 2. 釘住範圍

- 使用者指定的 commit 或範圍：照用。單一 commit 是 `<commit>^` 到 `<commit>`；`^` 是第一個 parent，merge 也一樣。
- PR：用 `gh pr view <編號> --json baseRefName,headRefOid` 取 base 分支與 head commit；`base` 是兩者的 merge-base。
- 這個 session 的改動：`base` 是 session 開始時的 HEAD，`head` 是 `null`（工作區）。
- 分支或手上的工作：`base` 是 `git merge-base HEAD origin/<預設分支>`（沒有 remote 時用本地的預設分支）；`head` 是 `HEAD`，未 commit 的工作則為 `null`。

完成條件：`git diff --stat <base> [<head>]` 列出的正好是要展示的改動。範圍混進無關的 commit 時，問使用者要展示哪部分；`auto` 下照原範圍做，並在 `unverified` 註明。

## 3. 收集「為什麼」

讀每一個可能說明意圖的來源：產生這次改動的對話、PR 描述、commit message、分支名、PR 引用的 issue / 票 / 規格、改動碰到或引用的 ADR 與設計文件。記下用了哪些來源。票或文件涵蓋的範圍比這次改動大時，它只用來解釋為什麼；報告仍只描述這個範圍。

有來源支持的說法是**有來源**；從程式碼反推的是**推斷**，要標出來。沒有任何來源說明動機時，`why.sources` 留空，報告會顯示「待作者補充」。讀者會依「為什麼」行事，看得見的空白比看似合理的猜測對他們更有用。

完成條件：「為什麼」與每個決策裡的每一句，不是附了來源，就是標了推斷。

## 4. 收集證據

按讀者能觀察到什麼來分類改動。一個改動可以同時屬於多類；讀者最想看的主要效果拿最強的證據，次要效果可以停在較低等級，或列進 `unverified`。

| 類型 | 證據 |
|---|---|
| 看得見的 UI | 每個受影響的畫面與狀態，base 與 head 各截一張 |
| 要操作才看得出的 UI（動畫、轉場、多步流程、拖放、載入狀態） | base 與 head 用同一套操作各錄一段 |
| 行為（CLI、API、函式庫輸出、資料處理） | 同一份輸入分別跑 base 與 head，輸出並排 |
| 效能 | 同一個 benchmark 跑 base 與 head |
| 附測試的修正或新邏輯 | 新增或改動的測試在 base 跑（失敗）、在 head 跑（通過） |
| 沒附測試的修正 | 自己寫一支重現，在 base 失敗、在 head 通過，原始碼放進報告 |
| 意在保持行為的重構 | 兩邊各自的測試都綠、公開介面沒變 |
| 只有文件、設定或依賴 | 敘述與 diff 本身就是證據 |

照改動需要，在**證據階梯**上爬得越高越好：

1. `before-after`：base 與 head 用同樣方式跑過（同樣的畫面、輸入、指令或測試檔）。測試在 base 失敗或編譯不過、在 head 通過，也算。
2. `after`：只跑了 head。
3. `tests`：一邊的測試或指令輸出。
4. `static`：什麼都沒跑。

低於 `before-after` 時，`why_not_higher` 寫出具體障礙，例如「這個畫面需要登入真實帳號」。讀者靠這一行判斷整份報告可以信到什麼程度。

動手跑任何東西之前，先讀 [references/running.md](references/running.md)。它涵蓋：跑法從哪來、獨立 checkout、證明每一邊跑的是自己的程式碼、擷取與錄影、收尾。

輸入用假資料。只有改動本身就是關於真實帳號或外部服務時才碰它們，而且要先問；`auto` 下不碰，列進 `unverified`。

每項證據的 caption 寫兩件事：情境，以及**看到的差異**。例如「從第 40 筆返回：修改前回到頂端，修改後停在第 40 筆」。只讀 `pr.md` 的讀者看不到圖，靠 caption 知道差在哪。

證據是**原文**：程式印出或顯示的東西，用它自己的字詞與語言。

- 可以刪到只剩相關的行，每處刪減標 `…`。
- 可以遮蔽：把 token、cookie、金鑰、個人姓名或 email、帳號資料、家目錄路徑換成 `<redacted>`、`<home>` 這類佔位符，其他一字不動。
- 留下的每一行都是程式印出的原樣；你的摘要與計數寫在 caption，不混進輸出。

附上的報告在公開 repo 上就是公開的。

repo 的驗證規矩要求的平台或流程超出這次範圍時，照這次的範圍做，其餘列進 `unverified`，並註明 repo 規矩原本要求。

證據檔存在報告目錄，用相對路徑引用。

完成條件：改動所屬的每一類都有證據，或 `why_not_higher` 點名了它；running.md 的出處確認成立。

## 5. 寫敘述

寫給沒打開過程式碼的讀者。

- `summary`：1 到 3 句，使用這個軟體的人會感受到什麼改變。寫效果，不寫實作。
- `how`：用白話說做法，點出主要的組成部分。
- `decisions`：審查者可能質疑的每個選擇：為什麼、考慮過哪些替代方案、有來源還是推斷。
- `files`：每個改動的檔案一則說明。用 glob 當鍵可以讓一組檔案共用一則，例如產生的程式碼、lockfile、機械式改名。
- `hunks`：撐起這次改動的少數幾段 diff，每段說明它做什麼、為什麼。用 `match` 縮到關鍵的那幾行，很長的新檔也一樣；每段 hunk 只給一個條目。
- `try_it`：審查者從乾淨的 checkout 出發、用假資料親眼看到改動的步驟。
- `unverified`：沒驗證到的，例如平台、流程、邊界情況。

完成條件：讀者只看 summary、「為什麼」與 `try_it`，就答得出「改了什麼、為什麼、我怎麼看到」。

## 6. 渲染並檢查

在報告目錄寫 `report.json`，格式見 [references/report-schema.md](references/report-schema.md)，然後在 repo 根目錄用 Python 3.9 以上執行：

```
python <本 skill 的目錄>/scripts/showcase.py <報告目錄>/report.json [--pr-md]
```

要貼到 PR 時加 `--pr-md`，會另外寫出 `pr.md`。

渲染器自己從 git 讀每段 diff，並對照 repo 檢查報告。修報告直到它以 0 結束，並處理每個警告。

接著逐張打開證據截圖檢查：縮到報告的顯示寬度（約 1000px，並排時每張約 500px）時，差異仍看得清楚。錄影要檢查兩件事：

- 長度與檔案大小合理。
- 開頭停在操作前、結尾停在結果上。能抽影格就抽頭尾各一張看，例如用 `ffmpeg`。

完成條件：每項證據在報告寬度下看得出它的差異。沒辦法檢查的，在交接時說明。

## 7. 交接

不是 `auto` 時，用預設瀏覽器打開 `showcase.html`（Windows `start`、macOS `open`、Linux `xdg-open`）。給使用者它的路徑，再加三行：

- 達到的證據等級
- 沒驗證到的
- 待作者補充的

**貼到 PR**（有 `post` 時）：

- 用 `gh pr comment <編號> --body-file pr.md` 貼成留言。
- 不要用 `gh pr edit --body-file`：它會整份蓋掉作者寫的 PR 描述。使用者要求放進描述時，把 `pr.md` 接在原描述後面。
- 範圍沒有對應的 PR 時不開新 PR，在交接時說明。
- 想在 PR 上看到截圖與錄影的讀者，需要使用者在網頁上把 `showcase.html` 拖進留言框；交接時提一句。

**記下跑法**（不是 `auto`，且 repo 的指令檔不夠用時）：這次自己找出、或問使用者得來的跑法，包括指令、陷阱、出處確認方式，下次叫用就不必重找。把打算寫的文字給使用者看，問一次能不能寫進 repo 的 `AGENTS.md`（repo 只有 `CLAUDE.md` 時寫那裡），照該 repo 改指令檔的規矩寫。同意才寫。
