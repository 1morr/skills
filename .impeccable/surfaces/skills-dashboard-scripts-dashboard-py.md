---
version: 1
slug: "skills-dashboard-scripts-dashboard-py"
primary_target: "skills/dashboard/scripts/dashboard.py"
related_targets: ["skills/dashboard/SKILL.md"]
---

# dashboard 專案總覽頁

Scope: `skills/dashboard/scripts/dashboard.py` 裡的 `PAGE`（本機伺服器頁和靜態單檔是同一份）。Mode: Operate。
Reader: repo 的主人，一個人帶幾個 agent；開工前掃幾十秒，或整天開在旁邊瞄。筆電全寬和半邊視窗（700–900px）都常用，手機不是目標。
Job: 先回答「現在該我做什麼」，再看整體進度、Agent 自己定的決定、歷史。頁面不能改 repo，所以給可貼的指令和 `檔案:行`。
Must keep: 資料由 `collect()` 現讀、每 3 秒重讀；多個 repo 切換；「讀不到的檔／行」照列；離線單檔、不載入外部資源；決策的篩選與搜尋。
Constraints: 外觀只屬於 dashboard，不沿用 tutor，也不取 `pages/scripts/tokens.css`；專案不設 DESIGN.md，方向只記在這份紀錄（使用者指定，2026-11-15）。
Decided（使用者，2026-11-15）: 深色手動切、記在瀏覽器；「標為看過」的紀錄存在瀏覽器（localStorage），換瀏覽器就重來；配色從第一版的海軍藍加台鐵藍改成黑白灰。

## Direction contract

THESIS: 整個專案排成一張火車時刻表：里程碑是車次（一欄），票是停靠站（一列列往下），一條琥珀線標出現在開到哪。拒絕現行「一頁直排六區、每區一格格圓角卡片和膠囊」的排法。

OWN-WORLD: 白底、近黑的字、淺灰的側欄和表頭，整頁只有兩個顏色：琥珀色只表示「現在」，紅色只表示「你上次看過之後變了」。狀態用記號的形狀：實心點＝做完、空心點＝還沒、劃掉＝不做。直角或 3–4px 小圓角，欄線分隔；隔列淡灰底；數字一律等寬。系統黑體，一個字族。深色版是深灰底，同樣兩個顏色。

STORY: 打開先讀到一句該他做的事和一條可貼的指令；往下一眼看到每個里程碑走到哪一站；紅色記號告訴他離開之後哪幾格變了，按「標為看過」才熄。要細看就換分頁，每一頁都不長。

FIRST VIEWPORT: 左邊 216px 淺灰側欄：repo 名、五個分頁（現在／里程碑／功能與變更／決策／紀錄）各帶數量、其他 repo、更新時間。主區最上面一列：左邊大字是等他決定的問題或下一步，右邊是指令框和複製鈕，上面一條粗線（在等他決定時是琥珀色）。接著是里程碑時刻表：表頭每欄一個里程碑（進行中的那欄琥珀底），列是票，現在那一格上下各一條琥珀線。表下兩欄：Agent 自己定而他還沒看的、最近的 session。半邊視窗時側欄收成頂端一列，時刻表在自己的框裡橫向捲。

FORM: 台鐵印刷時刻表；我排序的七個候選裡的第 1 個（使用者在方向頁選的）。seed:8b91c6622321a62d。Signature：時刻表的欄列節奏加一條「現在」橫線；紅色變更記號留到看過為止。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

（FINISH 的 DESIGN.md 一項在這個專案由這份 surface 紀錄代替：使用者指定不寫專案的 DESIGN.md。）
