# 外觀

這頁是**校樣**：讀者拿它對照文件兩版，找出每一處改動，判斷改得對不對。內容是主角，介面退到邊上。

共用樣式由 `scripts/fill.py` 內嵌（`../../pages/scripts/tokens.css` 與 `scripts/diff.css`；共用目錄可用環境變數 `SKILLS_ROOT` 覆寫）。額外段落若需補樣式，寫在 `page-src.html` 自己的 `<style>`，顏色和字體一律從 [TOKENS.md](../../pages/TOKENS.md) 取變數。

## 原則

- **文件長得像文件**：內文採書本排版（襯線字、70ch 行寬）；原文件為無襯線字體（簡報、海報）時，在 `<body>` 加 `class="sans"`。
- **改動跳出來，沒改的退後**：每處改動同時有底色、刪除線或底線、頁邊的**修訂條**三種標記。區塊之間靠標題和留白分開；外框和陰影只給渲染圖。

## 文件頁結構

版面、改動標記和工具列都在 `scripts/document.html` 裡，照 [DOCUMENT.md](DOCUMENT.md) 複製成 `page-src.html` 並填入標題、結論與額外段落。額外段落使用下方〈渲染圖對照〉的 class；要補充說明時用 `.note`，裡面的標籤用 `.tag`，推斷標為 `.tag.guess`。

## 渲染圖對照

- 兩版用同一個方法轉圖，裁成**同一個框**：取兩版內容範圍的聯集並四周留邊，裁去頁面下方的大片空白。
- `.shots` 裡放兩個 `<figure>` 等寬並排，`<figcaption>` 寫版本和頁碼。不成對的單張渲染圖用 `<figure class="shot">`。
- 尺寸相同時可加滑桿：`.slider` 裡 `.stack` 疊兩張 `<img>`，下面 `.ends` 放「前」、`<input type="range">`、「後」；`scripts/document.html` 內建 script 已接好滑桿 `--at` 更新與點擊圖片 `<dialog class="zoom">` 放大（點一下或按 Esc 關閉）。
- 兩版像素相同的頁收成一行「第 n 頁兩版像素相同」，圖收進 `<details>`。
