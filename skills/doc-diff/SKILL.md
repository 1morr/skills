---
name: doc-diff
description: Make a word-level before/after diff page of a document or rendered output (docx, PDF, HTML page or poster, Markdown, text) that a person reads in a browser, with the whole document side by side or merged, an optional reason under each change, and table cells compared one by one. Use when the user wants to see what changed between two versions of a document, report, assignment or poster, or asks for a diff HTML (diff 的 html、左邊原來右邊修改、前後對照、改了哪些字), or when another skill needs a document diff. For explaining a code change with run evidence, use showcase instead.
---

# Doc diff

做一頁 HTML，讓人看出同一份文件的兩個版本逐字差在哪裡。比的是讀者看到的內容，例如 docx 的段落和表格、PDF
與網頁上的文字；不是產生它的原始碼。原始碼的改動交給 git diff 或 showcase。

腳本：這個 skill 的 `scripts/diff_html.py`，下文的 `<D>` 指 `scripts/` 的絕對路徑。它的開頭寫了完整用法和 `notes.json` 的格式。

## 1. 取得兩個版本

- 兩個檔案：直接用。
- git 裡的兩個版本：`git show <rev>:<路徑> > <暫存目錄>/before.<副檔名>`，after 也照做，或直接用工作區的檔。
- 由原始碼產生的文件（例如腳本產出 docx、HTML 輸出 PDF）：比**產出**。兩邊都要是同一套產生方式做出來的。

docx、pdf、html、htm 照格式抽字，其他副檔名都當純文字，以空行分段。圖片裡的字讀不到。

## 2. 寫說明（有根據時才寫）

知道每處為什麼改的話（commit message、審查紀錄、對話），寫一份 `notes.json`：

- `notes`：`match` 填該段的原文片段，`note` 寫原因，`tag` 選填（例如「必須修」）。
- `other`：不在文字裡的改動，例如版面、顏色、圖。
- `removed_midway`：中途加過、最後又刪掉的內容（比對只看得到兩端）。
- `images`：兩版的渲染圖並排，例如 PDF 逐頁轉成的圖，或用 playwright 照實際尺寸截的海報。

沒有根據的原因不寫。讀者會照說明判斷改得對不對，所以空著也比猜的好。

## 3. 產出

```
uv run --no-project --with python-docx --with pymupdf python <D>/diff_html.py <前版> <後版> -o <輸出.html> \
  [--notes notes.json] [--title 標題] [--before-label 起點] [--after-label 最終版]
```

只比 html 或文字時，可以不帶 `--with`。只想知道兩版各多少字時，加 `--words`，不產生 HTML。

輸出放在使用者或呼叫的 skill 指定的位置；沒有指定的話，放在暫存目錄。stderr 印出 `UNMATCHED NOTE`，代表那條
說明沒對上任何改動過的段落。通常是 `match` 抄錯了，或那段其實沒改；修正之後重跑，直到一條都不剩。

## 4. 檢查

用 playwright 打開頁面。file:// 會被擋，要先開本機 http server。確認三件事：

- 「合併顯示」「只看改動」兩個開關能切換。
- 圖片有顯示出來。
- 頁首的改動數合理。改動數大得不尋常時，先看是不是整欄、整段錯位（例如表格插了一欄、段落被拆成兩段），
  弄清楚再交。

交出時給頁面的路徑，並用一句話說明改了幾處、表格改了幾格。
