---
version: 1
slug: "skills-tutor-assets-lesson-css"
primary_target: "skills/tutor/assets/lesson.css"
related_targets: ["skills/tutor/assets/practice.css","skills/tutor/assets/lesson.js","skills/tutor/assets/practice.js"]
---

# tutor 的頁面：導讀頁、練習頁、模擬卷

範圍：`skills/tutor/assets/` 的四個檔，由 `skills/tutor/scripts/build.py`、`practice.py` 內嵌進每一頁。模式：導讀頁是 Read；練習頁和模擬卷是 Operate，沿用同一個視覺世界。

讀者：repo 主人，零基礎的學生，一次讀很久。裝置：筆電整個視窗、半個螢幕（旁邊開課件或對話）、平板手寫、手機複習。

要他做到：照課件順序讀懂每一節，隨時知道自己在第幾節，先自己做再打開答案。

使用者定下的限制（原話）：「像教材那樣白底黑字、黃色紅色高光」；不要藍色；不要「框太多、太花」「太擠」「分不出現在在哪」「看起來像模板」。保留：寬螢幕左右兩欄、§ 編號互相對照、速查卡和自測、答案先摺起來。移除「回到剛才」按鈕，改由瀏覽器的上一頁還原兩欄的捲動位置。

使用者看過完整稿後定的：速查卡的答案預設打開，要考自己時才按「遮住答案」。列印時答案一律顯示。

## Direction contract

THESIS：導讀頁是一本紅黑雙色印刷的應試參考書。要背的詞和答案是紅字，要考自己時用遮字板蓋住。拒絕的是文件站的做法：側欄目錄樹加一個個淺色提示框。

OWN-WORLD：白紙、黑墨、一種紅、一種螢光黃，沒有灰底色塊。節標題是黑底白字的橫條；小節標題下面一條黑線，節號紅字。書口一排爪標，現在這節實心黑，上次讀到的那節有紅色摺角。定義由一條黑線隔開，詞是紅字，判斷方法畫螢光筆。黑體字，數字等寬。深色模式是黑紙白墨，紅和黃各換一個在黑底上讀得清楚的值。

STORY：他打開就看到自己在哪一節、這節學什麼、考什麼；讀到定義時紅字是要背的、黃線是判斷方法；做題時做法先摺起來；複習速查卡時按「遮住答案」，自己說一次再點開。

FIRST VIEWPORT：1440 寬時上面一條 46px 的書眉（課名、兩欄現在的節、遮字板開關、圖片語言、查表、列印速查卡）。下面兩頁各 720px，中間一條黑線。左頁書口在左、右頁書口在右，各 36px 的爪標。左頁從 §1 的黑色橫條開始，接「學到、怎麼判斷、考法」三列；右頁從速查卡的題型表開始，中間那欄是紅字答案（預設打開，書眉的「遮住答案」把它遮起來）。

FORM：紅黑雙色參考書，我的清單第 4 個。seed:2c8236c7a5f254e5。招牌互動是遮字板：一個全頁開關加逐格點開，狀態用字寫出來（遮住答案、答案：已遮住），記在瀏覽器裡。動態只有一個：點開時遮字板往旁邊滑走。

FINISH：unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
