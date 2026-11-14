---
name: tutor 紅黑雙色參考書
description: 白紙、黑墨、一種紅、一種螢光黃的應試參考書；導讀頁、練習頁、模擬卷共用同一個世界。
colors:
  paper: "#ffffff"
  ink: "#111111"
  mute: "#555555"
  hair: "#c9c9c9"
  red: "#c8201a"
  red-wash: "#fbe3e1"
  highlighter: "#ffe45c"
  highlighter-ink: "#111111"
  grid: "#e4e4e4"
typography:
  display:
    fontFamily: "PingFang TC, Noto Sans TC, Microsoft JhengHei, Segoe UI, system-ui, sans-serif"
    fontSize: "1.7rem"
    fontWeight: 800
    lineHeight: 1.3
  band:
    fontFamily: "PingFang TC, Noto Sans TC, Microsoft JhengHei, Segoe UI, system-ui, sans-serif"
    fontSize: "1.16rem"
    fontWeight: 700
    lineHeight: 1.45
  title:
    fontFamily: "PingFang TC, Noto Sans TC, Microsoft JhengHei, Segoe UI, system-ui, sans-serif"
    fontSize: "1.08rem"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "PingFang TC, Noto Sans TC, Microsoft JhengHei, Segoe UI, system-ui, sans-serif"
    fontSize: "16.5px"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: "PingFang TC, Noto Sans TC, Microsoft JhengHei, Segoe UI, system-ui, sans-serif"
    fontSize: "0.84rem"
    fontWeight: 700
    lineHeight: 1.5
  math:
    fontFamily: "STIX Two Text, Cambria, Times New Roman, PingFang TC, Noto Sans TC, serif"
    fontSize: "1.1rem"
    fontWeight: 400
    lineHeight: 2
  data:
    fontFamily: "ui-monospace, SF Mono, Consolas, Courier New, monospace"
    fontSize: "0.92em"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  none: "0px"
  dot: "50%"
spacing:
  band-x: "0.85rem"
  box-x: "0.9rem"
  block: "1.2rem"
  section: "4.5rem"
  bar: "46px"
  edge: "36px"
components:
  section-band:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.band}"
    rounded: "{rounded.none}"
    padding: "0.5rem 0.85rem"
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.15rem 0.7rem"
  button-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-pressed-cover:
    backgroundColor: "{colors.red}"
    textColor: "{colors.paper}"
  tab-current:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    width: "36px"
  definition-test:
    backgroundColor: "{colors.highlighter}"
    textColor: "{colors.highlighter-ink}"
  cover-sheet:
    backgroundColor: "{colors.red-wash}"
  jump-cell-done:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.7rem"
  jump-cell-wrong:
    textColor: "{colors.red}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.7rem"
  answer-sheet:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.math}"
    rounded: "{rounded.none}"
    padding: "0.8rem 1.1rem"
  running-head:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    height: "46px"
---

# Design System: tutor 紅黑雙色參考書

> 範圍說明：這個 repo 刻意讓每個產出頁面的 skill 各有自己的視覺世界（PRODUCT.md 明說「不共用一套外觀」）。本文件只記錄 tutor skill 的世界「紅黑雙色參考書」，涵蓋 `skills/tutor/assets/` 的 `lesson.css`、`lesson.js`、`practice.css`、`practice.js`，也就是導讀頁、練習頁和模擬卷。checkpoint、explain、dashboard、diff 的頁面仍用 `pages/scripts/tokens.css` 和 `page.css`，之後各自補一節；這裡不描述它們，也不把本文件的規則套到它們身上。

## Overview

**Creative North Star: "紅黑雙色參考書"**

像一本考前用的雙色印刷參考書。白紙、黑墨、一種紅、一種螢光黃，沒有灰底色塊。層次靠黑線、黑色橫條和字重，不靠淺色提示框。讀者是零基礎的學生，一次讀很久，要隨時知道自己在第幾節、先自己做再打開答案。使用者的原話是「像教材那樣白底黑字、黃色紅色高光」，並且不要藍色、不要框太多、不要太擠、不要像模板。

