---
version: 1
slug: "skills-tutor-assets-lesson-css"
primary_target: "skills/tutor/assets/lesson.css"
related_targets: ["skills/tutor/assets/lesson.js","skills/tutor/scripts/build.py"]
---

# tutor 導讀頁

Scope: tutor 的導讀頁（`skills/tutor/assets/lesson.css`、`lesson.js`、`scripts/build.py` 組出的頁）。Mode: Read。
Reader: 零基礎學生；電腦和平板為主，手機考前看重點。兩條路線：照順序讀、直接做題卡住才查。
Must keep: § 編號、老師截圖的中英切換、先自己做再打開答案、速查卡、離線單檔。
Unresolved: 練習頁和模擬卷是否跟著換同一套外觀；深色模式是否保留。

## Direction contract

THESIS: 一本只有一條捲軸的課本。講義、例題、作業排成一本書的章節；拒絕現行「兩欄各自捲動、題目欄把講義再寫一次」的排法。

OWN-WORLD: 白紙、近黑的字、一個藍色管結構（§ 編號、連結、名詞），三支螢光筆各管一件事：黃＝答案和要帶走的、粉紅＝容易錯、綠＝讀過或答對。螢光筆是下半截的筆刷，不是色塊框。只有「這頁重點」是整塊上色。系統黑體內文，數學用襯線。

STORY: 讀者一打開就看到整本的目錄和自己在哪一行；讀到哪，目錄上那一行的 § 數字就變成藍底白字、標題變粗。做題時要查講義，原文那一段在旁邊打開，不離開題目。

FIRST VIEWPORT: 左邊固定的目錄欄（分「講義／例題／作業」三組，現在那一段的 § 數字藍底白字、讀過的打勾、上面寫讀了幾段和還剩多久）；中間一欄正文，約 40 個中文字寬，章節開頭是大號藍色 § 數字加問句標題；講義原文的截圖都排在正文裡，和正文同寬。頂端一條頁眉寫現在的 § 和小節，下面一條進度線，表示這一段讀到多少。

FORM: 兩色印刷的課本加上學生自己的螢光筆。seed: none (pinned)。使用者的原話：「比較簡潔，白底黑字，有顏色的高亮，能夠實時看到自己正在哪個位置，不會混亂」「像教材那樣能夠一眼看出來」。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
