# 配色與字體

diff、explain、checkpoint 產出的頁面共用這組 token 和字體，讀者換一頁不必重新學怎麼讀。

## Token

整頁的顏色只從這組變數取，不另寫色碼；深色模式跟著 `prefers-color-scheme`。

```css
:root {
  color-scheme: light dark;
  --paper: oklch(0.985 0.004 85);   --panel: oklch(0.962 0.006 85);   --rule: oklch(0.88 0.008 85);
  --ink: oklch(0.25 0.012 260);     --ink-2: oklch(0.47 0.012 260);   --accent: oklch(0.5 0.15 255);
  --del-bg: oklch(0.93 0.045 25);   --del-ink: oklch(0.44 0.16 25);   --del-bar: oklch(0.62 0.19 25);
  --ins-bg: oklch(0.93 0.055 165);  --ins-ink: oklch(0.38 0.1 165);   --ins-bar: oklch(0.6 0.13 165);
  --note-bg: oklch(0.955 0.04 85);  --note-ink: oklch(0.4 0.07 70);   --note-bar: oklch(0.72 0.13 75);
}
@media (prefers-color-scheme: dark) { :root {
  --paper: oklch(0.2 0.012 260);    --panel: oklch(0.235 0.014 260);  --rule: oklch(0.34 0.014 260);
  --ink: oklch(0.92 0.008 85);      --ink-2: oklch(0.72 0.01 260);    --accent: oklch(0.75 0.12 255);
  --del-bg: oklch(0.33 0.06 25);    --del-ink: oklch(0.86 0.08 25);   --del-bar: oklch(0.66 0.17 25);
  --ins-bg: oklch(0.33 0.05 165);   --ins-ink: oklch(0.88 0.08 165);  --ins-bar: oklch(0.66 0.13 165);
  --note-bg: oklch(0.27 0.025 80);  --note-ink: oklch(0.86 0.06 85);  --note-bar: oklch(0.74 0.12 80);
} }
```

- `--accent` 只用在可以操作的東西上：選中的切換、焦點環、連結、滑桿。`::selection`、`caret-color`、`accent-color`、`scrollbar-color` 和 `:focus-visible` 也從這組取色。

## 字體

只用系統字，離線也能顯示。Latin 字族排在 CJK 前面，英文和數字才會用 Latin 字形。

```css
--font-ui:   system-ui, -apple-system, "Segoe UI", "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
--font-doc:  "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Songti TC", "Noto Serif TC", "PMingLiU", serif;
--font-code: ui-monospace, "SF Mono", Menlo, Consolas, "Noto Sans Mono CJK TC", monospace;
```

- 文件內文用 `--font-doc`，工具列、標籤、說明和計數用 `--font-ui`。原文件是無襯線的（簡報、海報），內文也改用 `--font-ui`。
- 字級固定用 rem：內文 1.0625rem、行高 1.7；說明與標籤 0.875rem，不再更小；段落標題 1.375rem、頁面標題 2rem（手機 1.625rem）；摘要或結論段 1.125–1.25rem。
- 計數、行號和數字欄加 `font-variant-numeric: tabular-nums`；`html` 加 `text-autospace: normal`。
- 次要文字用 `--ink-2` 加上較小的字級來區分，正體字。
