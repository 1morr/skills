---
name: diff
description: 把同一份文件或報告的兩版（docx、PDF、HTML、Markdown）做成逐字與表格對照頁或差異 JSON。使用者要文件前後對照頁，或上游流程要抽兩版差異時用。
---

比對同一份文件或報告的兩個版本，讓讀者或上游流程直接取得精確的逐字與表格改動紀錄。

本檔與附屬文件的相對路徑以 `skills/diff/` 為準；共用層 `../../pages/` 可用環境變數 `SKILLS_ROOT` 指定 plugin 根目錄覆寫。

## 選分支

- **純資料輸出分支（`--json-only` / 只取差異 JSON）**：當上游流程（如 `coursework`）只需要結構化差異而不需展示網頁時，取得兩版成品後直接執行：
  ```bash
  python3 scripts/diff.py <前版> <後版> -o <輸出>/diff.json
  ```
  （輸入含 `.docx` 或 `.pdf` 時改用 `uv run --no-project --with python-docx --with pymupdf python scripts/diff.py <前版> <後版> -o <輸出>/diff.json`。）執行完即完成，跳過 `scripts/document.html`、`scripts/fill.py` 與瀏覽器檢查。
- **網頁交付分支（文件對照頁 HTML）**：使用者或上游流程需要一頁前後對照 HTML 時，依 [DOCUMENT.md](DOCUMENT.md) 組出單一自包含網頁。

## 對照頁標準

1. **改動標記全部出自計算**：逐段、逐字與表格逐格比對由 `scripts/diff.py` 算出 `diff.json`；把 `scripts/document.html` 複製為 `page-src.html` 填入標題與結論後，由 `scripts/fill.py` 注入 `diff.json`、本機媒體與共用樣式。兩支腳本的參數與輸出格式見各自檔案開頭。
2. **原因有根據才寫**：commit message、審查紀錄、票、規格、對話都算根據；從內容反推的原因標「推斷」，缺乏根據處直接留白。
3. **單一離線檔案**：圖片與影片寫相對 `page-src.html` 的本機路徑，由 `scripts/fill.py` 內嵌為 data URI（`fill.py` 會拒絕 `http://`、`https://` 與 `//` 外部網址），離線打開即可完整閱讀。
4. **外觀與元件**：版面與工具列內建於 `scripts/document.html`；額外段落（如渲染圖並排、滑桿、說明標籤）照 [LOOK.md](LOOK.md) 的結構與 class 撰寫。
5. **頁首給結論**：頁首一句話先寫改了幾處（取 `counts.groups`）與最該看哪幾處。

## 檢查與交付

- **純資料輸出（`--json-only`）**：確認 `diff.json` 已寫出（有傳 `--notes` 時 stderr 無 `UNMATCHED NOTE`），將 `diff.json` 完整路徑與改動處數（`counts.groups`；表格有改時附 `counts.table_cells`）交回呼叫方。
- **網頁交付（`document.html` 對照頁）**：`scripts/fill.py` 內建以無頭瀏覽器檢查 1440px 與 390px 水平溢出（報溢出時依 stderr 修正後重填；印出找不到瀏覽器的提醒時才依提醒補查），固定模板 `document.html` 免除另開瀏覽器自動化工具截寬窄兩張圖與點擊切換鈕。輸出放在使用者或呼叫方指定的位置，未指定時放在本次對話的暫存目錄（或 `mktemp -d` 建於 repo 外）。直接交給使用者時照 [HANDOFF.md](../../pages/HANDOFF.md) 給完整絕對路徑（遠端環境附網址），並加一句話：改了幾處（表格有改時再說改了幾格）；由其他 skill 呼叫時交回路徑與這句話。

完成條件：純資料分支寫出 `diff.json` 並回報處數；網頁分支 `scripts/fill.py` 退出碼 0、輸出檔無殘留 `{{標題` 或 `{{結論`、stderr 無 `UNMATCHED NOTE`，且接收方拿到路徑與改動處數。
