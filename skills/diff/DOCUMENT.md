# 文件的兩個版本

`diff.py` 和 `fill.py` 開頭寫了完整用法和輸出格式。

## 1. 取得兩個版本

- 兩個檔案：直接用。
- git 裡的版本：`git show <rev>:<路徑> > <暫存目錄>/before.<副檔名>`，另一邊照做或用工作區的檔。
- 由原始碼產生的文件（腳本產出 docx、HTML 輸出 PDF）：比**產出**，兩邊用同一套產生方式做出來。

docx、pdf、html、htm 照格式抽字，其他副檔名當純文字、以空行分段。限制：

- pdf 大約一行一個區塊，公式常被拆成碎片；頁面上把連續的區塊排得像連續的文字。
- 只有 docx 的表格會逐格比；pdf 和 html 的表格會拆成一格或一列一個區塊。
- 圖片裡的字讀不到：海報、圖表的改動要靠渲染圖並排。

## 2. 比對

```
uv run --no-project --with python-docx --with pymupdf python <S>/diff.py <前版> <後版> -o <暫存>/diff.json \
  [--notes notes.json] [--before-label 起點] [--after-label 最終版]
```

只比 html 或文字時可以不帶 `--with`。只要兩版字數時加 `--words`。

stderr 最後一行是計數。`groups` 是連續改動合成的「處」，給讀者看的改動數用它；其他是區塊數。數字大得不尋常時先看是不是整段錯位（表格插了一欄、段落被拆成兩段），弄清楚再往下。

**說明**（知道每處為什麼改時才寫）：`notes.json` 的格式在 `diff.py` 開頭，對上的會掛在那一段的 `notes`。從內容反推、沒有來源的原因，`tag` 寫「推斷」。stderr 印 `UNMATCHED NOTE` 代表那條沒對上任何改動過的段落，多半是 `match` 抄錯或那段其實沒改：修到一條都不剩。

## 3. 寫頁面

寫 `page-src.html`：版面、樣式和一段讀 JSON 畫出內容的 JS，資料放在

```html
<script type="application/json" id="data">__DATA__</script>
```

再用同一份 `diff.json` 填進去，產出單一檔案（相對路徑的圖片會被內嵌）：

```
python <S>/fill.py page-src.html -o <輸出.html> --json diff=<暫存>/diff.json
```

頁面要有：

- 頁首：標題、兩版的標籤、改動數（`groups` 處，表格另計改了幾格），和 SKILL.md〈共同標準〉要的那句結論。
- **整份文件**照順序顯示，改動處標出刪掉和加上的字。
- 切換：左右並排 / 合併成一欄；只看改動（沒改的段落收起來，留一行提示收了幾段）。
- 說明掛在對應的改動下面，`tag` 看得出來。
- 表格逐格標示：改過的格子、新加或刪掉的列，以及 `columns` 裡是 `null` 的整欄。
- 不在文字裡的改動（版面、顏色、圖）、中途加過又刪掉的內容（比對只看得到兩端）、兩版的渲染圖並排：有就直接寫進頁面，各自一段。渲染圖兩版用同一個方法做（PDF 用 PyMuPDF 的 `page.get_pixmap(dpi=…)` 逐頁轉圖，HTML 和海報用瀏覽器自動化工具照實際尺寸截），排法照 LOOK.md〈渲染圖對照〉。

## 4. 檢查

照 SKILL.md〈檢查與交付〉。

完成條件：頁首的改動數等於 `diff.json` 的 `counts.groups`；渲染圖有顯示；stderr 沒有 `UNMATCHED NOTE`。
