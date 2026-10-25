---
name: tutor
description: Teach a university course topic, assignment, or exam to a learner who missed every lecture and has zero background, using the teacher's own slides and answers as the only source of truth. Produces a self-contained HTML guide with the relevant slide regions cropped in and boxed, so the learner never has to flip through the course files, plus (for assignments) an answer sheet written in the teacher's format. Two modes - read (one complete page with every answer; never asks questions or gives exercises; for a deadline or exam within about two days, or when the learner just wants to read it through) and learn (short lessons with checks and a learning record). Use when asked to teach, explain, or review course material, to do an assignment while teaching how it is done, or to prepare for a quiz or exam. Also triggers on 教我、看不懂、零基礎、沒聽過課、複習、備考、作業教我.
argument-hint: "[作業 | topic | 考試] [read | learn]"
---

# Tutor

讀者沒上過課、沒有前置知識，看到符號和英文術語就卡住。目標是讓他**只看這一頁就能自己答出老師的題目**，不用翻課件。

老師的材料是唯一標準：講義、例題答案、過去作業的 Suggested Answers、老師的統計表。課本是第二順位；網路和模型自己的知識只用來補前置知識、講為什麼、舉現實例子，而且符號和寫法要對齊老師。老師和課本不一致時照老師，並標出來。

## 叫用與模式

- `read`（一次讀完）：一整頁，每題附完整做法和答案。**全程不提問、不出練習。**範圍不確定時自己選最可能的，寫在頁首「這頁假設了什麼」。適用於交件或考試在兩天內，或使用者說「趕」「明天交」「今晚要考」「不要問我」「直接給我看」。
- `learn`（分課學）：時間充足、想自己練。先診斷，再一次只教一小課，每課有回想題，記學習紀錄。
- 沒指定時：先看使用者有沒有說不想被問，有就選 `read`。再查 repo 裡的日程表或評核說明找截止日：兩天內選 `read`，否則選 `learn`。找不到日期就選 `read`，因為使用者通常是要交了才來問。開頭說一句選了哪個模式、為什麼。

## 1. 找材料，找出「怎樣才算答對」

1. 找題目原文。題目只寫「課本 Problem X」時，到課本把整題（含表格）找出來。
2. 找老師的教法：這個 topic 的講義、例題與答案、軟體輸出範例。
3. 找老師的**答題格式**：過去作業的 Suggested Answers、In-class Exercise 答案。答案紙照這個格式寫，句型照講義寫。
4. 要查的表（t 表、F 表、週期表）用課程發的那份。
5. 讀 PDF 用文字層（`pdftotext -layout -enc UTF-8`，或 PyMuPDF 的 `get_text`）。講義可能有白色字，截圖上看是空白，要從文字層讀出來另外寫在頁面裡。

## 2. 考點地圖：只教會用到的東西

列一張表：每一題（考試則是每個考點）→ 要用到的概念 → 老師講義第幾頁。**只有地圖上的東西會寫進頁面。**不重寫整份課件，也不寫「完整版」。使用者要過的是這份作業或這次考試，不是一本教科書。

地圖限制的是**教哪些**，不是**教多深**：地圖上的每一樣，都要教到讀者知道它為什麼這樣做、數字從哪來，換一題也會做。只給步驟的頁面，讀者照抄得出這題，換個數字就不會了。

`read` 時依分數比重或出題機率排序；`learn` 時依前置關係排序，一課只拿一兩個點。

## 3. 前置知識：在用到的地方才補

每個概念先問：讀者要先知道什麼才看得懂？例如 t 檢定要先懂假設檢定、α、自由度、怎麼查 t 表。

- 不寫一大章「Part 0 零基礎補課」。在**第一次用到的地方**放一個「先補」小框，只補這裡需要的那一點。
- `learn`：開始前先出 3–5 題前置知識診斷（能直接答的選擇題），依答案決定要補哪些。

## 4. 講解頁

每題或每個考點一個 `<h2>` 段落，固定用這個骨架：

1. **一句話**：這題要你做什麼，用白話講。
2. **為什麼**（`<div class="why">`）：讀者什麼都不懂時會先問的事，依序回答：
   - 這個方法在回答什麼問題：用一個現實情境講誰要做什麼決定、不用這個方法會怎樣。題目本身就是現實情境時用題目的。
   - 公式為什麼長這樣：從讀者已經懂的東西一步步推出來，每一塊（分子、分母、平方、減 1）說它在做什麼、拿掉會怎樣。用直覺推，不寫證明；推導不考時說一句「看懂就好，不會考」。
   - 算出來的數字怎麼讀：大代表什麼、小代表什麼、通常落在什麼範圍。
3. **課件原圖**：把老師講義上教這件事的那一塊截下來，用紅框圈出要看的地方，旁邊逐句翻譯紅框裡的英文。
4. **套到這題**：一步一步算。查表要附查表截圖，用標色標出列與欄。
5. **數字從哪來**（`<table class="origin">`，`<caption>數字從哪來</caption>`）：這段用到的每個數字一列，欄位是「值｜從哪來｜固定嗎？換一題怎麼找」。「從哪來」分這幾種，每種要交代的不同：
   - 題目給的：在題目哪一句、哪張表。
   - 上一步算的：寫 §編號。
   - 查表：哪張表、哪一列哪一欄，列和欄的值又各自從哪來。
   - 慣例（例如 α = 0.05）：說明這是大家約定的，不是算出來的；為什麼常用這個值；題目怎樣寫就要換（「at the 1% level」→ 0.01）；題目沒寫時老師用什麼。
   - 經驗法則（例如 |*r*| ≥ 0.7 算多重共線性、DW 在 1.5–2.5 之間）：誰定的（老師講義或課本）、背後的道理、別的書可能用別的門檻，考試照老師。
   - 公式裡的常數（例如 *n* − *k* − 1 的 1）：它代表什麼。

   同一個數字在後面的段落再出現，寫「見 §3」就好。
