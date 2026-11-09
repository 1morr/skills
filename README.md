# skills

給 [Claude Code](https://code.claude.com) 用的 skills，打包成一個 plugin。

| Skill | 叫用 | 做什麼 |
|---|---|---|
| [bake-off](skills/bake-off/SKILL.md) | `/1morr:bake-off [版數] <prompt 或 prompt 檔> [現成版本…]`（只能手動叫用） | 同一個任務平行做幾版再挑一版：從主分支開一個刪掉舊產出的 base 分支，用 [Orca](https://www.onorca.dev) 為每一版開 worktree 和子 Claude Code session，送同一份 prompt（先提修改建議給你確認）。各版的開工計畫整理成一張表讓你一次核可，中途的需求問題給每版同一個答案。也可以把現成的版本（檔案、zip、claude.ai artifact）加進來一起比，版數給 0 就只比現成版本。做完列出每版的產出位置，先定評分項再逐版實際渲染審查，建議用哪一版當基礎（你說過偏好的會正面回應）、它還要改什麼、別版有哪些能合進來（逐項註明來源）。需要 Orca，共用 ticket-coordinator 的腳本 |
| [doc-diff](skills/doc-diff/SKILL.md) | 說「給我 diff 的 html」「左邊原來右邊修改」，或由其他 skill 呼叫 | 把同一份文件的兩個版本（docx、PDF、HTML 頁面或海報、Markdown、純文字）做成一頁逐字對照：整份左右並排或合併顯示、可只看改動、每處改動可附原因、docx 表格逐格比對（插入的欄用表頭對齊）、可並排兩版的渲染圖。比的是讀者看到的內容，不是產生它的原始碼 |
| [review-loop](skills/review-loop/SKILL.md) | `/1morr:review-loop <產出路徑> [補充]`（只能手動叫用） | 一輪一輪審一份成品（作業、海報、報告）到可以交：每輪用 [Orca](https://www.onorca.dev) 開一個新 session 當審查員（它再開分角度的子代理和盲做），只回報不改；主對話逐條查證、決定改什麼、動手改並 commit。只有採納了必須修才開下一輪，只剩建議修就改完收尾，避免多審幾輪只是在挑小毛病。定案附理由和出處，每輪自動帶進 prompt。收尾時開一個 opus 子代理只看起點和最終版，找出越改越長、重複、題目沒問的內容並精簡，最後用 doc-diff 在產出旁邊存一份起點→最終版的總 diff，每處改動附原因。需要 Orca，共用 ticket-coordinator 的腳本 |
| [showcase](skills/showcase/SKILL.md) | `/1morr:showcase [commit \| 範圍 \| PR# \| 分支] [no-run] [post] [auto]`，或直接說「展示這個改動」。預設實跑擷取、不提問；`post` 貼成 PR 留言，`auto` 全程不問（適合接在自己的流程後面） | 把一次程式改動展示給沒寫它的人，不必問 agent、不必自己跑：實跑修改前後兩版，擷取截圖、錄影、輸出與測試結果，產出內嵌證據的 HTML 報告（貼到 PR 時另有純文字版），說明改了什麼、為什麼、做了哪些決策、合併風險（單向或雙向門、影響範圍）；做法能用示意圖（呼叫樹、檔案樹、示意 diff）就畫。改到文件或產出檔時，逐字對照交給 doc-diff。合併風險與示意圖參考 [mattpocock/skills 的 pr](https://github.com/mattpocock/skills/tree/main/skills/engineering/pr) |
| [tutor](skills/tutor/SKILL.md) | `/1morr:tutor [作業 \| topic \| 考試] [read \| learn]`，或說「教我」「看不懂」「複習」 | 把大學課程、作業或考試教給沒上過課、零基礎的人：以老師課件為唯一標準，產出單一 HTML 導讀頁，左右兩欄並排、各自捲動。左欄照講義順序逐頁教（課件截圖附同版面的中文翻譯圖，點圖切換原文；術語附「怎樣才算」的定義，公式都寫全再代入數字，每段結尾有重點），右欄開頭是題型表，接著是老師的例題和這個 topic 的作業：每題把用到的定義、公式和課件截圖放在題目旁邊，只看右欄也能做，做法和答案摺起來、可一鍵全部展開；別的 topic 或別的課的前置知識在原地從零教，不叫讀者去翻；少數連回左欄的 § 連結有「回到剛才」可以跳回來；還沒交的作業另出照老師格式寫的答案紙。文科課用 `data-problems="text"`，答案是要點和句子，可放摺起來的自測。`read`（兩天內要交 / 考，或不想被問）自己讀完整頁；`learn` 用同一份頁面，在對話裡由你一步步做例題、再自己做沒看過的同類題，做對才算會，學習紀錄記每類題會不會做；另出一份練習頁：先是只考一個判斷的基本功小題，再是對照每題例題、但結論或陷阱不同的同類題，每題下面有能手寫也能打字的畫布，做完按「複製給 Claude」貼回對話批改 |
| [ticket-coordinator](skills/ticket-coordinator/SKILL.md) | `/1morr:ticket-coordinator <票目錄> [順序]`（只能手動叫用） | 當協調者，用 [Orca](https://www.onorca.dev) 為每張票開一個子 Claude Code session 解票、代答提問、驗收、合併，逐張跑完隊列。需要 Orca |

## 安裝

在 Claude Code 裡：

```
/plugin marketplace add 1morr/skills
/plugin install 1morr@1morr-skills
```

plugin 不釘版本，`/plugin update 1morr@1morr-skills` 會更新到最新 commit；也可以在 `/plugin` 的 Marketplaces 分頁打開自動更新。

## 開發

把 clone 下來的目錄加成 marketplace，plugin 會直接從這個目錄載入：改完檔案，開新 session 或執行 `/reload-plugins` 就生效，不用 push、不用重裝。

```
claude plugin marketplace add <clone 的路徑>
claude plugin install 1morr@1morr-skills
```

新增 skill：建 `skills/<名稱>/SKILL.md`，plugin 會自動載入；同時在上面的表格加一列。

測試（CI 跑的就是這四條）：

```
python -m unittest discover -s skills/showcase/tests
uv run --no-project --with python-docx --with pymupdf python -m unittest discover -s skills/doc-diff/tests
bash skills/ticket-coordinator/scripts/selftest.sh
uv run --no-project --with pymupdf --with pillow python -m unittest discover -s skills/tutor/tests
```

檢查 manifest：`claude plugin validate .`。manifest 刻意不寫 `version`（寫了會把使用者釘在那個版本），所以 validator 會提醒缺 `version`，那條可以忽略。

## 授權

MIT
