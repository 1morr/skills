# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

只有 repo 主人一個人。他用 Claude Code 開發自己的專案、修自己的課，這些 skill 產出的 HTML 頁是給他自己讀和操作的：

- **tutor**：他是零基礎的學生，照導讀頁學一個 topic，再做練習頁和計時模擬卷，目標考 90 分。一次讀很久，會來回對照課件和題目。
- **explain、checkpoint**：他是專案主人，讀一頁長文弄懂一段程式怎麼運作，或回顧一個里程碑並決定下一步。
- **dashboard**：他掃一眼就要知道專案在哪、下一步是什麼、有什麼等他決定。
- **diff**：他審一份文件或一段程式改動的前後差異。

## Product Purpose

一組 Claude Code skills，打包成 plugin `1morr`。其中五個會產出單檔 HTML 頁；頁面是 skill 的交付物，由腳本組頁、模型填內容。成功的樣子：讀者不用回對話問「這頁在講什麼」，也不用橫向捲動。

## Positioning

頁面的內容每句都對得到來源（課件頁碼、`檔案:行號`、commit），由腳本量過不會水平溢出才交付。

## Operating Context

- 頁面在本機瀏覽器開，從對話給的網址或完整路徑進去；skill 不替他開瀏覽器。
- 每個 skill 的頁面各有自己的視覺方向，各自定稿，不共用一套外觀。
- tutor 的頁面存在課程資料夾裡反覆使用；explain、checkpoint、diff 的頁是臨時頁；dashboard 會自動更新。

## Capabilities and Constraints

- 單檔 HTML，離線可開：只用系統字型，不載入外部資源。
- 淺色和深色都要，跟系統設定走。
- 內容是繁體中文夾英文術語、數學式、程式碼和檔案路徑。
- tutor 導讀頁要能列印。
- 寬螢幕（1440px）和手機寬（390px）都不能出現水平捲軸，由 `pages/scripts/overflow.py` 在組頁時檢查。

## Evidence on Hand

- tutor 的真實產出：`/Users/roxy/Downloads/ISOM3031/lessons/`（topic5 的導讀頁、練習頁、模擬卷）。
- 現有樣式：`skills/tutor/assets/`、`pages/scripts/tokens.css`、`pages/scripts/page.css`、`skills/dashboard/scripts/dashboard.py` 內嵌的樣式。
- 沒有商標、品牌色或指定字型。

## Product Principles

1. 內容先於介面：介面退到邊上，讀者的注意力留給講解、題目和證據。
2. 每一頁回答一個問題，讀者一進來就知道這頁是什麼、要他做什麼。
3. 來源查得到：每個說法旁邊找得到出處，但出處不打斷閱讀。
4. 腳本保證的事不靠模型自律：版面、溢出、樣式由腳本和共用樣式負責。
