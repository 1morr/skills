# 練習頁與模擬卷

tutor 做材料的分支：讀者在練習頁上自己做題，模擬卷印出來照考試做；批改在 COACH.md，學習紀錄和筆記的格式在 RECORDS.md。`<S>` 的定義在 SKILL.md。

兩種頁用同一種原始檔、同一支 `practice.py`。原始檔、答案檔、`gen.py` 可以和導讀頁同時寫，照 `plan.md` 的測驗形式和段落順序；組頁要等導讀頁組好，它會讀組好的導讀頁來對 § 和題型。

## 出什麼題

**題目長得像這場考試**：考試是 10 分鐘配對，這一頁就是幾組配對；考試是三大題計算，就是整題計算；考試混著考，就混著出。出幾題、怎麼排、要不要提示，照這場考試的考法、各部分的份量，和讀者做錯過什麼（學習紀錄、筆記的「錯過」）來定。

- 導讀頁已經解了老師的每一題，所以這裡的題目是讀者沒看過答案的：換資料、換情境、換問法，改在會改變答案的地方。老師的原題要原樣重做時，答案用老師的。
- 課本章末題、In-class Exercise、過去的測驗出過哪幾題記在學習紀錄〈練習題來源〉，同一題原題只出一次。
- 有數字的題由腳本產生（`gen.py`）：算好每個值、用 assert 判定結論，寫成 `values.json`；題目原始檔和答案檔用同一組 `{{佔位}}`，各用 `fill.py` 填一次（GUIDE.md〈答案紙〉），再組頁。
- 答案檔照老師的答題格式寫每一題的完整做法和常見錯法，每題的標題寫題目代號。它留著批改用，不給讀者。

## 練習頁

每份導讀頁配一份 `<名稱>-practice.html`，放在導讀頁旁邊。題目有兩種：

- **小題**（`<section class="q drill">`）：一題問一件事，只有填答格，填了馬上知道對錯，錯兩次公布答案。
- **整題**（`<section class="q">`）：下面有一張畫布可以手寫、打字，自動存在瀏覽器裡。

題目裡可以放這幾樣，用得到才放：

| 寫法 | 讀者看到什麼 |
| --- | --- |
| `<p class="fill" data-answer="0.62\|0.620" data-tol="0.005" data-why="…">` | 填一個值按「對答案」，馬上知道對不對。`data-answer` 用 `\|` 列出可接受的寫法（原文和譯名、全名和簡稱）；`data-why` 是公布答案時顯示的一句原因 |
| `<p class="ref">對照 Eg 1（導讀頁 §16）</p>` | § 連到導讀頁那一段，開新分頁 |
| `<ol class="hints">` | 「看提示」一次看一個，用了幾個會回報 |
| `<details class="steps">` | 提示看完才出現的逐步詳解 |
| `<details class="model">` 裡 `.sheet` 和 `<ul class="rubric"><li data-marks="2">` | 寫完才打開的範本答案；有給分點就自己勾、算出自評分數 |
| `<figure>`、`<pre class="mtb">` | 題目的圖、排成老師樣式的軟體輸出 |
| `<div class="en">`、`<div class="zh">` | 原文題目和翻譯 |

整題至少要有範本答案或填答格其中一樣，讀者才對得了答案。

```html
<body data-title="STAT101 Topic 4 練習" data-key="stat101-topic4"
      data-guide="topic4-guide.html" data-answers="practice/topic4/answers.md">
<aside class="panel" data-label="查表">   右下角按鈕打開：統計表、要對照的課件截圖
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
  <figure><img src="assets/p1-acf.png"><figcaption>gen.py 畫的 ACF，樣式照 Minitab</figcaption></figure>
  <p class="fill" data-answer="0.62" data-tol="0.005">(b) r<sub>4</sub> =</p>
  <ol class="hints"><li>這是讀 ACF 的題型，做法在導讀頁 §16。</li><li>先找超出紅線的是哪幾根，再看它們隔幾期。</li></ol>
  <details class="model">
    <div class="sheet">老師格式的完整答案，數字用 {{佔位}}</div>
    <ul class="rubric"><li data-marks="2">指出 r4、r8 超出紅線</li><li data-marks="1">結論：有季節性</li></ul>
  </details>
</section>
</body>
```

- 每題要有 `<h2>` 標題和 `data-id`：說明內容的英文小寫代號（`ci-sigma-known`）。它是存檔的鍵，也是答案檔裡找這題的名字；練習頁發出去之後維持原樣，加題用新代號，讀者的筆跡才留得住。
- 導讀頁有題型表時（GUIDE.md〈速查卡和題型表〉），整題的 `data-type` 寫它練的是哪幾列（代號用空白分開）。
- `data-h` 是畫布的高度，預設不夠寫的題才寫。`<body>` 和填答格其餘的 `data-*`、怎麼比對答案，在 `<S>/practice.py` 開頭。

```bash
python <S>/practice.py practice-src.html -o topicN-practice.html
```

畫布、按鈕、摺疊的摘要、題目導覽、「複製填答結果」、頁面頂端的用法說明、§ 的連結由 `practice.py` 加上。會讓頁面壞掉或題目對不回導讀頁、答案檔的事它不產出，逐條印出原因；照訊息改到通過。

完成條件：`practice.py` 通過。用瀏覽器自動化工具打開練習頁看這次的內容：挑幾個填答格填進答案檔的答案，頁面判對；每張題目圖看得清楚軸和數字；有提示的題挑一題按到底，提示留著答案給讀者算，逐步詳解算出的數字和填答格的答案一樣。

## 模擬卷

模擬卷照考試驗收：用筆做（印在 A4 紙上，或在平板上寫在考卷 PDF 上），題數、小題數、配分、作答時間照測驗的形式。課程教過兩個以上的範圍之後，可以出一份跨範圍的累積卷，`data-guide` 列出涵蓋的每份導讀頁。

和練習頁的差別是 `<body data-mode="mock">`（寫法在 `practice.py` 開頭）。它組好頁面後印兩份 PDF 放在旁邊：考卷（封面、題目、作答頁、卷末的表）和答案。

- 題目都寫成整題，標題寫題號和配分（「第 1 題（14 分）」）；`data-minutes` 是印在封面的建議時間。考卷上只有題目：提示、逐步詳解、`.ref` 是練習頁的東西。
- 要寫步驟的題，每題從新的一頁開始，後面接一張整頁的作答頁。答案直接寫在題目上的題（配對、填空、選擇）在 section 寫 `data-space="none"`：接著上一題排、後面沒有作答頁，一張紙就放得下一整組配對。
- 查表面板的東西印在卷末，所以只放考場會發的：課程發的統計表，和有出處說考場會附的公式表。
- 讀者在紙上做完，回頁面按「我在紙上做完了」才對填答格、才出現範本答案。

完成條件：`practice.py` 通過，兩份 PDF 都印出來了。兩份各打開看一次：樣子像這場考試；每張題目圖和軟體輸出看得清楚、沒有被換頁切斷；沒有只剩一兩行字的頁；卷末的表都在；考卷上只有題目。
