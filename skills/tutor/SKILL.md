---
name: tutor
description: Teach a university course topic, assignment, or exam to a learner who missed every lecture and has zero background, using the teacher's own slides and answers as the only source of truth. Produces a self-contained HTML guide that first walks through the teacher's courseware page by page in its own order (each page shown whole with a full translation, then explained block by block with that block cropped in), then works the teacher's examples, then the topic's assignments, so the learner never has to open the course files; an assignment not yet handed in also gets an answer sheet in the teacher's format. Two modes - read (the guide with every answer; never asks questions; for a deadline or exam within about two days, or when the learner just wants to read it through) and learn (the same guide as a textbook, then in the chat - check understanding, work the examples together with the learner giving each answer, then practice on textbook or past problems, or new ones generated in the format of the course's quizzes and assignments, and keep a learning record). Use when asked to teach, explain, or review course material, to do an assignment while teaching how it is done, or to prepare for a quiz or exam. Also triggers on 教我、看不懂、零基礎、沒聽過課、複習、備考、作業教我.
argument-hint: "[作業 | topic | 考試] [read | learn]"
---

# Tutor

讀者沒上過課、沒有前置知識，看到符號和英文術語就卡住。目標是讓他**完全不用打開課件**：照課件順序讀完導讀頁，就懂每一頁在講什麼，也能自己答出老師的題目。

老師的材料是唯一標準：講義、例題答案、過去作業的 Suggested Answers、老師的統計表。課本是第二順位；網路和模型自己的知識只用來補前置知識、講為什麼、舉現實例子，而且符號和寫法要對齊老師。老師和課本不一致時照老師，並標出來。

## 叫用與模式

- `read`（一次讀完）：導讀頁，每題附完整做法和答案。**全程不提問、不出練習。**範圍不確定時自己選最可能的，寫在頁首「這頁假設了什麼」。適用於交件或考試在兩天內，或使用者說「趕」「明天交」「今晚要考」「不要問我」「直接給我看」。
- `learn`（帶著做）：先做同一份導讀頁當課本（例題的做法和答案摺起來），再在對話裡一段一段帶：確認讀懂、一起做例題、自己做練習（§6）。適用於時間充足、想自己會做。
- 沒指定時：先看使用者有沒有說不想被問，有就選 `read`。再查 repo 裡的日程表或評核說明找截止日：兩天內選 `read`，否則選 `learn`。找不到日期就選 `read`，因為使用者通常是要交了才來問。開頭說一句選了哪個模式、為什麼。

## 1. 找材料，找出「怎樣才算答對」

1. 找題目原文。題目只寫「課本 Problem X」時，到課本把整題（含表格）找出來。
2. 找老師的教法：這個 topic 的講義、例題與答案、軟體輸出範例。
3. 找老師的**答題格式**：過去作業的 Suggested Answers、In-class Exercise 答案。答案紙照這個格式寫，句型照講義寫。
4. 要查的表（t 表、F 表、週期表）用課程發的那份。
5. 讀 PDF 用文字層（`pdftotext -layout -enc UTF-8`，或 PyMuPDF 的 `get_text`）。講義可能有白色字（上課填空用），截圖上看是空白，要從文字層讀出來寫進譯文，標明「課件上是空白，上課填的」。
6. `learn` 另外找練習來源和**測驗的形式**：課本章末題、In-class Exercise、過去的測驗和作業。看它們怎麼給資料（表格、軟體輸出）、分幾小題、答案要寫成什麼句型。沒有測驗樣本時以作業為準。

## 2. 範圍：整份課件，照課件順序

- topic、考試：這個 topic 的**全部**課件頁。先講義（Classnote、Summary），再例題檔（例題、軟體輸出），各自照頁碼順序。最後是**這個 topic 的作業**：作業比例題重要，因為要交、要算分，而且期末考的題型通常和作業差不多。
  - 哪些作業屬於這個 topic：看作業標題寫的 topic 或章節（例如 Assignment 3A 對 Topic 3）、題目用到的方法出自哪幾頁課件、課程大綱的週次表。In-Class Exercise 也算。
  - 每份作業的狀態從日程表、評核資料夾的 README、有沒有老師答案判斷：還沒交、已交、還沒發佈。