三種頁面是同一本書的不同部分。導讀頁是閱讀（Read）：寬螢幕左右兩欄，左課件、右題目。練習頁和模擬卷是操作（Operate）：一題一節，題目在上、畫布在下。模擬卷的計時列和練習頁的書眉扮演同一個角色，都是頂端那條 46px 的黑色粗底線列。

深色模式是黑紙白墨，紅和黃各換一個在黑底上讀得清楚的值。答案紙和畫布在深色模式仍是白紙，因為它們模擬真的紙，筆色和複製出去的圖也是白底。

**Key Characteristics:**
- 紅色有固定語意：要背的詞、算出來的答案、答錯或錯誤狀態、需要再確認的動作。
- 黃色只有三個用途：判斷方法、選取文字、跳轉後的閃光。
- 實心黑只留給兩種東西：一節的黑色橫條、現在這節的爪標。
- 沒有淺色填色塊，沒有圓角，沒有彩色陰影。
- 狀態一律用字寫出來，顏色只是輔助。

## Colors

一張白紙、一支黑墨、一種印刷紅、一支螢光筆。其餘是從黑墨退出來的灰字和灰線。

### Primary
- **印刷紅** (`colors.red`，淺色 #c8201a，深色 #ff7566)：要背的詞（`dfn`）、算出來的答案（`.ans`）、速查卡題型表中間那欄、「常見錯誤」的線和標籤、答錯的狀態（填答格 `.no`、題號格 `a.no`）、「再按一次」的待確認按鈕（`.armed`）、超時的倒數、焦點框、插入點。小節的節號 `.num` 也是紅字。

### Secondary
- **螢光黃** (`colors.highlighter`，淺色 #ffe45c，深色 #e6c84a，字色 `colors.highlighter-ink` #111111)：只用在三處。判斷方法 `.def .test`（用 inline 漸層畫成貼著字的螢光筆，不是整條色帶）、文字選取 `::selection`、跳轉到某一節後 2.2 秒的閃光 `:target`。

### Neutral
- **白紙** (`colors.paper`，深色 #141414)：頁面底色，也是按鈕、書眉、面板的底。
- **黑墨** (`colors.ink`，深色 #ededed)：內文、所有粗細黑線、框、黑色橫條底色。
- **灰字** (`colors.mute`，深色 #a8a8a8)：次要說明、圖說、清單符號、「打開／收起」的狀態字。
- **髮線灰** (`colors.hair`，深色 #474747)：表格列線、細分隔、圖片外框。
- **淡紅底** (`colors.red-wash`，深色 #3b1b18)：只用在速查卡被遮住的那一格（遮字板）和它滑開的動畫，是遮字板這個物件本身的顏色，不是底色塊。
- **方格灰** (`colors.grid`，#e4e4e4)：只用在練習頁畫布的方格，見 Components 的畫布。

### Named Rules
**The Red Means Memorise Rule.** 紅色只出現在要背的詞、算出來的答案、答錯或錯誤狀態。不拿紅色當強調、裝飾或品牌色。

**The Highlighter Is Not Hover Rule.** 黃色只給判斷方法、選取和跳轉閃光。滑過（hover）一律用反白（黑底白字）或底線，不用黃色。

**The Solid Black Is Reserved Rule.** 實心黑底只給一節的黑色橫條（`h2`、`h2.part`、`.cheat::before`）和現在這節的爪標。滑過爪標只畫粗底線，不填黑，否則分不出現在在哪。按鈕和選單的 hover 反白是短暫的互動回饋，不算「保留」。

**The No Tint Rule.** 不用淺色底色塊分層次。要分開兩塊內容，用一條黑線或髮線加一個粗體標籤。

## Typography

**Display / Body Font:** PingFang TC，後面接 Noto Sans TC、Microsoft JhengHei、Segoe UI、system-ui（只用系統字型，離線可開）。
**Math / 英文原文:** STIX Two Text，接 Cambria、Times New Roman，最後落回中文黑體（中文字不會變成細明體）。
**Data / 軟體輸出:** ui-monospace、SF Mono、Consolas。

**Character:** 一般內文是中文黑體，數學式、變數和英文原文換成襯線，像教科書。數字一律等寬（`tabular-nums lining-nums`），表格和計時才對得齊。

### Hierarchy
- **Display** (800，1.7rem，行高 1.3；手機 1.45rem)：書名或科目名 `h1`。練習頁的 `h1` 下面壓一條 1.5px 黑線，像考卷封面。
- **Band** (700，1.16rem，行高 1.45；手機 1.05rem)：節標題 `h2`、練習頁的 `h2.part`、速查卡標題，黑底白字。題目標題 `section.q h2` 是 1.25rem。
- **Title** (700，1.08rem，行高 1.5)：小節標題 `h3`，下面一條 1.5px 黑線。
- **Body** (400，16.5px，行高 1.8；練習頁 1.75；手機 16px)：導讀頁欄寬最寬 44rem，練習頁 50rem。
- **Label** (700，0.84rem，行高 1.5)：「定義」「這題記住」「為什麼」「常見錯誤」這類條目標籤、書眉按鈕、爪標（0.74rem）。
- **Math** (400，1.1rem，行高 2)：`.calc` 計算、`.sheet` 答案紙（16px／1.65）、`math` 元素、變數 `i`／`var`（1.06em 襯線斜體）。
- **Data** (0.92em，等寬)：練習頁的 `.data`、填答格、`pre.mtb` 軟體輸出（0.84rem）、`code`。

### Named Rules
**The Tabular Numbers Rule.** 數字欄、節號、計時、表格一律 `tabular-nums lining-nums`。

**The Serif For Symbols Rule.** 變數、公式、英文原文用襯線；其餘一律黑體。不引入第三種展示字體。

## Layout

導讀頁窄螢幕是單欄（最寬 44rem），課件接題目上下排。1100px 以上變成左右兩頁各佔半個視窗，各自捲動，中間一條 1px 黑線；左頁書口（爪標）在左、右頁書口在右，各 36px（`--edge`）。頂端 46px（`--bar`）是書眉。內容欄最寬 42rem 置中，書眉用同一個內距往兩邊伸到欄邊。

練習頁和模擬卷是單欄，`main` 最寬 50rem，旁邊的查表面板打開時（1100px 以上）把 `main` 往左推，不蓋住題目。

間距沒有統一刻度，是從書的節奏長出來的：節與節之間 4.5rem（寬螢幕每欄第一節 2.5rem），小節 2.6rem，一般區塊 1.2rem，黑色橫條內距 0.5rem 0.85rem，框內左右 0.9rem。手機寬（560px 以下）側邊內距縮到 1rem，題號格每格只留題號。

窄螢幕的爪標躺在畫面底下（固定在底部、高 36px、上緣 3px 黑線），兩欄的節排成一列。

表格是書籍式：上下 1.5px 黑線、表頭下一條黑線、列間髮線，沒有直線。太寬的表、公式、答案紙在自己那一行橫向捲動，不撐寬整頁。

## Elevation & Depth

平面。深度靠黑線粗細表達：1px 髮線是次要分隔，1.5px 是條目與框，3px 只給書眉（`.bar`、`.clock`）和窄螢幕的爪標列。不用卡片、不用漸層面板。

唯一的陰影是查表面板（`#panel`）：`box-shadow: -10px 0 28px -14px rgba(0,0,0,.35)`，一條向左的柔邊，讓它從頁面上浮起來，這是整個系統唯一浮起的物件。畫布工具列色點的 `0 0 0 1.5px` 外環是描邊，不是陰影。

### Named Rules
**The Flat Page Rule.** 除了查表面板，任何東西都不加陰影。層次用線，不用影。

## Shapes

全部直角（`border-radius: 0`，按鈕明確寫出）。唯一的圓是畫布工具列的筆色點（50%）。框是黑色 1–1.5px 實線；表示「錯」的框是紅色 1.5px 虛線（題號格 `a.no`、填答格 `.no`、被遮住的格子底線）。題號格是一排相鄰共用邊線的方格，像考卷封面的格子。

## Components

### 書眉（導讀頁 `.bar`、練習頁 `.bar`、模擬卷 `.clock`）
- 每欄頂端 46px、`paper` 底、下緣 3px 黑線，`position: sticky`。
- 導讀頁：欄名（課件／題目，800）、現在讀到哪一節（`.here`，灰字，捲動時換，按一下回到該欄目錄）、遮字板開關、圖片語言、查表、列印速查卡。
- 練習頁：現在第幾題（`.here`，粗體）、右側「查表」。按一下回到題號格。
- 模擬卷：同一個位置換成計時列：倒數 1.3rem／800、開始與交卷按鈕（黑底白字）、狀態字。超時時倒數變紅。

### 按鈕
- 直角、`paper` 底、1.5px 黑框、0.84–0.88rem；hover 反白成黑底白字。
- 開關型按鈕用 `aria-pressed`：工具列與面板分頁按下是黑底白字；遮字板開關按下是紅底（見下）。
- 需要確認的動作（清空畫布、交卷）按第一下變紅並把字改成「再按一次清空」「再按一次交卷」，2.5 秒不再按就還原。交卷不能反悔，要連按兩下。
- 停用時 `opacity: .45`。

### 爪標（`.tabs`）
- 書口一排方格，寬螢幕直立在兩頁外緣，窄螢幕躺在底部。
- 現在這節實心黑底白字（`aria-current="true"`）；上次讀到的那節右上角有 6px 紅色摺角（`.mark`）；hover 只畫 2px 底線。

### 條目（定義、這頁重點、為什麼、常見錯誤、符號表）
- 不加框、不上底色。上緣一條 1.5px 黑線，加一個粗體標籤。
- 「定義」「為什麼」「常見錯誤」的標籤和第一行內文排在同一行；「這題記住」「這頁重點」的標籤獨佔一行，條目間髮線隔開。
- 定義裡的詞 `dfn` 是紅色粗體；判斷方法 `.test` 前面自動加「怎樣才算：」並畫螢光筆。
- 「常見錯誤」整條換成紅線、紅色標籤，是紅色語意中「錯」的那一類。
- 譯文 `div.tr` 上下髮線、標籤灰字，內文裡的粗體是紅字（對應課件上老師的紅框）。

### 遮字板（速查卡的答案欄）
- 速查卡是題目欄開頭一張可單獨列印的卡，標題是黑色橫條。題型表中間那欄是紅字答案。
- **預設打開。**這是使用者看過完整稿後定的決定。遮字板是自願的：要考自己時才按書眉的「遮住答案」。
- 遮住後每格被淡紅底加紅色虛線底邊蓋住，點一格打開一格，開時蓋板往右滑走（0.32 秒，`prefers-reduced-motion` 時關閉）。這是整個導讀頁唯一的動態。
- 開關文字寫出狀態：未遮是「遮住答案」，已遮是「答案：已遮住」（紅底按鈕）。狀態記在瀏覽器的 localStorage。列印時答案一律顯示、遮板與說明隱藏。

### 摺疊（`details`）
- 右邊用字寫出現在的狀態：「打開」「收起」（灰字 0.86rem）。不用箭頭圖示。
- 一般摺疊只有上下髮線。先自己做再打開的那種（`details.answer`、`details.check`、練習頁的 `details.model`）有 1.5px 黑框，標題右側寫「先自己做，再打開」或「打開」，hover 整條反白。

### 答案紙（`.sheet`）
- 模擬真的紙：白底黑字襯線，1px 黑框，內距 0.8rem 1.1rem；標籤「答案紙上寫這樣」是灰字。深色模式仍是白紙，答案用固定紅 #c8201a。

### 題號格（練習頁 `nav.jump`）
- 一排每格同寬的方格，題號粗體在前、題名在後。做對是實心黑，答錯是紅色虛線框加粗體，對過範本答案的格子後面寫「已評」。目前題的格子下緣有 4px 紅色內線。手機寬只留題號。

### 填答格（`.fill`）
- 像考卷上的一條底線：只有 2px 黑底線的輸入框，等寬字。對了是雙底線加粗體結果字，錯了是紅色虛線底線加紅字。對錯都用字寫出來（`.result`）。

### 給分點（`.rubric`）
- 一列一列勾選，列間髮線；勾起來的那列粗體，hover 整列反白，分數灰字靠右。

### 畫布（`.pad`、`.tools`、`.board`）
- 白紙加一層 28px 的方格（`colors.grid`）。這個方格是繪圖功能：寫算式時對齊用，不是裝飾，所以深色模式也保持白底方格，不要改成底紋或拿掉。
- 筆色在 `practice.js` 的 `COLORS`：黑 #1d2433、紅 #c62828、藍 #1f5fd1，故意不跟頁面的紅同值，因為畫在白紙上、也會被複製成白底圖。工具列在畫布上方，黏在頂端，按下的工具是黑底白字。
- 文字工具的輸入框用黑色虛線外框；紅色插入點。

### 查表面板（`#panel`）
- 右側固定，寬 560–620px（手機全寬），1px 黑色左線，唯一的柔陰影。標頭一排分頁按鈕（按下是黑底白字），內容是整張統計表圖片。

## Do's and Don'ts

### Do:
- **Do** 用紅色標示要背的詞、算出來的答案、錯誤狀態；用 `colors.red` 的淺色與深色兩個值，不另造第二種紅。
- **Do** 把判斷方法畫成 inline 螢光筆（`.def .test`），選取和跳轉閃光用同一個黃。
- **Do** 用一條黑線加一個粗體標籤分開條目；要分一節就用黑底白字的橫條。
- **Do** 把狀態寫成字：打開／收起、遮住答案／答案：已遮住、已評、再按一次交卷；顏色是輔助。
- **Do** 讓現在這節獨佔實心黑（爪標）；滑過只畫底線。
- **Do** 讓模擬卷的計時列和練習頁的書眉保持同一個位置、同樣的 46px 和 3px 黑底線。
- **Do** 讓答案紙和畫布在深色模式仍是白紙。

### Don't:
- **Don't** 用黃色當 hover、強調或圖示色。
- **Don't** 用淺色底色塊、彩色提示框、卡片或側欄目錄樹把內容分層（使用者明確反對「框太多、太花」；這也是這個世界拒絕的文件站做法）。
- **Don't** 加藍色到頁面本身（使用者明確不要藍色）。畫布的藍筆是繪圖工具的墨色，不算頁面顏色，見下方未決問題。
- **Don't** 用圓角、漸層面板、除查表面板之外的陰影。
- **Don't** 把速查卡答案預設遮住；遮字板是使用者自己要考時才開的。
- **Don't** 拿掉畫布的方格，也不要把它當背景花紋複製到別處。

## Open Questions

- **畫布藍筆。**`practice.js` 的 `COLORS.blue`（#1f5fd1）提供藍色畫筆，而使用者對頁面說過「不要藍色」。來源沒有說這是否經過同意，也沒有說「不要藍色」是否涵蓋畫布工具。目前只記錄事實，不判斷。
- **答案紙內的紅色。**`.sheet .ans` 固定 #c8201a，不跟 `--red` 走（因為紙是白的）。是否要在其他白紙物件（畫布）統一，來源沒有說明。
- **間距刻度。**來源沒有統一的間距變數，只有 `--bar`、`--edge`、`--pad`；frontmatter 的 `spacing` 是從重複出現的值整理的，若之後要成為正式刻度需要使用者確認。
- **其他 skill。**checkpoint、explain、dashboard、diff 的頁面不在本文件範圍；它們是否與 tutor 共用任何東西尚未決定。

## 未收進系統的缺陷

目前沒有發現需要排除的違反 craft floor 的元素；兩個待決項目見上方 Open Questions。
