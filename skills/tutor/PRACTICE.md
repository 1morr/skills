# 練習頁、模擬卷、批改、帶著做

tutor 做材料的分支：導讀頁照 GUIDE.md 做好之後做這兩樣。讀者在練習頁上自己做題，再用模擬卷照考試的樣子驗收；批改和學習紀錄在 COACH.md。`<S>` 的定義在 SKILL.md。

## 練習頁

每份導讀頁配一份練習頁 `topicN-practice.html`，放在導讀頁旁邊。每題完整題目下面有一張畫布：可以手寫、打字、擦掉、復原，自動存在瀏覽器裡。讀者拿得到的回饋有三種：

- **填答格**（`.fill`）：填一個值按「對答案」，頁面馬上說對不對。基本功錯兩次就公布答案和原因；整題的填答格只說對不對，不公布。做完的格子可以按「再做一次」重練，之前幾次的紀錄會留著。
- **範本答案**（`details.model`，每題完整題目一個）：讀者寫完才打開。裡面是老師格式的完整答案（`.sheet`），和一張給分點清單（`ul.rubric`，每個 `<li data-marks="2">` 一個老師會給分的點）。讀者照清單一點一點勾，頁面算出自評分數。配分照老師的評分方式：In-class Exercise 答案上的 [3%]、作業的評分指引；都沒有就每個步驟、每句結論各 1 分。結論句的給分點寫到老師會看的字，例如「寫明 at the 5% significance level」。
- **複製給 Claude**：把頁面標題、題目名稱、題目代號、填答紀錄和畫布合成一張圖放進剪貼簿，讀者貼到對話裡批改步驟。

內容照這個順序：

1. **基本功小題**（`<section class="q drill">`，至少 3 題）：每題只考一個判斷，例如用 t 還是 Z、左尾還是右尾、Z 表要找哪個面積、df 是多少、r₂ 的分子有幾對。從題型表和學習紀錄的「錯在哪一步」挑。整題做錯時看不出錯在哪一步，小題一題就看得出來。每題一個填答格，要讀者**給出東西**（一個數字、一個名稱）；是非題猜也有一半會對，改問背後那個數字。
2. **完整題目**（`<section class="q">`）：每題對照導讀頁的一題例題或作業，換情境和數字。`data-type` 寫它練的是題型表的哪幾列（代號用空白分開）。題型表的每一列至少要有 2 題變式，老師原題不算。`data-differs` 寫這題和對照題哪裡不一樣，例如結論相反（例題拒絕、這題不拒絕）、信賴水準不同、多一個例題沒有的陷阱。照抄例題步驟的人會在這裡錯。這段只給出題的人看，不會出現在頁面上。最後的數字（檢定統計量、臨界值）可以各放一個填答格，讀者先知道對不對。
3. **老師原題重做**（有的話）：作業和 In-Class Exercise 的原題，也是完整題目，`data-differs` 寫「老師原題」。答案是導讀頁裡的老師答案；還沒交的作業是答案紙。

題目長得像考試，不像作業：

- 題型的比例照測驗的形式（SKILL.md〈找材料〉第 7 步）。考試不能用軟體時，讀圖和讀輸出的題目要佔多數。
- 題型表上寫了 `data-reads="figure"` 的題型，題目裡要有圖或軟體輸出：`gen.py` 畫出時間序列圖、ACF 圖這類圖（`<figure data-tr="none">`），輸出表排成老師材料的樣式（`<pre class="mtb">`，欄名和小數位照老師的）。只用文字描述圖（「r₁ = 0.93、慢慢下降」）不算。
- 手算題的資料量要在考場做得完：照老師例題的大小（例如 8 到 10 期、一位或兩位數）。課本題的資料太多時，改成給出中間的加總，只留關鍵的幾步手算。

完整題目的來源，依序找課本章末題、In-class Exercise、過去的測驗；用過的跳過。都沒有就自己出：形式照該科的測驗，沒有測驗樣本就照作業（同樣的題型、資料給法、小題結構、答題句型）；需要軟體輸出時，用腳本算出輸出表的數字，排成老師材料的樣式。