- 作業：只挑作業用得到的講義頁，但一樣是整頁、照課件順序，後面接作業題。
- 頁首放一張範圍表：課件頁 → 這頁講什麼 → 哪一題、哪份作業用到、考不考。不考的頁一樣教，標一句「不會直接考」。範圍表下面列這個 topic 的作業和狀態、截止日。趕時間時，告訴讀者先讀作業用到的那幾頁。
- 範圍寫進 `<body data-pages="...">`，例如 `"Classnote Topic 3 p.1-8; Classnote Topic 3 Eg Minitab p.1-5"`。名稱要和 figcaption 裡寫的一樣，build 會檢查每一頁都有整頁圖。

## 3. 前置知識：在用到的地方才補

每個概念先問：讀者要先知道什麼才看得懂？例如 t 檢定要先懂假設檢定、α、自由度、怎麼查 t 表。不寫一大章「零基礎補課」，在**第一次用到的地方**放一個 `<div class="prereq">` 小框，只補這裡需要的那一點。

## 4. 導讀頁

### 第一部分：課件導讀

課件每一頁一個 `<h2>`，標題寫「檔名簡稱 p.N：這頁在講什麼」，照這個順序：

1. **整頁譯文**（`<div class="tr">`）：把這一頁的字**全部**譯成使用者的語言，順序和原文一樣，不摘要、不改寫。公式照原樣寫，術語寫成「中文（English）」。
2. **整頁圖**（`<figure class="page">`），緊接在譯文後面。
3. **這頁在講什麼**：一兩句話，說這頁分幾塊、各在講什麼。
4. **逐塊講解**：課件上的一塊（一個標題、一條公式、一條規則）一個 `<h3>`，從上講到下，直到這頁結束。每塊先放那一塊的小截圖（紅框圈出要看的地方；整頁已經翻過，不用再翻），再講：
   - **為什麼**（`<div class="why">`），依序回答：
     - 這塊在回答什麼問題：用一個現實情境講誰要做什麼決定、不用它會怎樣。
     - 公式為什麼長這樣：從讀者已經懂的東西一步步推出來，每一塊（分子、分母、平方、減 1）說它在做什麼、拿掉會怎樣。用直覺推，不寫證明；推導不考時說一句「看懂就好，不會考」。
     - 算出來的數字怎麼讀：大代表什麼、小代表什麼、通常落在什麼範圍。
   - 課件上有門檻或常數（例如 |*r*| ≥ 0.7、DW 1.5–2.5）時，用「數字從哪來」表交代（格式見下面第 5 步）。
   - 舉例時用老師例題的數字，並說「第二部分 §N 會完整做」。

### 第二部分：例題；第三部分：作業

例題和作業題用同一個骨架，每題一個 `<h2>`。作業依狀態處理：

- 還沒交：照 §5 做答案紙，講解頁每題放「答案紙上寫這樣」。
- 已交、老師答案出了：照老師答案講，答案紙那一步截老師答案（前面放譯文），不另外寫。
- 已交、老師答案還沒出：照講義格式寫，標明「老師答案還沒出，出了要對一次」。
- 還沒發佈：不寫段落，在範圍表下面寫一句「Assignment N 還沒發佈，發佈後叫 `/tutor Assignment N`」。

每題的骨架：

1. **一句話**：這題要你做什麼，用白話講。
2. **為什麼**（`.why`）：這題在問什麼現實問題，要用到第一部分哪幾頁（連到那幾個 §）。概念已經在第一部分講過，不再重講。作業題再加一句：和第二部分哪一題同類、哪裡不一樣。
3. **題目和軟體輸出**：例題檔在範圍內時放整頁（前面放整頁譯文）；不在範圍內時截需要的部分，前面放那一塊的譯文。Minitab 的欄名列名（Source、DF、SS…）、統計表的列和欄也要翻。
4. **套到這題**：一步一步算。用到的數字在材料上看得到時（題目、軟體輸出、統計表、講義），就在這一段放那份材料的截圖，紅框圈出那幾個數字，查表用 `--mark` 標出列與欄。前一段放過同一張也要再放：讀者不該往上翻找數字。
5. **數字從哪來**（`<table class="origin">`，`<caption>數字從哪來</caption>`）：這段用到的每個數字一列，欄位是「值｜從哪來｜固定嗎？換一題怎麼找」。材料上看得到的數字，「從哪來」那格用 `<a href="#圖的id">` 連到這一段圈出它的那張圖；看不到的，在 `<tr>` 寫 `data-from`：`calc`（算出來的）、`convention`（材料上沒寫的慣例）、`constant`（公式裡的常數）。各種來源要交代的不同：
   - 題目給的：在題目哪一句、哪張表。
   - 上一步算的：寫 §編號。
   - 查表：哪張表、哪一列哪一欄，列和欄的值又各自從哪來。
   - 慣例（例如 α = 0.05）：說明這是大家約定的，不是算出來的；為什麼常用這個值；題目怎樣寫就要換（「at the 1% level」→ 0.01）；題目沒寫時老師用什麼。
   - 經驗法則（例如 DW 在 1.5–2.5 之間）：誰定的（老師講義或課本）、背後的道理、別的書可能用別的門檻，考試照老師。
   - 公式裡的常數（例如 *n* − *k* − 1 的 1）：它代表什麼。

   同一個數字在後面的段落再出現，寫「見 §3」就好。
