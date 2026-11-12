# 解說頁的寫法

`explain` 和 `checkpoint` 的 HTML 頁共用這份。頁面是一次性的：放 scratchpad，不進 repo。

## 來源

讀者靠這頁理解系統，一句錯的說明會讓他帶著錯的印象去改程式。

- 「現在怎麼運作」以**程式碼**為準，每句附 `檔案:行`。
- 「為什麼這樣做」引文件原文：需求、計畫、ADR、偏差紀錄、票的 Comments、commit，附章節或 hash。
- 文件說的和程式做的不一樣：不在正文裡挑一邊講，另列〈文件和程式對不上〉，兩邊的來源都附。
- 找不到來源的句子標 `推斷`（灰色小標籤），寫出根據什麼推的。
- 決定附**決定者**：使用者定、使用者同意（agent 提議）、Agent 定、不明（當時沒記）。repo 有標就照標，沒標的照原文判斷，判斷不了寫不明。

## 圖

用 Mermaid，只用 `flowchart`、`sequenceDiagram`、`stateDiagram-v2`、`classDiagram`、`erDiagram` 這幾種。

- 一張圖 ≤ 15 個節點；更大就拆成總圖加分圖。
- 節點標籤加雙引號，寫使用者看得懂的話；程式名稱放括號裡，例如 `A["送下載（submit_job）"]`。
- 每張圖下面一兩句說這張圖在講什麼、從哪裡讀起。

圖寫在 `<pre class="mermaid">` 裡，頁尾載入：

```html
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral" });
</script>
```

## 外觀

照 [`../diff/LOOK.md`](../diff/LOOK.md) 的〈Token〉和〈字體〉。版面是一般文章：70ch 文字欄、標題和留白分段，表格只用在真正逐列比較的地方。

## 寫法

讀者是 repo 的主人，常常不是這個領域的專家。

- 先講效果，再講機制：「你按下確認之後，Berth 會…」，再說哪個模組做的。
- 名詞用 repo 名詞表的詞；第一次出現附一句白話解釋。
- 變化寫成「以前…，現在…」。

## 交出前

1. **核對**：把頁上每一句附來源的說法和它的來源，交給一個沒看過你結論的子代理（審查用的模型）逐句對照，回報對不上的句子。改掉，或改標 `推斷`。
2. **渲染**：用 playwright 打開，確認每張圖都畫成 svg、頁面上沒有 `Syntax error`。
3. 用預設瀏覽器打開（macOS `open`、Windows `start`、Linux `xdg-open`），在對話給完整路徑。

完成條件：核對回報的每一句都處理了；每張圖都畫得出來。