```html
<body data-title="STAT101 Topic 4 練習" data-key="stat101-topic4"
      data-guide="topic4-guide.html" data-answers="practice/topic4/answers.md">
<aside class="panel" data-label="查表">   右下角按鈕打開：統計表、要對照的課件截圖
  <figure data-tab="Z 表"><img src="assets/z.png" data-zh="assets/z.zh.png"><figcaption>Statistical Tables p.1</figcaption></figure>
</aside>
<section class="q drill" data-id="df-one-sample"><h2>基本功 1</h2>
  <p>樣本有 10 筆，σ 未知。df 是多少？</p>
  <p class="fill" data-answer="9" data-why="df = n − 1 = 10 − 1。">df =</p>
</section>
<section class="q" data-id="acf-seasonal" data-type="acf-read plot-describe" data-differs="有季節性沒有趨勢，Eg 1 有趨勢" data-h="1300">
  <h2>練習 1</h2>
  <p class="ref">對照 Eg 1、Assignment 4 第 1 題（導讀頁 §16、§20）</p>
  <div class="en">英文題目，寫法照測驗</div><div class="zh">中文翻譯</div>
  <figure data-tr="none"><img src="assets/p1-acf.png"><figcaption>gen.py 畫的 ACF，樣式照 Minitab</figcaption></figure>
  <p class="fill" data-answer="0.62" data-tol="0.005">(b) r<sub>4</sub> =</p>
  <details class="model">
    <div class="sheet">老師格式的完整答案，數字用 {{佔位}}</div>
    <ul class="rubric"><li data-marks="2">指出 r4、r8 超出紅線</li><li data-marks="1">結論：有季節性</li></ul>
  </details>
</section>
</body>
```

- `<body>` 和填答格的 `data-*` 怎麼寫、怎麼比對答案，在 `<S>/practice.py` 開頭。基本功的 `data-why` 必填。
- `data-id` 寫成說明內容的英文小寫代號（例如 `ci-sigma-known`）。它是存檔的鍵，也是答案檔裡找這題的名字。練習頁發出去之後**不要改代號**，改了讀者的筆跡會不見；加題就用新代號。
- 畫布只加在完整題目，預設高度 900，排在範本答案前面；題目長的在 section 寫 `data-h`。基本功只填一格、沒有畫布，要打草稿的那一題才寫 `data-h`。
- 數字由腳本產生（`gen.py`）：算好每個值、用 assert 判定結論，寫成 `values.json`；題目原始檔和答案檔用同一組 `{{佔位}}`，各用 `fill.py` 填一次（用法見 GUIDE.md〈答案紙〉），再組頁。
- 答案檔照老師的答題格式寫每一小題的完整做法（比範本答案多了每一步的中間數字和常見錯法），每題的標題寫題目代號。它留著批改用，不給讀者。

組頁：

```bash
python <S>/practice.py practice-src.html -o topicN-practice.html
```

practice.py 會替每題完整題目加畫布、替範本答案加上摺疊的摘要、產生題目導覽和「複製填答結果」按鈕，把 `.ref` 裡的 §N 連到導讀頁那一段（開新分頁，練習頁上寫到一半的不會跑掉），並內嵌圖片和程式。它檢查本節的結構規則，並和導讀頁一樣量水平溢出，任何一條不過就不產出，並逐條印出原因；照訊息改到通過。

完成條件：`practice.py` 通過。用瀏覽器自動化工具打開練習頁，下面每一項都試過：填答格答對、答錯兩次、再做一次各試一次；範本答案打開、勾給分點、分數會變；每張題目圖看得清楚軸和數字；題目導覽鈕會跟著對錯變色；手寫、打字、點字修改、復原；重新整理後筆跡和填答還在；「複製給 Claude」拿到的圖有題目代號；§ 連結打開導讀頁的那一段；查表面板能切換分頁和中英文。

## 模擬卷

練習頁是一個題型一個題型練、可以看導讀頁；模擬卷是照考試驗收：題型混在一起、計時、沒有提示。每份導讀頁配一份 `topicN-mock.html`；課程教過兩個以上的 topic 之後，每次再出一份跨 topic 的累積卷 `mock-topic1-N.html`，考前再出一份涵蓋全部範圍的。

和練習頁同一種原始檔、同一支 `practice.py`，差別寫在 `<body>`：

```html
<body data-mode="mock" data-minutes="45" data-title="STAT101 Topic 4 模擬卷" data-key="stat101-topic4-mock"
      data-guide="topic4-guide.html" data-answers="mock/topic4/answers.md">
<section class="q" data-id="mock-acf-monthly" data-type="acf-read">…題目、圖、填答格、details.model…</section>
</body>
```

- 只放完整題目，沒有基本功、沒有 `.ref`、不用 `data-differs`。每題一樣要有 `data-type` 和 `details.model`。
- 題目是練習頁沒出過的：換資料、換情境、換結論的方向。順序打亂，同一個題型不連著出。
- 題數、每題小題數、配分照測驗的形式；`data-minutes` 照老師的考試時間按題數比例抓。給分點的總分就是這份卷子的滿分。
- 單一 topic 的卷子，題型表的每一列至少一題。累積卷的 `data-guide` 用 `;` 列出涵蓋的導讀頁，從學習紀錄上狀態不是「會做」和最久沒複習的題型先挑。
- 讀者按「開始計時」才看得到題目，按「交卷」才對填答格、才出現範本答案。他照給分點自評後貼回填答結果。

完成條件：`practice.py` 通過。用瀏覽器自動化工具打開，下面每一項都看到了：開始前看不到題目；作答時填答格不顯示對錯；交卷後填答格對完、範本答案出現、重新整理後還是交卷的狀態。