6. **答案紙上寫這樣**：放在 `<div class="sheet">` 裡，內容和答案紙上的那段一模一樣。
7. **常見錯誤**（有才寫）。

`learn` 時例題和還沒交的作業，第 4–6 步整個收進 `<details><summary>做完再打開</summary>…</details>`：使用者要先在對話裡自己做。

### 寫作規則

- 一段只引入一個新詞。新詞第一次出現寫成「中文（English）」，接一句白話解釋。考試用英文時，英文術語要讓讀者認得出來。
- 每個符號第一次出現就說它怎麼唸、代表什麼，例如「β（beta，母體的係數）」。
- 句子短，一句一件事。比喻只在概念太抽象時用一個，而且馬上回到課件上的寫法。
- 寫完一段，假裝自己什麼都不懂再讀一次：還會問「為什麼」「這個數字哪來的」「換一題要怎麼知道」，就是還沒寫完。
- 計算用 HTML 寫（`<span class="frac">` 表示分數），不用圖片。
- 頁首寫：這頁要讀多久、閱讀順序、這頁假設了什麼、範圍表。頁尾寫：「卡在哪就說 §編號」。

### 截圖與組頁

截圖用 `scripts/crop.py`。座標單位是 PDF point，頁碼從 1 起算：

```bash
CROP="uv run --no-project --with pymupdf --with pillow python <skill 目錄>/scripts/crop.py"
$CROP find  講義.pdf 4 "Decision rule"         # 找文字的位置（掃描檔找不到）
$CROP grid  表.pdf 2 grid.png [--rotate 90]     # 掃描檔：畫格線，看圖讀座標
$CROP cut   講義.pdf 4 page.png --dpi 150       # 整頁圖：不給 --clip
$CROP cut   講義.pdf 4 out.png --clip 70,80,560,430 --box 90,250,540,280 [--mark ...] [--rotate 90]
```

`--box` 畫紅框（要看這裡），`--mark` 塗淡黃（查表時的列與欄）。截完一定要用 Read 打開圖看一次，確認框對準了。

每張圖都放在 `<figure>` 裡，`<figcaption>` 寫出處（檔名與 `p.頁碼`）。數字從哪來要連到的圖，給 `<figure>` 一個 `id`。

頁面寫成原始 HTML，`<body data-mode="read|learn" data-pages="...">`，圖片用相對路徑。再用 `scripts/build.py` 組成單一檔案：

```bash
python <skill 目錄>/scripts/build.py guide-src.html -o guide.html
```

build 會內嵌圖片、加上共用樣式、替 `<h2>` / `<h3>` 編號（§1、§1.2，讓使用者能說「卡在 §3.2」），並檢查以下規則，任何一條不過就不產出：

- `data-pages` 宣告的每一頁，都有一張 figcaption 寫著那個名稱和頁碼的 `<figure class="page">`。
- 每張圖都在 `<figure>` 裡，而且 figcaption 有頁碼。
- 不引用外部資源（離線要能開）。
- 每個 `<figure>` 的前一個元素是 `.tr` 譯文。例外：同一段在整頁圖之後的截圖（整頁已經翻過）；圖上沒有要翻的字，在 `<figure>` 寫 `data-tr="none"`。
- 有整頁圖的 `<h2>` 段落要有 `.why`；有 `.calc` 或 `.sheet` 的段落要有 `.why` 和 `.origin` 表。
- `.origin` 表的每一列，要嘛連到同一段裡有那個 `id` 的 `<figure>`，要嘛寫 `data-from="calc|convention|constant"`。
- 每個 `<h2>` 段落的文字量有上限；figure、表格、公式、`.sheet`、`.tr` 譯文不算。超過時拆段，或刪掉不是在教這頁的東西。
- 頁面不能有練習或輸入框；`learn` 的 `.sheet` 要在 `<details>` 裡。

