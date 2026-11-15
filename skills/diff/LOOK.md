# 外觀

這頁是**校樣**：讀者拿它對照兩版，找出每一處改動，判斷改得對不對。內容是主角，介面退到邊上。程式頁每一頁照內容排版，文件頁用現成的那一份；標記方式每頁都一樣，讀者換一頁不必重新學怎麼讀。

樣式由 `<S>/fill.py` 內嵌（`<P>/scripts/tokens.css` 和 `<S>/diff.css`）：原始頁寫結構和 JS，用下面的 class。這些不夠用時在原始頁自己的 `<style>` 補，顏色和字體照 `<P>/TOKENS.md` 取變數；變數本身不重新定義，否則 `fill.py` 拒絕產出。

## 原則

- **文件長得像文件**：文件頁的內文是書本排版（襯線字、70ch 行寬）；原文件是無襯線的（簡報、海報）和程式頁，在 `<body>` 加 `class="sans"`。
- **改動跳出來，沒改的退後**：每處改動同時有底色、刪除線或底線、頁邊的**修訂條**三種標記。區塊之間靠標題和留白分開；外框和陰影只給渲染圖和證據面板。

## 文件頁

版面、標記和工具列都在 `<S>/document.html` 裡，照 DOCUMENT.md 複製、填空，不重寫。額外的段落用下面〈渲染圖對照〉的寫法；要加說明時用 `.note`，裡面的標籤用 `.tag`，推斷寫 `.tag.guess`。

## 渲染圖對照

- 兩版用同一個方法轉圖，裁成**同一個框**：取兩版內容範圍的聯集，四周留邊，頁面下方的大片空白不要截進來。
- `.shots` 裡兩個 `<figure>` 等寬並排，`<figcaption>` 寫版本和頁碼。不成對的單張渲染圖用 `<figure class="shot">`。
- 尺寸相同就加滑桿：`.slider` 裡 `.stack` 疊兩張 `<img>`，下面 `.ends` 放「前」、`<input type="range">`、「後」；JS 把滑桿的值寫進 `.stack` 的 `--at`（例如 `40%`）。文件頁的 script 已經接好滑桿和點圖放大，程式頁要自己接。
- 兩版像素相同的頁收成一行「第 n 頁兩版像素相同」，圖放進 `<details>`。點圖用 `<dialog class="zoom">` 放大，點一下或按 Esc 關閉。

## 程式頁

寬螢幕左邊一條目錄：`<div class="layout">` 裡放 `<nav class="toc">` 和 `<main>`，用 IntersectionObserver 把目前段落的連結標成 `.here`。文字欄 70ch；要伸到整欄寬的區塊加 `.full`。

| 寫法 | 用在 |
| --- | --- |
| `.meta` | 標題下面一行：`base..head` 短 SHA（`.mono`）、分支、檔案數加 `+n −m`（`.plus` / `.minus`）、證據等級 |
| `.lede` | 摘要 |
| `<blockquote>`，裡面 `.src` | 「為什麼」引用的原文，和它的來源，例如 `5fca937 message` |
| `.tag.guess` | 推斷的句子 |
| `.tree`，新增的部分 `.new` | 呼叫樹、檔案樹這類示意圖；加 `role="img"` 和 `aria-label` |
| `.risk`、`.risk.one-way` | 合併風險的定調詞：雙向門、單向門。後面接一句理由，再列影響範圍 |
| `dl.decisions`，替代方案 `.alt` | 決定：`<dt>` 寫選擇，`<dd>` 寫理由和來源 |
| `.evidence` 裡兩個 `.panel`；`.panel-head` 的結果用 `.bad` / `.good`；輸出 `pre.out`，一行一個 `<span>`，失敗的行 `.fail`、修改後通過的同一條 `.pass`、刪減處 `.cut` | 證據：前後並排，標頭寫「修改前 · SHA」和結果（例如「12 條 FAIL · exit 1」） |
| `.hunk` 裡的 `<table>`：每列 `td.ln` 舊行號、`td.ln` 新行號、`td.sign`、程式碼；列加 `.add` / `.rm`，新檔的列再加 `.newfile`，省略處 `.skip` | 關鍵 diff，每段上方一句話說明 |
| `table.files`：`td.path`（目錄部分 `.dir`，斜線後加 `<wbr>`）、`td.stat`、`td.what` | 檔案表 |
| `ol.try`，指令放 `.cmd` | 親自試 |

圖示畫線寬一致的 inline SVG。計數寫進句子裡或圖例裡；圖例裡的「刪除」「新增」直接用 `<del>` / `<ins>`。
