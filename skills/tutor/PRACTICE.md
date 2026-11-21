# 練習頁與模擬卷

tutor 做材料的分支：讀者在練習頁上自己做題，模擬卷印出來照考試做；批改在 [COACH.md](COACH.md)，學習紀錄和筆記的格式在 [RECORDS.md](RECORDS.md)。腳本位在同目錄的 `scripts/`。

兩種頁用同一種原始檔、同一支 `scripts/practice.py`。**等導讀頁的題型表 `table.types`、`§` 結構與統一符號鎖定後才動筆出題**（[SKILL.md](SKILL.md)〈分階段平行開工〉），確保提示、逐步詳解與導讀頁使用完全相同的符號、直覺講法和 `§N` 座標；導讀頁組出 `.html` 後跑 `scripts/practice.py` 組頁。

## 出什麼題

**題目長得像這場考試**：考試是 10 分鐘配對，這一頁就是幾組配對；考試是三大題計算、申論或手寫追蹤程式碼，就照那個形式出；混著考就混著出。出幾題、怎麼排、要不要提示，照這場考試的考法、各部分的份量，和讀者做錯過什麼（學習紀錄、筆記的「錯過」）來定。

依課程題型設計檢核與作答方式：

- **量化計算與讀輸出題**：由 `gen.py` 算出每個數並用 `assert` 驗證大小關係與結論，寫入 `values.json` 經 `scripts/fill.py` 填入題目與答案檔；關鍵數值設 `.fill` 填答格（配 `data-tol`），程式或統計軟體輸出放 `<pre class="output">`（向下相容 `pre.mtb`），需要畫圖或列算式的整題配畫布（讀者可在畫布打字或打開流式「文字步驟」框）。
- **文史社科申論與個案分析題**：概念辨識與史料配對用 `.fill` 小題；申論題寫成整題 `<section class="q">`，可在題目內放選配 `<textarea class="work" placeholder="在這裡擬論點大綱與段落…"></textarea>` 讓讀者流暢打字擬答，並在 `<details class="model">` 附上 `.sheet` 範本段落與 `<ul class="rubric">` 具體給分點（如「點出核心論點［2 分］」「引述具體史實／條文佐證［3 分］」「回應反方或制度限制［2 分］」）。
- **程式實作與演算法題**：追蹤輸出、迴圈不變量、時間／空間複雜度用 `.fill` 填答格（如 `data-answer="O(n log n)|n log n"`），終端機或測試輸出放 `<pre class="output">`；手寫演算法或邊界條件推導放在整題（配 `<textarea class="work">` 或畫布），在 `.rubric` 列出正確性、邊界條件與複雜度給分點。

共通原則：

- 導讀頁已經解了老師的每一題，所以這裡的題目是讀者沒看過答案的：換資料、換情境、換問法，改在會改變答案或判斷走向的地方（特別針對 `table.types` 裡的易混淆線索出題）。老師的原題要原樣重做時，答案用老師的。
- 課本章末題、In-class Exercise、過去的測驗出過哪幾題記在學習紀錄〈練習題來源〉，同一題原題只出一次；自己出的題記答案檔在哪。
- 答案檔照老師的答題格式寫每一題的完整做法和常見錯法，每題標題寫題目代號（`data-id`）。它留著批改用，不放進頁面。

## 練習頁

每份導讀頁配一份 `<名稱>-practice.html`，放在導讀頁旁邊。題目有兩種：

- **小題**（`<section class="q drill">`）：沒有畫布，只有填答格：一格，或一組。每一格填了馬上知道對錯，錯兩次公布答案和原因。
- **整題**（`<section class="q">`）：下面有畫布（支援手寫、畫布標註打字，以及工具列內建或題目自帶的流式 `<textarea class="work">` 文字步驟框），全部自動存在瀏覽器裡，並支援「匯出進度／匯入進度」JSON；裡面的填答格只說對不對，讀者按頂部「複製填答結果」時會自動按 `y` 排序匯出算式與文字步驟供批改診斷錯因。

題目裡放什麼照這場考試定，用得到才放。下面的範例示範了填答格、對照的 §、程式／軟體輸出、提示、範本答案和給分點；其餘屬性與比對規則寫在 `scripts/practice.py` 開頭：

- `data-answer="0.62|0.620"`：用 `|` 列出可接受的寫法（原文和譯名、全名和簡稱）。每一格各對各的答案，「兩格順序不拘」的問法拆開問。
- `<details class="steps">`：提示全部看完才出現的逐步詳解。
- `<pre class="output">`：排成等寬區塊的程式執行輸出或統計軟體報表（向下相容 `pre.mtb`）。
- `<textarea class="work">`：選配的流式文字作答框（長篇申論、程式碼或長推導可直接放在題幹下方；沒放時讀者也能在畫布工具列按「文字步驟」打開）。