## 5. 作業：答案紙與講解分開

- 答案紙是一份要交的檔案，照老師的 Suggested Answers 格式寫：英文、簡潔，句型照講義。用 HTML 寫，再用 Chrome headless 印成 PDF（`--print-to-pdf`）。
- 所有數字都由一支計算腳本（`calc.py`）算出來，不手打。答案紙寫成 `answer-tpl.html`，講解頁寫成 `guide-tpl.html`，數字用 `{{名稱}}` 佔位，由 `calc.py` 填入。答案紙每一題包在 `<div class="part" data-part="a">…</div><!--/part-->` 裡；講解頁寫 `{{sheet:a}}`，`calc.py` 會把答案紙那一段原樣放進來。這樣兩邊不會對不上。
- 題目本身有給、也能自己算出來的數字（例如表上已有的 MSE、F），在 `calc.py` 裡用 assert 對一次，對不上表示抄錯題。

## 6. learn：在對話裡帶著做

導讀頁做好之後，一次帶一個單元（課件一兩頁，加上用到它的例題和作業題），照「我示範 → 一起做 → 你自己做」的順序。有截止日快到的作業時，先帶那份作業用到的單元：

0. **開始前**讀課程資料夾的 `學習紀錄.md`。第一次學這科時，先出 3–5 題前置知識診斷（能直接答的選擇題），依答案決定要在對話裡先補什麼。上次錯過的地方，先出一題同類的。
1. **讀懂**：請使用者讀導讀頁的 §x–§y，說大約要讀多久。讀完問一兩題確認，問「為什麼」和「這個數字怎麼讀」，不問背定義。答錯就換個講法再講，指回對應的 §。
2. **一起做**：老師的例題，一次只問一步（例如「df₁ 是多少？從 ANOVA 表哪裡看？」），等使用者回答再往下。
   - 答對：簡短確認，說一句為什麼對。
   - 答錯：先給提示（指到哪張圖、哪個 §），第二次再錯才講答案和原因。
   - 不要一次把所有步驟列出來。最後請使用者寫出答案紙那一段，再對照老師的格式改。
3. **做作業**：這個單元有用到的作業題，由使用者自己做，一小題做完再看下一小題。卡住時給提示，規則和「一起做」一樣。還沒交的作業，用使用者改對的答案組成答案紙（§5），交之前再完整對一次。已交的作業照老師答案批改。
4. **自己做**：同類題，依序找課本章末題、In-class Exercise、過去的測驗；用過的跳過。都沒有就自己出：
   - 形式照該科的測驗，沒有測驗樣本就照作業：同樣的題型、資料給法、小題結構、答題句型。
   - 數字用腳本產生並算好答案；需要軟體輸出時，用腳本算出輸出表的數字，排成老師材料的樣式。
   - 題目和答案分兩個檔，放在導讀頁原始檔旁的 `practice/`；給使用者題目檔，答案檔留著批改用。
   - 使用者整題做完再批改：逐小題對答案，照老師評分會看的點（步驟、結論句）指出錯在哪。
5. **記錄**：在 `學習紀錄.md` 寫下教到哪、哪一步錯、錯了幾次、作業做到哪、下次先複習什麼。

對話規則：

- 一次只問一個問題，問完就停，等使用者回答。
- 使用者說「不懂」「直接告訴我」時就講解，講完再出一題同類的讓他自己做。
- 術語第一次定下中文譯名後記進 `學習紀錄.md`，之後都用同一個。

## 7. 驗證

- 用計算腳本重算每個數字；題目或老師答案本身有給的，要對得上。練習題的答案也由腳本算。
- 查表值要對照截圖上框住的那一格。
- `build.py` 通過。
- 用瀏覽器打開導讀頁和答案 PDF，截圖確認圖片有顯示、版面沒有跑掉。

## 8. 交付

產出放在 repo 既有的位置（例如評核資料夾）；沒有慣例時，放在評核資料夾底下的 `tutor/`（原始 HTML、截圖、計算腳本），組好的頁面放在評核資料夾。

最後跟使用者說：先讀哪個檔、大約要讀多久、答案紙在哪、交之前要做什麼（印、簽名、檔名）。`learn` 則接著開始 §6 的第一個單元。