6. **答案紙上寫這樣**：放在 `<div class="sheet">` 裡，內容和答案紙上的那段一模一樣。
7. **常見錯誤**（有才寫）。

寫作規則：

- 一段只引入一個新詞。新詞第一次出現寫成「中文（English）」，接一句白話解釋。考試用英文時，英文術語要讓讀者認得出來。
- 每個符號第一次出現就說它怎麼唸、代表什麼，例如「β（beta，母體的係數）」。
- 句子短，一句一件事。比喻只在概念太抽象時用一個，而且馬上回到課件上的寫法。
- 寫完一段，假裝自己什麼都不懂再讀一次：還會問「為什麼」「這個數字哪來的」「換一題要怎麼知道」，就是還沒寫完。
- 計算用 HTML 寫（`<span class="frac">` 表示分數），不用圖片。
- 頁首寫：這頁要讀多久、閱讀順序、這頁假設了什麼。頁尾寫：「卡在哪就說 §編號」。

截圖用 `scripts/crop.py`。座標單位是 PDF point，頁碼從 1 起算：

```bash
CROP="uv run --no-project --with pymupdf --with pillow python <skill 目錄>/scripts/crop.py"
$CROP find  講義.pdf 4 "Decision rule"         # 找文字的位置（掃描檔找不到）
$CROP grid  表.pdf 2 grid.png [--rotate 90]     # 掃描檔：畫格線，看圖讀座標
$CROP cut   講義.pdf 4 out.png --clip 70,80,560,430 --box 90,250,540,280 [--mark ...] [--rotate 90]
```

`--box` 畫紅框（要看這裡），`--mark` 塗淡黃（查表時的列與欄）。截完一定要用 Read 打開圖看一次，確認框對準了。

每張圖都要放在 `<figure>` 裡，`<figcaption>` 寫出處（檔名與 `p.頁碼`）。

頁面寫成原始 HTML，`<body data-mode="read">` 或 `"learn"`，圖片用相對路徑。再用 `scripts/build.py` 組成單一檔案：

```bash
python <skill 目錄>/scripts/build.py guide-src.html -o guide.html
```

build 會內嵌圖片、加上共用樣式、替 `<h2>` / `<h3>` 編號（§1、§1.2，讓使用者能說「卡在 §3.2」），並檢查以下規則，任何一條不過就不產出：

- 每張圖都在 `<figure>` 裡，而且 figcaption 有頁碼。
- 不引用外部資源（離線要能開）。
- 有 `.calc` 或 `.sheet` 的 `<h2>` 段落，要有 `.why` 區塊和 `.origin` 表。
- 每個 `<h2>` 段落的文字量和整頁總量有上限。figure、表格、公式、`.sheet` 不算。超過時，代表你在寫參考書，不是在教：砍掉地圖外的東西，或拆成兩課。
- `read` 不能有練習或輸入框；`learn` 至少要有一題 `<details class="check">` 回想題。

## 5. 作業：答案紙與講解分開

- 答案紙是一份要交的檔案，照老師的 Suggested Answers 格式寫：英文、簡潔，句型照講義。用 HTML 寫，再用 Chrome headless 印成 PDF（`--print-to-pdf`）。
- 所有數字都由一支計算腳本（`calc.py`）算出來，不手打。答案紙寫成 `answer-tpl.html`，講解頁寫成 `guide-tpl.html`，數字用 `{{名稱}}` 佔位，由 `calc.py` 填入。答案紙每一題包在 `<div class="part" data-part="a">…</div><!--/part-->` 裡；講解頁寫 `{{sheet:a}}`，`calc.py` 會把答案紙那一段原樣放進來。這樣兩邊不會對不上。
- 題目本身有給、也能自己算出來的數字（例如表上已有的 MSE、F），在 `calc.py` 裡用 assert 對一次，對不上表示抄錯題。
- `read`：講解頁每題直接附完整做法和答案。
- `learn`：先教概念，每題先讓使用者自己做；`.sheet` 放在 `<details>` 裡，做完再打開對答案。

## 6. 驗證

- 用計算腳本重算每個數字；題目或老師答案本身有給的，要對得上。
- 查表值要對照截圖上框住的那一格。
- `build.py` 通過。
- 用瀏覽器打開講解頁和答案 PDF，截圖確認圖片有顯示、版面沒有跑掉。

## 7. 交付

產出放在 repo 既有的位置（例如評核資料夾）；沒有慣例時，放在評核資料夾底下的 `tutor/`（原始 HTML、截圖、計算腳本），組好的頁面放在評核資料夾。

最後跟使用者說：先讀哪個檔、大約要讀多久、答案紙在哪、交之前要做什麼（印、簽名、檔名）。

## learn 模式另外要做

- 一課 10–15 分鐘，只教一兩個點，結尾 2–3 題 `<details class="check">` 回想題。
- 在課程資料夾的 `學習紀錄.md` 記下：教過什麼、診斷和回想時錯在哪裡、下一課要教什麼。下次開始前先讀它。
- 術語第一次定下中文譯名後，之後各課都用同一個。
