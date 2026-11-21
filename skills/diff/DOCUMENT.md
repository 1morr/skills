# 文件的兩個版本

比對讀者最終看到的成品檔案（docx、PDF、HTML 頁面或海報、Markdown、純文字）。

## 1. 取得兩個版本

- 現成兩個檔案：直接使用。
- git 裡的版本：`git show <rev>:<路徑> > <暫存目錄>/before.<副檔名>`，另一邊照做或取工作區檔案。
- 由原始碼或腳本產生的文件（如腳本產出 docx、HTML 匯出 PDF）：先用同一套產生方式做出兩版成品，再拿成品比對。

各格式怎麼抽字、表格怎麼逐格比，寫在 `scripts/diff.py` 開頭。文字擷取涵蓋不到的視覺資訊由對照頁補齊：

- PDF 大約一行一個文字區塊，公式常拆成碎片：後版為 `.pdf` 時，`scripts/document.html` 會自動收緊段距排成連續文字。
- 海報、圖表與版面配置：在對照頁加上兩版渲染圖並排。

## 2. 比對

純文字、Markdown 或 HTML：

```bash
python3 scripts/diff.py <前版> <後版> -o <輸出>/diff.json
```

輸入含 `.docx` 或 `.pdf` 時透過 `uv` 載入解析套件：

```bash
uv run --no-project --with python-docx --with pymupdf python scripts/diff.py <前版> <後版> -o <輸出>/diff.json
```

- **純資料輸出分支（`--json-only` / 只取差異 JSON）**：當上游流程（如 `coursework`）只需要結構化差異而不需展示網頁時，跑完上方 `scripts/diff.py` 寫出 `diff.json` 即完成，跳過第 3、4 步的 `document.html`、`fill.py` 與瀏覽器檢查，直接回傳 `diff.json` 路徑與 `counts.groups`（及 `counts.table_cells`）。
- stderr 最後一行印出計數，給讀者看的改動處數取 `groups`。若處數異常偏大，先檢查是否發生整段錯位（例如表格插欄未對齊表頭或段落拆分方式不同），釐清後再往下。
- **說明**（已知修改原因時選填）：寫成 `notes.json` 以 `--notes` 傳入；從內容反推的原因將 `tag` 設為 `"推斷"`。若 stderr 出現 `UNMATCHED NOTE`，修正 `match` 字串直到全部對上。

## 3. 寫頁面

把 `scripts/document.html` 複製成 `page-src.html`。整份文件、逐字與表格改動標記、計數、說明及工具列（並排／合併、只看改動、上一處／下一處）皆由模板內建 script 從 `diff.json` 繪製。在 `page-src.html` 填入：

- `<title>`、`<h1>` 的標題，以及 `.lede` 那句結論（改了幾處、最要看哪幾處）。
- 額外的段落（有需要時才加，各自一個 `<h2>`）：版面／配色／圖片改動、中途加過又刪掉的內容、兩版渲染圖並排。渲染圖兩版用同一方法轉圖（PDF 用 PyMuPDF `page.get_pixmap(dpi=…)` 逐頁轉圖，HTML 與海報用瀏覽器自動化工具依實際尺寸擷取），排法照 [LOOK.md](LOOK.md)〈渲染圖對照〉。
- 原文件為無襯線字體（簡報、海報）時，`<body>` 改為 `<body class="sans">`。
- 改動集中在視覺圖面、文字差異極少時（海報、圖表、純版面調整）：把額外段落移到 `<div class="colhead">` 前面讓渲染圖領頭，結論也先講視覺改動。

再用 `scripts/fill.py` 填入 `diff.json`、內嵌媒體與樣式並執行 1440px / 390px 水平溢出檢查：

```bash
python3 scripts/fill.py page-src.html -o <輸出.html> --json diff=<輸出>/diff.json
```

## 4. 檢查與交付

照 [SKILL.md](SKILL.md)〈檢查與交付〉與 [HANDOFF.md](../../pages/HANDOFF.md) 交付。

完成條件：`scripts/fill.py` 退出碼 0；輸出檔搜不到 `{{標題` 與 `{{結論`；stderr 無 `UNMATCHED NOTE`。