整題至少要有範本答案或填答格其中一樣，讀者才對得了答案。

```html
<body data-title="STAT101 Topic 4 練習" data-key="stat101-topic4"
      data-guide="topic4-guide.html" data-answers="practice/topic4/answers.md">
<aside class="panel" data-label="查表"><!-- 右下角按鈕打開：統計表、語法速查表 -->
  <figure data-tab="Z 表"><img src="assets/z.png"><figcaption>Statistical Tables p.1</figcaption></figure>
</aside>
<section class="q drill" data-id="df-one-sample"><h2>小題 1</h2>
  <p>樣本有 10 筆，σ 未知。df 是多少？</p>
  <p class="fill" data-answer="9" data-why="df = n − 1 = 10 − 1。">df =</p>
</section>
<section class="q" data-id="acf-seasonal" data-type="acf-read plot-describe" data-h="1300">
  <h2>練習 1</h2>
  <p class="ref">對照 Eg 1（導讀頁 §16）</p>
  <div class="en">原文題目，寫法照測驗</div><div class="zh">翻譯</div>
  <pre class="output">Lag   ACF      T
  4  0.62   3.10</pre>
  <p class="fill" data-answer="0.62" data-tol="0.005">(b) r<sub>4</sub> =</p>
  <ol class="hints"><li>這是讀 ACF 的題型，做法在導讀頁 §16。</li><li>先找超出臨界值的是哪幾期，再看間隔。</li></ol>
  <details class="model">
    <div class="sheet">老師格式的完整答案，數字用 {{佔位}}</div>
    <ul class="rubric"><li data-marks="2">指出 r4、r8 顯著</li><li data-marks="1">結論：有季節性</li></ul>
  </details>
</section>
</body>
```

- 每題要有 `<h2>` 標題和 `data-id`：說明內容的英文小寫代號（`ci-sigma-known`）。它是存檔的鍵，也是答案檔裡找這題的名字；練習頁發出去之後維持原樣，加題用新代號，讀者的筆跡才留得住。
- 導讀頁有題型表時（[GUIDE.md](GUIDE.md)〈速查卡和題型表〉），整題的 `data-type` 寫它練的是哪幾列（代號用空白分開）。
- `data-h` 是畫布的高度，預設不夠寫的題才寫。

```bash
python <tutor目錄>/scripts/practice.py practice-src.html -o topicN-practice.html
```

畫布、按鈕、摺疊摘要、題目導覽、「複製填答結果」、「匯出／匯入進度」、頁面頂端用法說明、§ 連結（自動排除 `<code>`/`<pre>` 與註解）由 `practice.py` 加上。會讓頁面壞掉或題目對不回導讀頁、答案檔的事它不產出，逐條印出原因；照訊息改到通過。

完成條件：`scripts/practice.py` 通過。用瀏覽器自動化工具打開練習頁檢查：挑幾個填答格填進答案檔的答案確認判對；每張題目圖與 `<pre class="output">` 清楚不溢出；有提示的題按到底確認提示不直接洩漏答案，且逐步詳解數字與填答格一致。

## 模擬卷

模擬卷照考試驗收：用筆做（印在 A4 紙上，或在平板上寫在考卷 PDF 上），題數、小題數、配分、作答時間照測驗的形式。有過去的考卷時逐題仿：每一題原題對一題，題型、小題數、配分照它，換資料和情境。課程教過兩個以上的範圍之後，可以出一份跨範圍的累積卷，`data-guide` 列出涵蓋的每份導讀頁。

和練習頁的差別是 `<body data-mode="mock">`（寫法在 `scripts/practice.py` 開頭）。它組好頁面後印兩份 PDF 放在旁邊：考卷（封面、題目、作答頁、卷末的表）和答案。

- 題目都寫成整題，標題寫題號和配分（「第 1 題（14 分）」）；`data-minutes` 是印在封面的建議時間。考卷上只有題目：提示、逐步詳解、`.ref` 是練習頁的東西。
- 要寫步驟的題，每題從新的一頁開始，後面接一張整頁的作答頁。答案直接寫在題目上的題（配對、填空、選擇）在 section 寫 `data-space="none"`：接著上一題排、後面沒有作答頁。
- 查表面板的東西印在卷末，只放考場會發的表。
- 讀者在紙上做完，回頁面按「我在紙上做完了」才對填答格、才出現範本答案。

完成條件：`scripts/practice.py` 通過，兩份 PDF 都印出來了。兩份各打開看一次：樣子像這場考試；每張題目圖和 `<pre class="output">` 看得清楚、沒有被換頁切斷；卷末的表都在；考卷上只有題目。
