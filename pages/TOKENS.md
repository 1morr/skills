# 配色與字體

diff、explain、checkpoint、dashboard 的頁面共用這組 token 和字體，讀者換一頁不必重新學怎麼讀。

## Token

變數的值在 [scripts/tokens.css](scripts/tokens.css)，只有那一份：`build.py` 組頁時內嵌它，頁面裡不重寫；不經 `build.py` 的頁面（diff）把整份放進 `<style>` 的開頭。整頁的顏色只從這組變數取，不另寫色碼；深色模式跟著 `prefers-color-scheme`。

- 底與線：`--paper` 頁面、`--panel` 襯底、`--rule` 線。
- 字：`--ink` 內文、`--ink-2` 次要。
- 三組狀態色，各有 `-bg` 底、`-ink` 字、`-bar` 邊條：`--del-*` 刪除或沒過，`--ins-*` 新增或通過，`--note-*` 說明或但書。
- `--accent` 只用在可以操作的東西上：選中的切換、焦點環、連結、滑桿。`::selection`、`caret-color`、`accent-color`、`scrollbar-color` 和 `:focus-visible` 也從這組取色。

## 字體

只用系統字，離線也能顯示。Latin 字族排在 CJK 前面，英文和數字才會用 Latin 字形。

三個字族變數 `--font-ui`、`--font-doc`、`--font-code` 也在 `tokens.css`。

- 文件內文用 `--font-doc`，工具列、標籤、說明和計數用 `--font-ui`。原文件是無襯線的（簡報、海報），內文也改用 `--font-ui`。
- 字級固定用 rem：內文 1.0625rem、行高 1.7；說明與標籤 0.875rem，不再更小；段落標題 1.375rem、頁面標題 2rem（手機 1.625rem）；摘要或結論段 1.125–1.25rem。
- 計數、行號和數字欄加 `font-variant-numeric: tabular-nums`；`html` 加 `text-autospace: normal`。
- 次要文字用 `--ink-2` 加上較小的字級來區分，正體字。
